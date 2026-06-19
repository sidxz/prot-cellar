"""Protein Catalog value objects."""

from __future__ import annotations

from dataclasses import dataclass


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
        alt = data.get("alternative") or []
        sub = data.get("submitted") or []
        recommended = data.get("recommended")
        return cls(
            recommended=recommended if isinstance(recommended, str) else None,
            alternative=tuple(str(x) for x in alt),  # type: ignore[attr-defined]
            submitted=tuple(str(x) for x in sub),  # type: ignore[attr-defined]
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
