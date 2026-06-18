"""Taxonomy DI bindings — registers Organism and Strain use cases into Lagom."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.taxonomy.create_organism import CreateOrganism
from protcellar.application.taxonomy.create_strain import CreateStrain
from protcellar.application.taxonomy.get_organism import GetOrganism
from protcellar.application.taxonomy.get_strain import GetStrain
from protcellar.application.taxonomy.list_organisms import ListOrganisms
from protcellar.application.taxonomy.list_strains import ListStrains
from protcellar.application.taxonomy.resolve_tax_id import ResolveTaxId
from protcellar.application.taxonomy.update_organism import UpdateOrganism
from protcellar.application.taxonomy.update_strain import UpdateStrain
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.strain_repository import (
    SQLAlchemyStrainRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_taxonomy(container: Container) -> None:
    """Register Organism and Strain use cases into the Lagom container."""

    # --- Organisms (command — needs EventDispatcher) ---
    def _org_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyOrganismRepository(uow), c[EventDispatcher])

        return _f

    # --- Organisms (query — no EventDispatcher) ---
    def _org_query(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyOrganismRepository(uow))

        return _f

    container.define(CreateOrganism, _org_cmd(CreateOrganism))
    container.define(UpdateOrganism, _org_cmd(UpdateOrganism))
    container.define(GetOrganism, _org_query(GetOrganism))
    container.define(ListOrganisms, _org_query(ListOrganisms))
    container.define(ResolveTaxId, _org_query(ResolveTaxId))

    # --- Strains (command — needs EventDispatcher) ---
    def _strain_cmd(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyStrainRepository(uow), c[EventDispatcher])

        return _f

    # --- Strains (query — no EventDispatcher) ---
    def _strain_query(uc_cls: type) -> Any:
        def _f(c: Container) -> Any:
            uow = AsyncUnitOfWork(c[async_sessionmaker])
            return uc_cls(uow, SQLAlchemyStrainRepository(uow))

        return _f

    container.define(CreateStrain, _strain_cmd(CreateStrain))
    container.define(UpdateStrain, _strain_cmd(UpdateStrain))
    container.define(GetStrain, _strain_query(GetStrain))
    container.define(ListStrains, _strain_query(ListStrains))
