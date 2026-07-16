"""Target-biology DI bindings — read-side bundle queries."""

from __future__ import annotations

from typing import Any

from lagom import Container
from sqlalchemy.ext.asyncio import async_sessionmaker

from protcellar.application.target_biology.get_gene_target_biology import GetGeneTargetBiology
from protcellar.application.target_biology.get_protein_target_biology import (
    GetProteinTargetBiology,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.crispri_strain_repository import (  # noqa: E501
    SQLAlchemyCrispriStrainRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.hypomorph_repository import (
    SQLAlchemyHypomorphRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.protein_activity_assay_repository import (  # noqa: E501
    SQLAlchemyProteinActivityAssayRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.protein_production_repository import (  # noqa: E501
    SQLAlchemyProteinProductionRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.resistance_mutation_repository import (  # noqa: E501
    SQLAlchemyResistanceMutationRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.unpublished_structure_repository import (  # noqa: E501
    SQLAlchemyUnpublishedStructureRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.vulnerability_repository import (  # noqa: E501
    SQLAlchemyVulnerabilityRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def register_target_biology(container: Container) -> None:
    def _gene_bundle(c: Container) -> Any:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return GetGeneTargetBiology(
            uow,
            SQLAlchemyEssentialityRepository(uow),
            SQLAlchemyVulnerabilityRepository(uow),
            SQLAlchemyHypomorphRepository(uow),
            SQLAlchemyCrispriStrainRepository(uow),
            SQLAlchemyResistanceMutationRepository(uow),
        )

    def _protein_bundle(c: Container) -> Any:
        uow = AsyncUnitOfWork(c[async_sessionmaker])
        return GetProteinTargetBiology(
            uow,
            SQLAlchemyProteinProductionRepository(uow),
            SQLAlchemyProteinActivityAssayRepository(uow),
            SQLAlchemyUnpublishedStructureRepository(uow),
        )

    container.define(GetGeneTargetBiology, _gene_bundle)
    container.define(GetProteinTargetBiology, _protein_bundle)
