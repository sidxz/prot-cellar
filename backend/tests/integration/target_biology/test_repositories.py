import uuid

import pytest

from protcellar.domain.shared.provenance import Citation, Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.vulnerability import Vulnerability
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.crispri_strain_repository import (  # noqa: E501
    SQLAlchemyCrispriStrainRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.vulnerability_repository import (  # noqa: E501
    SQLAlchemyVulnerabilityRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

# The testcontainer engine/session_factory fixtures are session-scoped, so their
# asyncpg pool binds to one event loop; run these tests on a shared session loop
# (the default function-scoped loop would close between tests -> "Event loop is closed").
pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_essentiality_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, gene = uuid.uuid4(), uuid.uuid4()
    prov = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        citations=(Citation(pmid="28096490", label="DeJesus 2017"),),
    )
    record = Essentiality.create(
        workspace_id=ws,
        gene_id=gene,
        classification=EssentialityClass.ESSENTIAL,
        condition="in vitro 7H9",
        method="TnSeq",
        provenance=prov,
        extensions={"raw_call": "essential"},
    )
    async with uow:
        await SQLAlchemyEssentialityRepository(uow).save(record)
        await uow.commit()
    async with uow:
        found = await SQLAlchemyEssentialityRepository(uow).find_by_gene(ws, gene)
    assert len(found) == 1
    assert found[0].classification is EssentialityClass.ESSENTIAL
    assert found[0].provenance.citations[0].pmid == "28096490"
    assert found[0].extensions == {"raw_call": "essential"}


async def test_crispri_strain_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, gene = uuid.uuid4(), uuid.uuid4()
    strain = CrispriStrain.create(
        workspace_id=ws,
        name="sgRNA-rpoB-1",
        target_gene_id=gene,
        provenance=Provenance(source_type=ProvenanceSourceType.INTERNAL),
    )
    async with uow:
        await SQLAlchemyCrispriStrainRepository(uow).save(strain)
        await uow.commit()
    async with uow:
        found = await SQLAlchemyCrispriStrainRepository(uow).find_owned(ws, strain.id)
    assert found is not None and found.name == "sgRNA-rpoB-1"


async def test_vulnerability_round_trip(uow: AsyncUnitOfWork) -> None:
    ws, gene = uuid.uuid4(), uuid.uuid4()
    record = Vulnerability.create(
        workspace_id=ws,
        gene_id=gene,
        method="CRISPRi",
        vulnerability_score=0.82,
        confidence=0.9,
        provenance=Provenance(
            source_type=ProvenanceSourceType.PUBLISHED,
            citations=(Citation(doi="10.1016/j.cell.2021.02.010", label="Bosch 2021"),),
        ),
        extensions={"vi_index": -3.1, "bin": "high"},
    )
    async with uow:
        await SQLAlchemyVulnerabilityRepository(uow).save(record)
        await uow.commit()
    async with uow:
        found = await SQLAlchemyVulnerabilityRepository(uow).find_by_gene(ws, gene)
    assert len(found) == 1
    assert found[0].vulnerability_score == 0.82
    assert found[0].extensions == {"vi_index": -3.1, "bin": "high"}
    assert found[0].provenance.citations[0].doi == "10.1016/j.cell.2021.02.010"
