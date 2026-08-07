"""Read-model projections for the protein catalog.

A projection is a thin, query-shaped result — only the fields a list/dashboard shows — so a page of
rows never hydrates full aggregates (and their child tables). The write side and the detail page
still use the ``Protein`` aggregate; these exist purely for cheap reads."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.value_objects import ProteinNames


@dataclass(frozen=True, kw_only=True)
class GeneSummaryRow:
    """The gene naming fields embedded per protein list row (see GeneSummaryResponse).

    Field names mirror ``Gene`` so response builders accept either. Selecting only these
    columns skips hydrating the aggregate's JSON cross-references/annotations — and skips
    read-path tracking — for the thousands of genes a bulk protein page can reference."""

    id: uuid.UUID
    primary_name: str
    synonyms: list[str]
    ordered_locus_names: list[str]
    orf_names: list[str]


@dataclass(frozen=True, kw_only=True)
class ProteinListRow:
    """One protein as the catalog list needs it: scalar columns + a name summary + the four
    structure/chemistry flags. The flags are computed in SQL, so no cross-reference (or feature /
    comment / …) rows are loaded — those belong to the full aggregate on the detail page."""

    id: uuid.UUID
    primary_accession: str
    entry_name: str | None
    is_reviewed: bool
    protein_names: ProteinNames
    organism_id: uuid.UUID
    strain_id: uuid.UUID | None
    gene_id: uuid.UUID | None
    seq_length: int
    seq_mass: int | None
    protein_existence: ProteinExistence | None
    pdb_count: int
    has_alphafold: bool
    has_chembl: bool
    has_drugbank: bool
