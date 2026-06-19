"""Protein Catalog DI bindings."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.protein_catalog.create_gene import CreateGene
from protcellar.application.protein_catalog.get_gene import GetGene
from protcellar.application.protein_catalog.list_genes import ListGenes
from protcellar.application.protein_catalog.update_gene import UpdateGene
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_protein_catalog(container: Container) -> None:
    def _gene_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyGeneRepository(uow), c[EventDispatcher])

        return _f

    def _gene_query(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyGeneRepository(uow))

        return _f

    container.define(CreateGene, _gene_cmd(CreateGene))
    container.define(UpdateGene, _gene_cmd(UpdateGene))
    container.define(GetGene, _gene_query(GetGene))
    container.define(ListGenes, _gene_query(ListGenes))
