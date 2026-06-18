"""Taxonomy controlled vocabularies."""

from __future__ import annotations

from enum import StrEnum

# Common NCBI ranks — NOT exhaustive and NOT a DB enum. Unknown ranks are allowed
# (stored as-is) so GTDB's fixed 7 ranks and NCBI's long tail both fit.
KNOWN_RANKS: frozenset[str] = frozenset(
    {
        "superkingdom", "kingdom", "phylum", "class", "order", "family",
        "genus", "species", "subspecies", "strain", "varietas", "forma",
        "clade", "no rank",
    }
)


class NameClass(StrEnum):
    SCIENTIFIC_NAME = "scientific_name"
    COMMON_NAME = "common_name"
    GENBANK_COMMON_NAME = "genbank_common_name"
    SYNONYM = "synonym"
    AUTHORITY = "authority"
    EQUIVALENT_NAME = "equivalent_name"
    ACRONYM = "acronym"
    BLAST_NAME = "blast_name"
    UNIPROT_MNEMONIC = "uniprot_mnemonic"  # e.g. HUMAN, ECOLI


class OrganismSource(StrEnum):
    NCBI = "ncbi"
    GTDB = "gtdb"
    LOCAL = "local"


class ProteomeType(StrEnum):
    REFERENCE = "reference"
    REPRESENTATIVE = "representative"
    REDUNDANT = "redundant"
    EXCLUDED = "excluded"


class StrainRelationship(StrEnum):
    """How a Strain relates to its anchoring Organism nodes."""

    SPECIES_ANCHOR = "species_anchor"
