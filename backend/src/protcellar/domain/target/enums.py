"""Target controlled vocabularies (ChEMBL target-type subset)."""

from __future__ import annotations

from enum import StrEnum


class TargetType(StrEnum):
    SINGLE_PROTEIN = "single_protein"
    PROTEIN_COMPLEX = "protein_complex"
    PROTEIN_FAMILY = "protein_family"
    PROTEIN_PROTEIN_INTERACTION = "protein_protein_interaction"
    NUCLEIC_ACID = "nucleic_acid"
    ORGANISM = "organism"
    CELL_LINE = "cell_line"
    TISSUE = "tissue"
    UNKNOWN = "unknown"


class ComponentRelationship(StrEnum):
    SINGLE_PROTEIN = "single_protein"
    PROTEIN_SUBUNIT = "protein_subunit"
    FAMILY_MEMBER = "family_member"
    INTERACTING_PROTEIN = "interacting_protein"
