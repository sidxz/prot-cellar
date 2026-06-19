"""Create a gene reference record (admin/service only)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class CreateGeneCommand(Command):
    primary_name: str
    organism_id: uuid.UUID
    synonyms: list[str] = field(default_factory=list)
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    hgnc_id: str | None = None


class CreateGene:
    def __init__(
        self, uow: UnitOfWork, repo: GeneRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: CreateGeneCommand, auth: AuthContext | None = None
    ) -> Result[Gene, DomainError]:
        require_admin(auth)
        async with self._uow:
            gene = Gene.create(
                primary_name=input.primary_name,
                organism_id=input.organism_id,
                synonyms=list(input.synonyms),
                ncbi_gene_id=input.ncbi_gene_id,
                ensembl_gene_id=input.ensembl_gene_id,
                hgnc_id=input.hgnc_id,
            )
            await self._repo.save(gene)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(gene)
