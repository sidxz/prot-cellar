"""Idempotent bulk upsert of UnpublishedStructure records, resolving proteins by accession.

Upsert key is (protein_id, method). ``ligand_ids`` are portable chem-cellar
molecule ids; resolution (Å) must be positive (the aggregate enforces it).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.application.target_biology._import_support import ItemResult, provenance_from
from protcellar.domain.protein_catalog.repository import ProteinRepository
from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import ProvenanceSourceType
from protcellar.domain.target_biology.repository import UnpublishedStructureRepository
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure


@dataclass(frozen=True, kw_only=True)
class UnpublishedStructureImportRecord:
    accession: str
    method: str | None = None
    resolution: float | None = None
    ligand_ids: tuple[uuid.UUID, ...] = ()
    is_published: bool = False
    is_experimental: bool = True
    pmid: str | None = None
    dataset: str | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertUnpublishedStructureCommand(Command):
    records: tuple[UnpublishedStructureImportRecord, ...]
    source_type: str = ProvenanceSourceType.PUBLISHED.value
    dry_run: bool = False


def _ligands(rec: UnpublishedStructureImportRecord) -> tuple[CompoundRef, ...]:
    return tuple(CompoundRef(compound_id=lid) for lid in rec.ligand_ids)


class BulkUpsertUnpublishedStructure:
    def __init__(
        self,
        uow: UnitOfWork,
        protein_repo: ProteinRepository,
        structure_repo: UnpublishedStructureRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._protein_repo = protein_repo
        self._st_repo = structure_repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: BulkUpsertUnpublishedStructureCommand, auth: AuthContext | None = None
    ) -> Result[list[ItemResult], DomainError]:
        require_admin(auth)
        results: list[ItemResult] = []
        async with self._uow:
            for i, rec in enumerate(input.records):
                try:
                    protein = await self._protein_repo.find_by_accession(rec.accession)
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
                    existing = await self._st_repo.find_owned_by_protein(
                        SHARED_WORKSPACE_ID, protein.id
                    )
                    match = next((s for s in existing if s.method == rec.method), None)
                    if match is not None:
                        match.update(
                            resolution=rec.resolution,
                            ligands=_ligands(rec),
                            is_published=rec.is_published,
                            is_experimental=rec.is_experimental,
                            provenance=provenance,
                        )
                        if not input.dry_run:
                            await self._st_repo.save(match)
                        results.append(ItemResult(index=i, status="updated", id=str(match.id)))
                    else:
                        record = UnpublishedStructure.create(
                            workspace_id=SHARED_WORKSPACE_ID,
                            protein_id=protein.id,
                            method=rec.method,
                            resolution=rec.resolution,
                            ligands=_ligands(rec),
                            is_published=rec.is_published,
                            is_experimental=rec.is_experimental,
                            provenance=provenance,
                        )
                        if not input.dry_run:
                            await self._st_repo.save(record)
                        results.append(ItemResult(index=i, status="created", id=str(record.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
