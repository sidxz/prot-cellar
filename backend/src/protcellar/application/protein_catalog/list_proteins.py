"""ListProteins query — retrieve protein reference records (paginated)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_authenticated
from protcellar.application.shared.pagination import PageResult
from protcellar.application.shared.query import Query
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.gene_ontology.repository import GoOntologyRepository
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.repository import GeneRepository, ProteinRepository
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True)
class ProteinListItem:
    """A protein paired with a lightweight summary of its linked gene (if any).

    The list view shows the gene name + synonyms alongside each protein; the gene
    lives on a separate aggregate, so we batch-resolve it here rather than forcing
    the client into one request per row.
    """

    protein: Protein
    gene: Gene | None


@dataclass(frozen=True, kw_only=True)
class ListProteinsQuery(Query):
    cursor_id: uuid.UUID | None = None
    limit: int | None = None
    organism_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    is_reviewed: bool | None = None
    min_length: int | None = None
    max_length: int | None = None
    xref_db: str | None = None
    has_structure: bool | None = None
    go_term: str | None = None
    descendants: bool = False
    keyword: str | None = None
    search: str | None = None
    is_enzyme: bool | None = None


class ListProteins:
    def __init__(
        self,
        uow: UnitOfWork,
        repo: ProteinRepository,
        go_repo: GoOntologyRepository,
        gene_repo: GeneRepository,
    ) -> None:
        self._uow = uow
        self._repo = repo
        self._go_repo = go_repo
        self._gene_repo = gene_repo

    async def __call__(
        self, input: ListProteinsQuery, auth: AuthContext | None = None
    ) -> Result[PageResult[ProteinListItem], DomainError]:
        require_authenticated(auth)
        async with self._uow:
            go_terms: list[str] | None = None
            if input.go_term is not None:
                if input.descendants:
                    go_terms = sorted(
                        {input.go_term} | await self._go_repo.descendants(input.go_term)
                    )
                else:
                    go_terms = [input.go_term]
            effective_limit = input.limit
            fetch_limit = effective_limit + 1 if effective_limit is not None else None
            proteins = await self._repo.find_all(
                cursor_id=input.cursor_id,
                limit=fetch_limit,
                organism_id=input.organism_id,
                gene_id=input.gene_id,
                is_reviewed=input.is_reviewed,
                min_length=input.min_length,
                max_length=input.max_length,
                xref_db=input.xref_db,
                has_structure=input.has_structure,
                go_terms=go_terms,
                keyword=input.keyword,
                search=input.search,
                is_enzyme=input.is_enzyme,
            )

            next_cursor: str | None = None
            if effective_limit is not None and len(proteins) > effective_limit:
                proteins = proteins[:effective_limit]
                next_cursor = str(proteins[-1].id)

            total_count = await self._repo.count_all(
                organism_id=input.organism_id,
                gene_id=input.gene_id,
                is_reviewed=input.is_reviewed,
                min_length=input.min_length,
                max_length=input.max_length,
                xref_db=input.xref_db,
                has_structure=input.has_structure,
                go_terms=go_terms,
                keyword=input.keyword,
                search=input.search,
                is_enzyme=input.is_enzyme,
            )

            gene_ids = {p.gene_id for p in proteins if p.gene_id is not None}
            genes_by_id = {g.id: g for g in await self._gene_repo.find_by_ids(list(gene_ids))}
            items = [
                ProteinListItem(
                    protein=p,
                    gene=genes_by_id.get(p.gene_id) if p.gene_id is not None else None,
                )
                for p in proteins
            ]

            return Success(
                PageResult(items=items, next_cursor=next_cursor, total_count=total_count)
            )
