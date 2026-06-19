"""Protein Catalog DI bindings."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.protein_catalog.create_gene import CreateGene
from protcellar.application.protein_catalog.create_protein import CreateProtein
from protcellar.application.protein_catalog.get_gene import GetGene
from protcellar.application.protein_catalog.get_protein import GetProtein
from protcellar.application.protein_catalog.list_genes import ListGenes
from protcellar.application.protein_catalog.list_proteins import ListProteins
from protcellar.application.protein_catalog.resolve_protein_id import ResolveProteinId
from protcellar.application.protein_catalog.update_gene import UpdateGene
from protcellar.application.protein_catalog.update_protein import UpdateProtein
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
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

    def _protein_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyProteinRepository(uow), c[EventDispatcher])

        return _f

    def _protein_query(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyProteinRepository(uow))

        return _f

    container.define(CreateGene, _gene_cmd(CreateGene))
    container.define(UpdateGene, _gene_cmd(UpdateGene))
    container.define(GetGene, _gene_query(GetGene))
    container.define(ListGenes, _gene_query(ListGenes))

    container.define(CreateProtein, _protein_cmd(CreateProtein))
    container.define(UpdateProtein, _protein_cmd(UpdateProtein))
    container.define(GetProtein, _protein_query(GetProtein))
    container.define(ListProteins, _protein_query(ListProteins))
    container.define(ResolveProteinId, _protein_query(ResolveProteinId))
