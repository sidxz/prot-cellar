"""Unit tests for BulkEnrichGenes (in-memory fake repo — no DB).

Covers the match-and-merge core: locus matching by primary_name / synonym /
source_record_id suffix, location set, dataset-scoped annotation merge, and
idempotency (re-run never duplicates).
"""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.protein_catalog.bulk_enrich_genes import (
    BulkEnrichGenes,
    GeneEnrichmentRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from tests.fakes.fake_auth import FakeAuth


class _FakeGeneRepo:
    def __init__(self, genes: list[Gene]) -> None:
        self._genes = list(genes)

    async def list_owned_by_organism(
        self,
        organism_id: uuid.UUID,
        *,
        workspace_id: uuid.UUID = SHARED_WORKSPACE_ID,
        batch: int = 1000,
    ) -> list[Gene]:
        return [g for g in self._genes if g.organism_id == organism_id]

    async def save(self, gene: Gene) -> None:
        for i, g in enumerate(self._genes):
            if g.id == gene.id:
                self._genes[i] = gene
                return
        self._genes.append(gene)

    def by_locus(self, locus: str) -> Gene:
        for g in self._genes:
            if g.primary_name == locus or locus in g.synonyms:
                return g
            if g.source_record_id and g.source_record_id.split(":")[-1] == locus:
                return g
        raise KeyError(locus)


class _FakeUoW:
    @property
    def is_active(self) -> bool:
        return True

    async def commit(self) -> list:
        return []

    async def rollback(self) -> None:
        return None

    async def __aenter__(self) -> _FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _NoopDispatcher:
    async def dispatch_all(self, events: object) -> None:
        return None


def _gene(
    primary: str,
    organism: uuid.UUID,
    synonyms: tuple[str, ...] = (),
    srid: str | None = None,
) -> Gene:
    gene = Gene.create(
        workspace_id=SHARED_WORKSPACE_ID,
        primary_name=primary,
        organism_id=organism,
        synonyms=list(synonyms),
    )
    if srid is not None:
        gene.source = "uniprot"
        gene.source_record_id = srid
    return gene


def _uc(repo: _FakeGeneRepo) -> BulkEnrichGenes:
    return BulkEnrichGenes(_FakeUoW(), repo, _NoopDispatcher())  # type: ignore[arg-type]


def _essentiality_record(locus: str) -> GeneEnrichmentRecord:
    return GeneEnrichmentRecord(
        locus_key=locus,
        genomic_accession="NC_000962.3",
        genomic_start=759807,
        genomic_end=763325,
        genomic_strand="+",
        assembly="ASM19595v2",
        annotations=(
            GeneAnnotation(
                axis=GeneAnnotationAxis.VULNERABILITY,
                key="essentiality",
                value="essential",
                dataset="DeJesus 2017",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_enrich_matches_by_name_synonym_and_srid() -> None:
    org = uuid.uuid4()
    repo = _FakeGeneRepo(
        [
            _gene("rpoB", org, synonyms=("Rv0667",)),  # match via synonym
            _gene("katG", org, synonyms=("Rv1908c",)),  # match via synonym
            _gene("Rv0001", org, srid="83332:Rv0001"),  # match via primary_name & srid suffix
        ]
    )
    uc = _uc(repo)
    recs = [
        _essentiality_record("Rv0667"),
        _essentiality_record("Rv1908c"),
        _essentiality_record("Rv0001"),
    ]
    summary = (await uc(org, recs, auth=FakeAuth(role="admin"))).unwrap()

    assert summary.matched == 3
    assert summary.unmatched == 0
    assert summary.locations_set == 3
    assert summary.annotations_written == 3
    assert summary.unmatched_loci == []

    g = repo.by_locus("Rv0667")
    assert g.genomic_accession == "NC_000962.3"
    assert g.genomic_start == 759807
    assert g.genomic_end == 763325
    assert g.genomic_strand == "+"
    assert g.assembly == "ASM19595v2"
    assert [a.value for a in g.annotations if a.key == "essentiality"] == ["essential"]


@pytest.mark.asyncio
async def test_enrich_is_idempotent_on_rerun() -> None:
    org = uuid.uuid4()
    repo = _FakeGeneRepo([_gene("rpoB", org, synonyms=("Rv0667",))])
    uc = _uc(repo)
    recs = [_essentiality_record("Rv0667")]

    (await uc(org, recs, auth=FakeAuth(role="admin"))).unwrap()
    (await uc(org, recs, auth=FakeAuth(role="admin"))).unwrap()

    g = repo.by_locus("Rv0667")
    essentiality = [a for a in g.annotations if a.key == "essentiality"]
    assert len(essentiality) == 1
    assert essentiality[0].value == "essential"


@pytest.mark.asyncio
async def test_merge_replaces_same_dataset_key_but_keeps_others() -> None:
    org = uuid.uuid4()
    existing = _gene("rpoB", org, synonyms=("Rv0667",))
    # Pre-existing annotations: one colliding (same dataset+key), one preserved.
    existing.annotations = [
        GeneAnnotation(
            axis=GeneAnnotationAxis.VULNERABILITY,
            key="essentiality",
            value="non-essential",
            dataset="DeJesus 2017",
        ),
        GeneAnnotation(
            axis=GeneAnnotationAxis.CONTEXT,
            key="functional_category",
            value="Information pathways",
            dataset="Mycobrowser",
        ),
    ]
    repo = _FakeGeneRepo([existing])
    uc = _uc(repo)

    summary = (
        await uc(org, [_essentiality_record("Rv0667")], auth=FakeAuth(role="admin"))
    ).unwrap()
    assert summary.annotations_written == 1

    g = repo.by_locus("Rv0667")
    essentiality = [a for a in g.annotations if a.key == "essentiality"]
    assert len(essentiality) == 1
    assert essentiality[0].value == "essential"  # replaced, not duplicated
    # Unrelated (different dataset+key) annotation is preserved.
    assert any(
        a.key == "functional_category" and a.dataset == "Mycobrowser" for a in g.annotations
    )


@pytest.mark.asyncio
async def test_unknown_locus_increments_unmatched() -> None:
    org = uuid.uuid4()
    repo = _FakeGeneRepo([_gene("rpoB", org, synonyms=("Rv0667",))])
    uc = _uc(repo)
    recs = [_essentiality_record("Rv0667"), _essentiality_record("Rv9999")]

    summary = (await uc(org, recs, auth=FakeAuth(role="admin"))).unwrap()
    assert summary.matched == 1
    assert summary.unmatched == 1
    assert summary.unmatched_loci == ["Rv9999"]


@pytest.mark.asyncio
async def test_match_is_case_insensitive() -> None:
    org = uuid.uuid4()
    repo = _FakeGeneRepo([_gene("rpoB", org, synonyms=("Rv0667",))])
    uc = _uc(repo)
    recs = [_essentiality_record("rv0667")]  # lowercase locus key

    summary = (await uc(org, recs, auth=FakeAuth(role="admin"))).unwrap()
    assert summary.matched == 1
    assert summary.unmatched == 0


@pytest.mark.asyncio
async def test_location_only_record_sets_location_without_annotations() -> None:
    org = uuid.uuid4()
    repo = _FakeGeneRepo([_gene("rpoB", org, synonyms=("Rv0667",))])
    uc = _uc(repo)
    recs = [
        GeneEnrichmentRecord(
            locus_key="Rv0667",
            genomic_accession="NC_000962.3",
            genomic_start=100,
            genomic_end=200,
            genomic_strand="-",
        )
    ]

    summary = (await uc(org, recs, auth=FakeAuth(role="admin"))).unwrap()
    assert summary.matched == 1
    assert summary.locations_set == 1
    assert summary.annotations_written == 0

    g = repo.by_locus("Rv0667")
    assert g.genomic_accession == "NC_000962.3"
    assert g.genomic_strand == "-"
    assert g.annotations == []
