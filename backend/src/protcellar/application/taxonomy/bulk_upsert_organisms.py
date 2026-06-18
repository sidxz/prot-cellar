"""Idempotent bulk upsert of organism reference records, keyed on (source, source_record_id)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.shared.errors import DomainError
from protcellar.domain.taxonomy.enums import OrganismSource
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.repository import OrganismRepository


@dataclass(frozen=True, kw_only=True)
class OrganismImportRecord:
    ncbi_tax_id: int | None
    rank: str
    scientific_name: str
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    division: str | None = None


@dataclass(frozen=True, kw_only=True)
class BulkUpsertOrganismsCommand(Command):
    records: tuple[OrganismImportRecord, ...]
    dry_run: bool = False


@dataclass(frozen=True, kw_only=True)
class ItemResult:
    index: int
    status: str  # created | updated | skipped | failed
    id: str | None = None
    error: str | None = None


class BulkUpsertOrganisms:
    def __init__(
        self, uow: UnitOfWork, repo: OrganismRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: BulkUpsertOrganismsCommand, auth: AuthContext | None = None
    ) -> Result[list[ItemResult], DomainError]:
        require_admin(auth)
        results: list[ItemResult] = []
        async with self._uow:
            for i, rec in enumerate(input.records):
                try:
                    existing = await self._repo.find_by_source_record_id(
                        rec.source, rec.source_record_id
                    )
                    if existing is not None:
                        if existing.source_record_checksum == rec.source_record_checksum:
                            results.append(
                                ItemResult(index=i, status="skipped", id=str(existing.id))
                            )
                            continue
                        existing.update(
                            scientific_name=rec.scientific_name,
                            rank=rec.rank,
                            division=rec.division,
                            source_version=rec.source_release,
                        )
                        existing.source_record_checksum = rec.source_record_checksum
                        existing.source_release = rec.source_release
                        existing.imported_at = datetime.now(UTC)
                        if not input.dry_run:
                            await self._repo.save(existing)
                        results.append(ItemResult(index=i, status="updated", id=str(existing.id)))
                    else:
                        source_enum = (
                            OrganismSource(rec.source)
                            if rec.source in OrganismSource._value2member_map_
                            else OrganismSource.LOCAL
                        )
                        org = Organism.create(
                            ncbi_tax_id=rec.ncbi_tax_id,
                            rank=rec.rank,
                            scientific_name=rec.scientific_name,
                            source=source_enum,
                            division=rec.division,
                            source_version=rec.source_release,
                        )
                        org.source_record_id = rec.source_record_id
                        org.source_record_checksum = rec.source_record_checksum
                        org.source_release = rec.source_release
                        org.imported_at = datetime.now(UTC)
                        if not input.dry_run:
                            await self._repo.save(org)
                        results.append(ItemResult(index=i, status="created", id=str(org.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                # no commit on dry run
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
