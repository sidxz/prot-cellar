"""Cross-context runner wiring — the infrastructure adapter layer for imports.

Each :class:`ImportAdapter` builds a fresh :class:`AsyncUnitOfWork`, wires
repos / bulk use-cases / HTTP clients, and delegates to the matching runner —
exactly as the CLI scripts do, but using the :class:`ImportRuntime` injected by
the background worker instead of local engine + noop dispatcher.

``IMPORT_ADAPTERS`` is the registry the worker calls by :class:`ImportType`.

**IMPORTANT**: All three runner classes are imported at module top level so that
monkeypatching (e.g. ``protcellar.infrastructure.ingestion.import_adapters.ProteomeImportRunner``)
resolves correctly in tests.
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from protcellar.application.auth import AuthContext
from protcellar.application.imports.progress_reporter import ProgressReporter
from protcellar.application.protein_catalog.bulk_enrich_genes import BulkEnrichGenes
from protcellar.application.protein_catalog.bulk_upsert_genes import BulkUpsertGenes
from protcellar.application.protein_catalog.bulk_upsert_proteins import BulkUpsertProteins
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.domain.imports.enums import ImportType
from protcellar.infrastructure.ingestion.gene_enrichment_runner import GeneEnrichmentRunner
from protcellar.infrastructure.ingestion.go_import_runner import GoImportRunner
from protcellar.infrastructure.ingestion.import_runner import ProteomeImportRunner
from protcellar.infrastructure.ingestion.mycobrowser_client import (
    MYCOBROWSER_H37RV_GFF_URL,
    MycobrowserClient,
)
from protcellar.infrastructure.ingestion.organism_resolver import resolve_organism_id
from protcellar.infrastructure.ingestion.uniprot_client import UniProtClient
from protcellar.infrastructure.ingestion.url_guard import fetch_text_guarded, validate_public_url
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

_UNIPROT_BASE_URL = "https://rest.uniprot.org"


# ---------------------------------------------------------------------------
# ImportRuntime — injected by the background worker
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportRuntime:
    """All cross-cutting dependencies the worker hands to an adapter."""

    session_factory: async_sessionmaker[AsyncSession]
    dispatcher: EventDispatcherProtocol
    reporter: ProgressReporter
    params: dict[str, Any]
    auth: AuthContext
    load_upload: Callable[[uuid.UUID], Awaitable[bytes]]


# ---------------------------------------------------------------------------
# ImportAdapter protocol
# ---------------------------------------------------------------------------


class ImportAdapter(Protocol):
    """A runnable import strategy keyed on an :class:`ImportType`."""

    import_type: ImportType

    async def run(self, rt: ImportRuntime) -> dict[str, Any]: ...


# ---------------------------------------------------------------------------
# Concrete adapters
# ---------------------------------------------------------------------------


class ProteomeAdapter:
    """Wires :class:`ProteomeImportRunner` from ``rt``."""

    import_type = ImportType.PROTEOME

    async def run(self, rt: ImportRuntime) -> dict[str, Any]:
        params = rt.params
        proteome_id: str = params["proteome_id"]
        force: bool = bool(params.get("force", False))
        dry_run: bool = bool(params.get("dry_run", False))
        limit: int | None = params.get("limit")

        uow = AsyncUnitOfWork(rt.session_factory)
        protein_repo = SQLAlchemyProteinRepository(uow)
        gene_repo = SQLAlchemyGeneRepository(uow)
        bulk = BulkUpsertProteins(uow, protein_repo, rt.dispatcher)
        gene_bulk = BulkUpsertGenes(uow, gene_repo, rt.dispatcher)

        async with httpx.AsyncClient(base_url=_UNIPROT_BASE_URL, timeout=120.0) as http:
            runner = ProteomeImportRunner(
                uow,
                UniProtClient(http),
                bulk,
                gene_bulk=gene_bulk,
                reporter=rt.reporter,
            )
            summary = await runner.run(
                proteome_id,
                dry_run=dry_run,
                limit=limit,
                force=force,
                auth=rt.auth,
            )
        return dataclasses.asdict(summary)


class GeneEnrichmentAdapter:
    """Wires :class:`GeneEnrichmentRunner` from ``rt``."""

    import_type = ImportType.GENE_ENRICHMENT

    async def run(self, rt: ImportRuntime) -> dict[str, Any]:
        params = rt.params

        # Coerce organism_id from JSON string to UUID if provided
        raw_organism_id = params.get("organism_id")
        organism_id: uuid.UUID | None = (
            uuid.UUID(raw_organism_id) if raw_organism_id is not None else None
        )
        tax_id: int = int(params["tax_id"]) if params.get("tax_id") is not None else 83332

        uow = AsyncUnitOfWork(rt.session_factory)
        resolved_id, gene_count = await resolve_organism_id(
            uow, organism_id=organism_id, tax_id=tax_id
        )
        if gene_count == 0:
            raise ValueError(f"organism {resolved_id} has no genes to enrich")

        gff_url: str = params.get("gff_url") or MYCOBROWSER_H37RV_GFF_URL
        # Guard admin-supplied GFF URL against SSRF before any network I/O
        validate_public_url(gff_url)

        # Build essentiality loader
        essentiality_loader = None
        if params.get("essentiality_upload_ref"):
            ref = uuid.UUID(params["essentiality_upload_ref"])

            async def _load_from_upload() -> str:
                return (await rt.load_upload(ref)).decode()

            essentiality_loader = _load_from_upload
        elif params.get("essentiality_url"):
            ess_url: str = params["essentiality_url"]

            async def _load_from_url() -> str:
                # Manual redirect following validates every hop for SSRF safety
                return await fetch_text_guarded(ess_url)

            essentiality_loader = _load_from_url

        uow2 = AsyncUnitOfWork(rt.session_factory)
        gene_repo = SQLAlchemyGeneRepository(uow2)
        bulk = BulkEnrichGenes(uow2, gene_repo, rt.dispatcher)

        async with httpx.AsyncClient() as http:
            client = MycobrowserClient(http)
            runner = GeneEnrichmentRunner(
                bulk,
                client,
                gff_url=gff_url,
                essentiality_loader=essentiality_loader,
                reporter=rt.reporter,
            )
            summary = await runner.run(resolved_id, auth=rt.auth)
        return dataclasses.asdict(summary)


class GoOntologyAdapter:
    """Wires :class:`GoImportRunner` from ``rt``."""

    import_type = ImportType.GO_ONTOLOGY

    async def run(self, rt: ImportRuntime) -> dict[str, Any]:
        force: bool = bool(rt.params.get("force", False))
        uow = AsyncUnitOfWork(rt.session_factory)
        runner = GoImportRunner(uow, reporter=rt.reporter)
        summary = await runner.run(force=force)
        return dataclasses.asdict(summary)


# ---------------------------------------------------------------------------
# Registry — the worker looks up adapters here
# ---------------------------------------------------------------------------

IMPORT_ADAPTERS: dict[ImportType, ImportAdapter] = {
    ImportType.PROTEOME: ProteomeAdapter(),
    ImportType.GENE_ENRICHMENT: GeneEnrichmentAdapter(),
    ImportType.GO_ONTOLOGY: GoOntologyAdapter(),
}
