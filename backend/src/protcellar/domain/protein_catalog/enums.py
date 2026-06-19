"""Protein Catalog controlled vocabularies."""

from __future__ import annotations

from enum import StrEnum

# UniProt protein-existence (PE) levels 1-5.
_PE_LEVELS: dict[str, int] = {
    "evidence_at_protein_level": 1,
    "evidence_at_transcript_level": 2,
    "inferred_from_homology": 3,
    "predicted": 4,
    "uncertain": 5,
}


class ProteinExistence(StrEnum):
    PROTEIN_LEVEL = "evidence_at_protein_level"
    TRANSCRIPT_LEVEL = "evidence_at_transcript_level"
    HOMOLOGY = "inferred_from_homology"
    PREDICTED = "predicted"
    UNCERTAIN = "uncertain"

    @property
    def level(self) -> int:
        return _PE_LEVELS[self.value]

    @classmethod
    def from_level(cls, level: int) -> ProteinExistence:
        for member in cls:
            if member.level == level:
                return member
        raise ValueError(f"Unknown protein-existence level: {level}")
