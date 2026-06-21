"""Generic, provenance-stamped gene-locus annotation value object."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protcellar.domain.shared.errors import ValidationError


class GeneAnnotationAxis(StrEnum):
    """The drug-discovery question a gene annotation speaks to.

    Universal across diseases; only the datasets that fill each axis differ.
    """

    VULNERABILITY = "vulnerability"  # does losing it hurt? (essentiality/dependency)
    SELECTIVITY = "selectivity"  # will hitting it hurt the patient? (host ortholog)
    ROBUSTNESS = "robustness"  # holds across the treated population? (conservation)
    CONTEXT = "context"  # where/when does it live? (functional category, operon)
    EXPRESSION = "expression"  # condition/stage expression


@dataclass(frozen=True, kw_only=True)
class GeneAnnotation:
    """A provenance-stamped fact about a gene locus, grouped by axis.

    Generic by design: `value` is always a display string, with `value_type`
    as a render hint, so categorical/continuous/boolean facts share one shape.
    """

    axis: GeneAnnotationAxis
    key: str
    value: str
    value_type: str = "categorical"  # "categorical" | "continuous" | "boolean" | "text"
    dataset: str | None = None
    condition: str | None = None
    evidence: str | None = None
    source: str | None = None
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not self.key or not self.key.strip():
            raise ValidationError("GeneAnnotation.key must not be empty")
        if self.value is None or str(self.value).strip() == "":
            raise ValidationError("GeneAnnotation.value must not be empty")
