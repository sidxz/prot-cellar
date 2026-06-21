"""Protein Catalog repository protocols."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.protein import Protein


@runtime_checkable
class GeneRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Gene | None: ...

    async def find_by_ids(self, ids: Sequence[uuid.UUID]) -> list[Gene]: ...

    async def find_by_name(
        self, name: str, organism_id: uuid.UUID | None = None
    ) -> list[Gene]: ...

    async def find_by_ncbi_gene_id(self, ncbi_gene_id: str) -> Gene | None: ...

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
    ) -> list[Gene]: ...

    async def find_by_source_record_id(
        self, source: str, source_record_id: str
    ) -> Gene | None: ...

    async def find_genomic_neighbors(
        self,
        *,
        organism_id: uuid.UUID,
        genomic_accession: str,
        center_start: int,
        window: int,
    ) -> list[Gene]: ...

    async def save(self, aggregate: Gene) -> None: ...


@runtime_checkable
class ProteinRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Protein | None: ...

    async def find_by_accession(self, accession: str) -> Protein | None: ...

    async def find_by_entry_name(self, entry_name: str) -> Protein | None: ...

    async def find_by_source_record_id(
        self, source: str, source_record_id: str
    ) -> Protein | None: ...

    async def find_all(
        self,
        *,
        cursor_id: uuid.UUID | None = None,
        limit: int | None = None,
        organism_id: uuid.UUID | None = None,
        gene_id: uuid.UUID | None = None,
        is_reviewed: bool | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        xref_db: str | None = None,
        has_structure: bool | None = None,
        go_terms: list[str] | None = None,
        keyword: str | None = None,
    ) -> list[Protein]: ...

    async def save(self, aggregate: Protein) -> None: ...
