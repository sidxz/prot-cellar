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
    short_names: tuple[str, ...] = ()
    ec_numbers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "recommended": self.recommended,
            "alternative": list(self.alternative),
            "submitted": list(self.submitted),
            "short_names": list(self.short_names),
            "ec_numbers": list(self.ec_numbers),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> ProteinNames:
        if not data:
            return cls()
        recommended = data.get("recommended")
        alt_raw = data.get("alternative")
        sub_raw = data.get("submitted")
        short_raw = data.get("short_names")
        ec_raw = data.get("ec_numbers")
        alt = alt_raw if isinstance(alt_raw, list) else []
        sub = sub_raw if isinstance(sub_raw, list) else []
        short = short_raw if isinstance(short_raw, list) else []
        ec = ec_raw if isinstance(ec_raw, list) else []
        return cls(
            recommended=recommended if isinstance(recommended, str) else None,
            alternative=tuple(str(x) for x in alt),
            submitted=tuple(str(x) for x in sub),
            short_names=tuple(str(x) for x in short),
            ec_numbers=tuple(str(x) for x in ec),
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


@dataclass
class ProteinComment:
    """A UniProt general-annotation comment (CC block).

    `comment_type` is the UniProt category (FUNCTION, CATALYTIC ACTIVITY,
    SUBCELLULAR LOCATION, COFACTOR, PATHWAY, SUBUNIT, DISEASE, ...). `text`
    holds free-text comments; `payload` carries the structured sub-object
    (reaction + Rhea/ChEBI, location, kinetics, disease) verbatim so the
    structured comment types are captured losslessly.
    """

    comment_type: str
    text: str | None = None
    payload: dict[str, object] | None = None
    evidence: list[dict[str, object]] | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class ProteinIsoform:
    """A UniProt ALTERNATIVE PRODUCTS isoform owned by a Protein.

    `isoform_accession` is the canonical accession with a `-N` suffix; the
    `is_displayed` isoform is the one whose sequence matches the entry's
    canonical sequence. `event` is the alternative-products event (e.g.
    "Alternative initiation", "Alternative splicing").
    """

    isoform_accession: str
    name: str | None = None
    is_displayed: bool = False
    sequence: str | None = None
    event: str | None = None
    note: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class ProteinKeyword:
    """A UniProt controlled-vocabulary keyword owned by a Protein.

    `kw_id` is the stable accession (e.g. "KW-0560"); `category` is the
    keyword category (e.g. "Molecular function", "Technical term").
    """

    kw_id: str
    name: str | None = None
    category: str | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass
class ProteinCitation:
    """A literature reference owned by a Protein (UniProt reference block).

    PubMed id / DOI are kept flat for lookup; `authors`, `positions` and
    `reference_comments` carry the list-valued sub-fields verbatim (JSONB).
    """

    citation_type: str | None = None
    title: str | None = None
    journal: str | None = None
    authors: list[str] | None = None
    publication_date: str | None = None
    pubmed_id: str | None = None
    doi: str | None = None
    reference_number: int | None = None
    positions: list[str] | None = None
    reference_comments: list[dict[str, object]] | None = None
    id: uuid.UUID = field(default_factory=uuid.uuid4)
