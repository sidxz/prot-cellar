"""Protein Catalog repository protocols."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.protein_catalog.gene import Gene


@runtime_checkable
class GeneRepository(Protocol):
    async def find_by_id_in_workspace(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> Gene | None: ...

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

    async def save(self, aggregate: Gene) -> None: ...
