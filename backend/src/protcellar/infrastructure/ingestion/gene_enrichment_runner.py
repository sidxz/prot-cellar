"""Orchestrates enriching existing genes from genome-annotation sources.

Ties the GFF client (network) + pure parsers/mapper + the ``BulkEnrichGenes``
use case (DB, owns its own UoW) together. Like the proteome import runner this
is infrastructure-level glue — it touches the network and (via the use case) the
database — so it lives beside the other ingestion adapters.

Flow: fetch GFF text -> ``parse_mycobrowser_gff`` -> (optional) load + parse a
DeJesus essentiality table -> ``build_enrichment_records`` -> ``BulkEnrichGenes``.
The use case matches each record to a gene by locus tag within the organism and
idempotently sets location + merges dataset-scoped annotations.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from returns.result import Result

from protcellar.application.auth import AuthContext
from protcellar.application.protein_catalog.bulk_enrich_genes import (
    EnrichSummary,
    GeneEnrichmentRecord,
)
from protcellar.domain.shared.errors import DomainError
from protcellar.infrastructure.ingestion.dejesus_essentiality import parse_dejesus_essentiality
from protcellar.infrastructure.ingestion.gene_enrichment_mapper import build_enrichment_records
from protcellar.infrastructure.ingestion.mycobrowser_gff import parse_mycobrowser_gff

_DEFAULT_ASSEMBLY = "ASM19595v2"


class GffClient(Protocol):
    async def fetch_text(self, url: str) -> str: ...


class _BulkEnrich(Protocol):
    async def __call__(
        self,
        organism_id: uuid.UUID,
        records: Sequence[GeneEnrichmentRecord],
        auth: AuthContext | None = None,
    ) -> Result[EnrichSummary, DomainError]: ...


# An essentiality loader returns the raw table text (TSV/CSV) to be parsed. It is
# a coroutine so a file read or a network fetch both fit; ``None`` skips essentiality.
EssentialityLoader = Callable[[], Awaitable[str]]


class GeneEnrichmentRunner:
    def __init__(
        self,
        bulk_enrich: _BulkEnrich,
        gff_client: GffClient,
        *,
        gff_url: str,
        essentiality_loader: EssentialityLoader | None = None,
        assembly: str = _DEFAULT_ASSEMBLY,
    ) -> None:
        self._bulk = bulk_enrich
        self._client = gff_client
        self._gff_url = gff_url
        self._load_essentiality = essentiality_loader
        self._assembly = assembly

    async def run(
        self, organism_id: uuid.UUID, *, auth: AuthContext | None = None
    ) -> EnrichSummary:
        gff_text = await self._client.fetch_text(self._gff_url)
        gff = parse_mycobrowser_gff(gff_text)

        essentiality: dict[str, str] = {}
        if self._load_essentiality is not None:
            essentiality = parse_dejesus_essentiality(await self._load_essentiality())

        records = build_enrichment_records(gff, essentiality, assembly=self._assembly)
        return (await self._bulk(organism_id, records, auth)).unwrap()
