import uuid

import pytest

from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.hypomorph import Hypomorph
from protcellar.domain.target_biology.protein_activity_assay import ProteinActivityAssay
from protcellar.domain.target_biology.protein_production import ProteinProduction
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure
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
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _prov() -> Provenance:
    return Provenance(source_type=ProvenanceSourceType.INTERNAL)


async def test_hypomorph_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, gene, strain = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    record = Hypomorph.create(
        workspace_id=ws,
        gene_id=gene,
        growth_defect=True,
        growth_defect_severity="severe",
        knockdown_strain_id=strain,
        provenance=_prov(),
    )
    async with uow:
        await SQLAlchemyHypomorphRepository(uow).save(record)
        await uow.commit()
    async with uow:
        found = await SQLAlchemyHypomorphRepository(uow).find_by_gene(ws, gene)
    assert len(found) == 1
    assert found[0].growth_defect is True
    assert found[0].knockdown_strain_id == strain


async def test_resistance_mutation_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, gene, compound = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    record = ResistanceMutation.create(
        workspace_id=ws,
        gene_id=gene,
        mutation="S315T",
        compound=CompoundRef(compound_id=compound, name="isoniazid"),
        mic_shift=64.0,
        provenance=_prov(),
    )
    async with uow:
        await SQLAlchemyResistanceMutationRepository(uow).save(record)
        await uow.commit()
    async with uow:
        found = await SQLAlchemyResistanceMutationRepository(uow).find_by_gene(ws, gene)
    assert len(found) == 1
    assert found[0].mutation == "S315T"
    assert found[0].compound is not None
    assert found[0].compound.compound_id == compound
    assert found[0].compound.name == "isoniazid"


async def test_protein_production_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, protein = uuid.uuid4(), uuid.uuid4()
    record = ProteinProduction.create(
        workspace_id=ws,
        protein_id=protein,
        status="produced",
        expression_host="E. coli BL21",
        purity=95.0,
        provenance=_prov(),
    )
    async with uow:
        await SQLAlchemyProteinProductionRepository(uow).save(record)
        await uow.commit()
    async with uow:
        found = await SQLAlchemyProteinProductionRepository(uow).find_by_protein(ws, protein)
    assert len(found) == 1
    assert found[0].status == "produced"
    assert found[0].purity == 95.0


async def test_protein_activity_assay_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, protein = uuid.uuid4(), uuid.uuid4()
    record = ProteinActivityAssay.create(
        workspace_id=ws,
        protein_id=protein,
        activity_measured="ATPase",
        readout="fluorescence",
        provenance=_prov(),
    )
    async with uow:
        await SQLAlchemyProteinActivityAssayRepository(uow).save(record)
        await uow.commit()
    async with uow:
        found = await SQLAlchemyProteinActivityAssayRepository(uow).find_by_protein(ws, protein)
    assert len(found) == 1
    assert found[0].activity_measured == "ATPase"


async def test_unpublished_structure_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, protein, ligand = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    record = UnpublishedStructure.create(
        workspace_id=ws,
        protein_id=protein,
        method="cryo-EM",
        resolution=2.4,
        ligands=(CompoundRef(compound_id=ligand, name="ATP"),),
        provenance=_prov(),
    )
    async with uow:
        await SQLAlchemyUnpublishedStructureRepository(uow).save(record)
        await uow.commit()
    async with uow:
        found = await SQLAlchemyUnpublishedStructureRepository(uow).find_by_protein(ws, protein)
    assert len(found) == 1
    assert found[0].resolution == 2.4
    assert len(found[0].ligands) == 1
    assert found[0].ligands[0].compound_id == ligand
