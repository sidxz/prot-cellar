"""Protein Catalog value objects."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class ProteinNames:
    """UniProt protein-name block: recommended / alternative / submitted names."""

    recommended: str | None = None
    alternative: tuple[str, ...] = ()
    submitted: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "recommended": self.recommended,
            "alternative": list(self.alternative),
            "submitted": list(self.submitted),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> ProteinNames:
        if not data:
            return cls()
        recommended = data.get("recommended")
        alt_raw = data.get("alternative")
        sub_raw = data.get("submitted")
        alt = alt_raw if isinstance(alt_raw, list) else []
        sub = sub_raw if isinstance(sub_raw, list) else []
        return cls(
            recommended=recommended if isinstance(recommended, str) else None,
            alternative=tuple(str(x) for x in alt),
            submitted=tuple(str(x) for x in sub),
        )

    @property
    def display_name(self) -> str | None:
        if self.recommended:
            return self.recommended
        if self.submitted:
            return self.submitted[0]
        if self.alternative:
            return self.alternative[0]
        return None


@dataclass
class ProteinFeature:
    """A UniProt sequence feature (FT line) — a positional annotation on the sequence.

    `feature_type` is the UniProt category (e.g. "Active site", "Binding site",
    "Domain", "Transmembrane"). `start`/`end` are 1-based residue positions.
    `ligand`/`evidence` carry the structured sub-objects (binding ligand, ECO
    evidence) verbatim so nothing in the UniProt entry is dropped.
    """

    feature_type: str
    start: int | None = None
    end: int | None = None
    start_modifier: str | None = None
    end_modifier: str | None = None
    description: str | None = None
    feature_id: str | None = None
    ligand: dict[str, object] | None = None
    alternative_sequence: str | None = None
    evidence: list[dict[str, object]] | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
