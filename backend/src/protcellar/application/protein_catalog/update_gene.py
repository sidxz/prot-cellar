"""UpdateGene command — partial update of an existing gene reference node."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from returns.result import Failure, Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.sentinel import UNSET
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.errors import DomainError, NotFoundError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


@dataclass(frozen=True, kw_only=True)
class UpdateGeneCommand(Command):
    gene_id: uuid.UUID
    primary_name: str | None = None
    synonyms: list[str] | None = None
    ncbi_gene_id: str | None | object = UNSET
    ensembl_gene_id: str | None | object = UNSET
    hgnc_id: str | None | object = UNSET


class UpdateGene:
    def __init__(
        self,
        uow: UnitOfWork,
        repo: GeneRepository,
        dispatcher: EventDispatcherProtocol,
    ) -> None:
        self._uow = uow
        self._repo = repo
        self._dispatcher = dispatcher

    async def __call__(
        self, input: UpdateGeneCommand, auth: AuthContext | None = None
    ) -> Result[Gene, DomainError]:
        require_admin(auth)

        async with self._uow:
            gene = await self._repo.find_by_id_in_workspace(GLOBAL_WORKSPACE_ID, input.gene_id)
            if gene is None:
                return Failure(NotFoundError("Gene", str(input.gene_id)))

            # Build kwargs dict — only include fields that were provided
            fields: dict[str, Any] = {}
            if input.primary_name is not None:
                fields["primary_name"] = input.primary_name
            if input.synonyms is not None:
                fields["synonyms"] = input.synonyms
            if input.ncbi_gene_id is not UNSET:
                fields["ncbi_gene_id"] = input.ncbi_gene_id
            if input.ensembl_gene_id is not UNSET:
                fields["ensembl_gene_id"] = input.ensembl_gene_id
            if input.hgnc_id is not UNSET:
                fields["hgnc_id"] = input.hgnc_id

            if fields:
                gene.update(**fields)
            await self._repo.save(gene)
            events = await self._uow.commit()

        await self._dispatcher.dispatch_all(events)
        return Success(gene)
