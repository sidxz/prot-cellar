"""Round-trip tests for the GeneAnnotation ↔ JSON helpers."""

from __future__ import annotations

from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog._annotation_json import (
    annotations_from_json,
    annotations_to_json,
)


def test_round_trip() -> None:
    anns = [
        GeneAnnotation(
            axis=GeneAnnotationAxis.VULNERABILITY,
            key="essentiality",
            value="essential",
            dataset="DeJesus 2017",
            condition="in vitro 7H9",
            evidence="PMID:28096490",
        )
    ]
    restored = annotations_from_json(annotations_to_json(anns))
    assert restored == anns


def test_from_json_handles_none() -> None:
    assert annotations_from_json(None) == []
