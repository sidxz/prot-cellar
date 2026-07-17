"""Orchestrates enriching existing genes from genome-annotation sources.

Ties the GFF client (network) + pure parsers/mapper + the ``BulkEnrichGenes``
use case (DB, owns its own UoW) together. Like the proteome import runner this
is infrastructure-level glue — it touches the network and (via the use case) the
database — so it lives beside the other ingestion adapters.

Flow: fetch GFF text -> ``parse_mycobrowser_gff`` -> ``build_enrichment_records``
-> ``BulkEnrichGenes``. The use case matches each record to a gene by locus tag
within the organism and idempotently sets location + merges dataset-scoped
annotations. Essentiality is ingested separately via the DeJesus plugin.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from returns.result import Result

from protcellar.application.auth import AuthContext
from protcellar.application.imports.progress_reporter import NoopProgressReporter, ProgressReporter
from protcellar.application.protein_catalog.bulk_enrich_genes import (
    EnrichSummary,
    GeneEnrichmentRecord,
)
from protcellar.domain.shared.errors import DomainError
from protcellar.infrastructure.ingestion.gene_enrichment_mapper import build_enrichment_records
from protcellar.infrastructure.ingestion.mycobrowser_gff import parse_mycobrowser_gff

_DEFAULT_ASSEMBLY = "ASM19595v2"
_NOOP_REPORTER: ProgressReporter = NoopProgressReporter()


class GffClient(Protocol):
    async def fetch_text(self, url: str) -> str: ...


class _BulkEnrich(Protocol):
    async def __call__(
        self,
        organism_id: uuid.UUID,
        records: Sequence[GeneEnrichmentRecord],
        auth: AuthContext | None = None,
    ) -> Result[EnrichSummary, DomainError]: ...


# A GFF fetcher takes a URL and returns decoded GFF text.
GffFetch = Callable[[str], Awaitable[str]]


class GeneEnrichmentRunner:
    def __init__(
        self,
        bulk_enrich: _BulkEnrich,
        gff_client: GffClient,
        *,
        gff_url: str,
        gff_fetch: GffFetch | None = None,
        assembly: str = _DEFAULT_ASSEMBLY,
        reporter: ProgressReporter = _NOOP_REPORTER,
    ) -> None:
        self._bulk = bulk_enrich
        self._client = gff_client
        self._gff_url = gff_url
        # Allow callers to inject a custom fetch coroutine (e.g. SSRF-safe
        # fetch_text_secure); fall back to the injected client's fetch_text.
        self._gff_fetch: GffFetch = gff_fetch if gff_fetch is not None else gff_client.fetch_text
        self._assembly = assembly
        self._reporter = reporter

    async def run(
        self, organism_id: uuid.UUID, *, auth: AuthContext | None = None
    ) -> EnrichSummary:
        await self._reporter.phase("fetch GFF")
        gff_text = await self._gff_fetch(self._gff_url)

        await self._reporter.phase("parse")
        gff = parse_mycobrowser_gff(gff_text)

        records = build_enrichment_records(gff, assembly=self._assembly)

        await self._reporter.phase("enrich")
        result = (await self._bulk(organism_id, records, auth)).unwrap()
        await self._reporter.advance(len(records), len(records))
        return result
