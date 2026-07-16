import uuid

from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.scripts.backfill_essentiality import (
    build_essentiality,
    is_essentiality_annotation,
)


def _ann(value: str) -> GeneAnnotation:
    return GeneAnnotation(
        axis=GeneAnnotationAxis.VULNERABILITY,
        key="essentiality",
        value=value,
        dataset="DeJesus 2017",
        condition="in vitro 7H9",
        evidence="PMID:28096490",
    )


def test_is_essentiality_annotation() -> None:
    assert is_essentiality_annotation(_ann("essential"))
    assert not is_essentiality_annotation(
        GeneAnnotation(axis=GeneAnnotationAxis.CONTEXT, key="functional_category", value="x")
    )


def test_build_essentiality_maps_call_and_provenance() -> None:
    gene = uuid.uuid4()
    e = build_essentiality(gene, _ann("growth-defect"))
    assert e.gene_id == gene
    assert e.classification is EssentialityClass.GROWTH_DEFECT
    assert e.condition == "in vitro 7H9"
    assert e.method == "TnSeq"
    assert e.provenance.citations[0].pmid == "28096490"
    assert e.extensions["raw_call"] == "growth-defect"


def test_build_essentiality_unknown_call_is_uncertain() -> None:
    e = build_essentiality(uuid.uuid4(), _ann("weird-value"))
    assert e.classification is EssentialityClass.UNCERTAIN
    assert e.extensions["raw_call"] == "weird-value"
