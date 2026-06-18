"""Generic cross-reference value object (UniProt DR-line shape)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CrossReference:
    """A reference to a record in an external database.

    `database` is a registry prefix (e.g. "uniprot", "pdb", "go").
    `accession` is the external id (e.g. "P0DTC2").
    `properties` holds secondary ids / qualifiers (e.g. PDB method+resolution).
    """

    database: str
    accession: str
    properties: dict[str, str] | None = None
    evidence: str | None = None

    def to_curie(self) -> str:
        return f"{self.database}:{self.accession}"
