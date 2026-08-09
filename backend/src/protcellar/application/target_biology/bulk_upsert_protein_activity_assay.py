"""Idempotent bulk upsert of ProteinActivityAssay records, resolving proteins by accession.

Upsert key is (protein_id, activity_measured, method).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.application.target_biology._import_support import ItemResult, provenance_from
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.shared.provenance import ProvenanceSourceType
from protcellar.domain.target_biology.protein_activity_assay import ProteinActivityAssay
from protcellar.domain.target_biology.repository import ProteinActivityAssayRepository


@dataclass(frozen=True, kw_only=True)
class ProteinActivityAssayImportRecord:
    accession: str
    activity_measured: str
    readout: str | None = None
    throughput: str | None = None
    condition: str | None = None
    method: str | None = None
    pmid: str | None = None
    dataset: str | None = None
    extensions: dict[str, Any] | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertProteinActivityAssayCommand(Command):
    target_workspace_id: uuid.UUID
    records: tuple[ProteinActivityAssayImportRecord, ...]
    source_type: str = ProvenanceSourceType.PUBLISHED.value
    dry_run: bool = False


class BulkUpsertProteinActivityAssay:
    def __init__(
        self,
        uow: UnitOfWork,
        protein_repo: ProteinRepository,
        assay_repo: ProteinActivityAssayRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._protein_repo = protein_repo
        self._assay_repo = assay_repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: BulkUpsertProteinActivityAssayCommand, auth: AuthContext | None = None
    ) -> Result[list[ItemResult], DomainError]:
        require_admin(auth)
        results: list[ItemResult] = []
        async with self._uow:
            for i, rec in enumerate(input.records):
                try:
                    protein = await self._protein_repo.find_by_accession(
                        rec.accession, workspace_id=input.target_workspace_id
                    )
                    if protein is None:
                        results.append(
                            ItemResult(
                                index=i,
                                status="failed",
                                error=f"unmatched accession {rec.accession}",
                            )
                        )
                        continue
                    provenance = provenance_from(input.source_type, rec.pmid, rec.dataset)
                    existing = await self._assay_repo.find_owned_by_protein(
                        input.target_workspace_id, protein.id
                    )
                    match = next(
                        (
                            a
                            for a in existing
                            if a.activity_measured == rec.activity_measured.strip()
                            and a.method == rec.method
                        ),
                        None,
                    )
                    if match is not None:
                        fields: dict[str, Any] = {
                            "readout": rec.readout,
                            "throughput": rec.throughput,
                            "condition": rec.condition,
                            "method": rec.method,
                            "provenance": provenance,
                        }
                        if rec.extensions is not None:
                            fields["extensions"] = {**(match.extensions or {}), **rec.extensions}
                        match.update(**fields)
                        if not input.dry_run:
                            await self._assay_repo.save(match)
                        results.append(ItemResult(index=i, status="updated", id=str(match.id)))
                    else:
                        record = ProteinActivityAssay.create(
                            workspace_id=input.target_workspace_id,
                            protein_id=protein.id,
                            activity_measured=rec.activity_measured,
                            readout=rec.readout,
                            throughput=rec.throughput,
                            condition=rec.condition,
                            method=rec.method,
                            provenance=provenance,
                            extensions=rec.extensions,
                        )
                        if not input.dry_run:
                            await self._assay_repo.save(record)
                        results.append(ItemResult(index=i, status="created", id=str(record.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
