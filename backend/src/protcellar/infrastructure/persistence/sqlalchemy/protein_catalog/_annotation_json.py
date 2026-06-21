"""Shared JSON serialisation helpers for GeneAnnotation lists.

The ``gene_repository`` persists axis-typed annotations as a JSON array on the
``genes`` table.  Keeping the (de)serialisation here mirrors ``_xref_json`` and
keeps the repository free of mapping boilerplate.
"""

from __future__ import annotations

from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis


def annotations_to_json(annotations: list[GeneAnnotation]) -> list[dict[str, object]]:
    return [
        {
            "axis": a.axis.value,
            "key": a.key,
            "value": a.value,
            "value_type": a.value_type,
            "dataset": a.dataset,
            "condition": a.condition,
            "evidence": a.evidence,
            "source": a.source,
            "source_url": a.source_url,
        }
        for a in annotations
    ]


def annotations_from_json(data: list[dict[str, object]] | None) -> list[GeneAnnotation]:
    if not data:
        return []
    return [
        GeneAnnotation(
            axis=GeneAnnotationAxis(str(d["axis"])),
            key=str(d["key"]),
            value=str(d["value"]),
            value_type=str(d.get("value_type") or "categorical"),
            dataset=_opt(d.get("dataset")),
            condition=_opt(d.get("condition")),
            evidence=_opt(d.get("evidence")),
            source=_opt(d.get("source")),
            source_url=_opt(d.get("source_url")),
        )
        for d in data
    ]


def _opt(value: object) -> str | None:
    return str(value) if value is not None else None
