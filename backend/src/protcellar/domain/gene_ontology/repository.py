"""Gene Ontology repository protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from protcellar.domain.gene_ontology.go_term import GoEdge, GoTerm


@runtime_checkable
class GoOntologyRepository(Protocol):
    async def upsert_terms(self, terms: list[GoTerm], *, source_version: str) -> int: ...

    async def replace_edges(self, edges: list[GoEdge]) -> int: ...

    async def find_term(self, go_id: str) -> GoTerm | None: ...

    async def latest_source_version(self) -> str | None: ...
