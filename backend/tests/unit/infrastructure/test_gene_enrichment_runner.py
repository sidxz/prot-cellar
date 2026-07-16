"""Unit tests for the Mycobrowser client + gene-enrichment runner.

The client is exercised with an ``httpx.MockTransport`` (no real network); the
runner is exercised with a fake client returning fixture GFF text and a fake
``BulkEnrichGenes`` capturing the records, so it asserts the
fetch -> parse -> map -> enrich wiring without touching the network or a DB.
"""

from __future__ import annotations

import gzip
import uuid
from collections.abc import Sequence

import httpx
import pytest

from protcellar.application.protein_catalog.bulk_enrich_genes import (
    EnrichSummary,
    GeneEnrichmentRecord,
)
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotationAxis
from protcellar.infrastructure.ingestion.gene_enrichment_runner import GeneEnrichmentRunner
from protcellar.infrastructure.ingestion.mycobrowser_client import MycobrowserClient
from tests.fakes.fake_auth import FakeAuth

# Two Mycobrowser-style CDS features: rpoB (Information pathways) on the + strand,
# katG (Virulence...) on the - strand. Both carry Locus + coords + category. Rows
# are built tab-joined so each source line stays readable and within line length.
_GFF = "##gff-version 3\n#!genome-build ASM19595v2\n" + "\n".join(
    "\t".join(cols)
    for cols in (
        (
            "NC_000962.3",
            "Mycobrowser",
            "CDS",
            "759807",
            "763325",
            ".",
            "+",
            "0",
            "Locus=Rv0667;Name=rpoB;Functional_Category=Information pathways",
        ),
        (
            "NC_000962.3",
            "Mycobrowser",
            "CDS",
            "2153889",
            "2156111",
            ".",
            "-",
            "0",
            "Locus=Rv1908c;Name=katG;"
            "Functional_Category=Virulence%2C detoxification%2C adaptation",
        ),
    )
)

# A tiny DeJesus essentiality table (TSV): rpoB essential, katG non-essential.
_ESSENTIALITY = "\n".join(("ORF\tFinal Call", "Rv0667\tES", "Rv1908c\tNE"))


# --------------------------------------------------------------------------- #
# MycobrowserClient (httpx.MockTransport — no real network)                    #
# --------------------------------------------------------------------------- #


def _client(handler: httpx.MockTransport) -> MycobrowserClient:
    return MycobrowserClient(httpx.AsyncClient(transport=handler))


@pytest.mark.asyncio
async def test_client_fetches_plain_gff_text() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith(".gff")
        return httpx.Response(200, text=_GFF)

    client = _client(httpx.MockTransport(handle))
    async with client:
        text = await client.fetch_text("https://mycobrowser.example/x.gff")
    assert "Rv0667" in text and "Functional_Category=Information pathways" in text


@pytest.mark.asyncio
async def test_client_gunzips_when_url_ends_with_gz() -> None:
    compressed = gzip.compress(_GFF.encode("utf-8"))

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=compressed)

    client = _client(httpx.MockTransport(handle))
    async with client:
        text = await client.fetch_text("https://mycobrowser.example/x.gff.gz")
    assert "Rv1908c" in text  # transparently decompressed


@pytest.mark.asyncio
async def test_client_raises_for_status() -> None:
    client = _client(httpx.MockTransport(lambda r: httpx.Response(404, text="nope")))
    with pytest.raises(httpx.HTTPStatusError):
        async with client:
            await client.fetch_text("https://mycobrowser.example/missing.gff")


# --------------------------------------------------------------------------- #
# GeneEnrichmentRunner (fake client + fake BulkEnrichGenes)                     #
# --------------------------------------------------------------------------- #


class _FakeGffClient:
    """Returns canned text per URL; records which URLs were fetched."""

    def __init__(self, text_by_url: dict[str, str]) -> None:
        self._by_url = text_by_url
        self.fetched: list[str] = []

    async def fetch_text(self, url: str) -> str:
        self.fetched.append(url)
        return self._by_url[url]


class _CapturingBulkEnrich:
    """Stands in for BulkEnrichGenes: captures the call and returns a Result."""

    def __init__(self) -> None:
        self.organism_id: uuid.UUID | None = None
        self.records: list[GeneEnrichmentRecord] = []
        self.auth: object | None = None

    async def __call__(
        self,
        organism_id: uuid.UUID,
        records: Sequence[GeneEnrichmentRecord],
        auth: object | None = None,
    ) -> object:
        from returns.result import Success

        self.organism_id = organism_id
        self.records = list(records)
        self.auth = auth
        return Success(
            EnrichSummary(
                matched=len(self.records),
                unmatched=0,
                locations_set=len(self.records),
                annotations_written=sum(len(r.annotations) for r in self.records),
            )
        )


@pytest.mark.asyncio
async def test_runner_wires_fetch_parse_map_enrich() -> None:
    gff_url = "https://mycobrowser.example/h37rv.gff"
    client = _FakeGffClient({gff_url: _GFF})
    bulk = _CapturingBulkEnrich()
    org = uuid.uuid4()
    auth = FakeAuth(role="admin")

    runner = GeneEnrichmentRunner(bulk, client, gff_url=gff_url)  # type: ignore[arg-type]
    summary = await runner.run(org, auth=auth)

    # Client fetched exactly the GFF URL.
    assert client.fetched == [gff_url]
    # BulkEnrichGenes received both loci, with location + a CONTEXT annotation each.
    assert bulk.organism_id == org
    assert bulk.auth is auth
    by_locus = {r.locus_key: r for r in bulk.records}
    assert set(by_locus) == {"Rv0667", "Rv1908c"}
    rpob = by_locus["Rv0667"]
    assert rpob.genomic_accession == "NC_000962.3"
    assert rpob.genomic_start == 759807
    assert rpob.genomic_strand == "+"
    assert rpob.assembly == "ASM19595v2"
    assert [a.key for a in rpob.annotations] == ["functional_category"]
    # No essentiality loader -> no VULNERABILITY annotations.
    assert not any(
        a.axis == GeneAnnotationAxis.VULNERABILITY for r in bulk.records for a in r.annotations
    )
    # Summary propagates from the use case.
    assert summary.matched == 2
    assert summary.locations_set == 2


@pytest.mark.asyncio
async def test_runner_includes_essentiality_when_loader_supplied() -> None:
    gff_url = "https://mycobrowser.example/h37rv.gff"
    client = _FakeGffClient({gff_url: _GFF})
    bulk = _CapturingBulkEnrich()

    async def _load_essentiality() -> str:
        return _ESSENTIALITY

    runner = GeneEnrichmentRunner(
        bulk,  # type: ignore[arg-type]
        client,  # type: ignore[arg-type]
        gff_url=gff_url,
        essentiality_loader=_load_essentiality,
    )
    await runner.run(uuid.uuid4(), auth=FakeAuth(role="admin"))

    by_locus = {r.locus_key: r for r in bulk.records}
    rpob_vuln = [
        a for a in by_locus["Rv0667"].annotations if a.axis == GeneAnnotationAxis.VULNERABILITY
    ]
    assert [a.value for a in rpob_vuln] == ["essential"]
    assert rpob_vuln[0].dataset == "DeJesus 2017"
    katg_vuln = [
        a.value
        for a in by_locus["Rv1908c"].annotations
        if a.axis == GeneAnnotationAxis.VULNERABILITY
    ]
    assert katg_vuln == ["non-essential"]
