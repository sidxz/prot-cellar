from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.imports.store_upload import StoreUpload
from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.organism import Organism
from protcellar.infrastructure.ingestion import worker as worker_mod
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_upload_repository import (
    SQLAlchemyImportUploadRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from tests.fakes.fake_auth import FakeAuth

pytestmark = pytest.mark.asyncio


def _ctx(factory) -> dict:
    return {"session_factory": factory, "dispatcher": EventDispatcher()}


async def test_dejesus_plugin_run_creates_essentiality(
    database_url: str, _run_migrations: None
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    admin = FakeAuth(role="admin", workspace_id=uuid.uuid4(), user_id=uuid.uuid4())
    try:
        # Seed an organism (genes.organism_id is FK-constrained) + a gene whose
        # locus matches the TSV.
        organism = Organism.create(
            workspace_id=SHARED_WORKSPACE_ID,
            ncbi_tax_id=83332,
            rank="strain",
            scientific_name="M. tuberculosis H37Rv (test)",
        )
        org = organism.id
        gene = Gene.create(
            workspace_id=SHARED_WORKSPACE_ID, primary_name="Rv0667", organism_id=org
        )
        async with AsyncUnitOfWork(factory) as uow:
            await SQLAlchemyOrganismRepository(uow).save(organism)
            await SQLAlchemyGeneRepository(uow).save(gene)
            await uow.commit()

        # Store an already-TSV-normalized upload (StoreUpload manages its own uow).
        # parse_dejesus_essentiality always treats row 0 as a header, so a
        # single-data-row fixture needs a header line the parser recognizes
        # ("locus" / "call" are both literal aliases in _LOCUS_HEADERS/_CALL_HEADERS).
        uow = AsyncUnitOfWork(factory)
        store = StoreUpload(uow, SQLAlchemyImportUploadRepository(uow))
        upload = (
            await store(
                filename="dejesus.tsv",
                content_type="text/tab-separated-values",
                data=b"locus\tcall\nRv0667\tES\n",
                auth=admin,
            )
        ).unwrap()

        # Seed a PLUGIN run and drive the worker.
        run = ImportRun.create(
            workspace_id=admin.workspace_id,
            import_type=ImportType.PLUGIN,
            params={
                "plugin_id": "dejesus_essentiality",
                "organism_id": str(org),
                "upload": str(upload.id),
                "upload_ref": str(upload.id),
            },
            target_key=f"dejesus_essentiality:{org}:run",
            requested_by=admin.user_id,
            upload_ref=upload.id,
        )
        async with AsyncUnitOfWork(factory) as uow:
            await SQLAlchemyImportRunRepository(uow).save(run)
            await uow.commit()

        await worker_mod.run_import(_ctx(factory), str(run.id), str(run.workspace_id))

        async with AsyncUnitOfWork(factory) as uow:
            reloaded = await SQLAlchemyImportRunRepository(uow).get(run.workspace_id, run.id)
            assert reloaded.status is ImportStatus.SUCCEEDED
            assert reloaded.summary["created"] == 1

            records = await SQLAlchemyEssentialityRepository(uow).find_by_gene(
                SHARED_WORKSPACE_ID, gene.id
            )
            assert len(records) == 1
            assert records[0].provenance.generation_method.value == "imported"
            assert records[0].extensions["source_run_id"] == str(run.id)
    finally:
        await engine.dispose()
