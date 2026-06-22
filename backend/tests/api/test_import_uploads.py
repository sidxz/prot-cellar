"""Use-case-level tests for StoreUpload / GetUpload (no HTTP route yet)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.imports.store_upload import GetUpload, StoreUpload
from protcellar.domain.shared.errors import NotFoundError
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_upload_repository import (
    SQLAlchemyImportUploadRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from returns.result import Failure, Success
from tests.fakes.fake_auth import FakeAuth

pytestmark = pytest.mark.asyncio


async def test_store_and_retrieve_upload(database_url: str, _run_migrations: None) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    admin = FakeAuth(role="admin")
    payload = b"Rv0667\tES\nRv0668\tGD\n"

    try:
        # Store via use case — let the use case manage the uow context internally
        uow = AsyncUnitOfWork(factory)
        repo = SQLAlchemyImportUploadRepository(uow)
        result = await StoreUpload(uow, repo)(
            filename="essentiality.tsv",
            content_type="text/tab-separated-values",
            data=payload,
            auth=admin,
        )

        assert isinstance(result, Success)
        upload = result.unwrap()
        assert upload.filename == "essentiality.tsv"
        upload_id = upload.id

        # Retrieve via GetUpload with a separate fresh UoW
        uow2 = AsyncUnitOfWork(factory)
        repo2 = SQLAlchemyImportUploadRepository(uow2)
        get_result = await GetUpload(uow2, repo2)(upload_id, admin)

        assert isinstance(get_result, Success)
        loaded = get_result.unwrap()
        assert loaded.filename == "essentiality.tsv"
        assert loaded.content_type == "text/tab-separated-values"
        assert loaded.data == payload

    finally:
        await engine.dispose()


async def test_get_upload_not_found(database_url: str, _run_migrations: None) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    admin = FakeAuth(role="admin")

    try:
        uow = AsyncUnitOfWork(factory)
        repo = SQLAlchemyImportUploadRepository(uow)
        result = await GetUpload(uow, repo)(uuid.uuid4(), admin)

        assert isinstance(result, Failure)
        err = result.failure()
        assert isinstance(err, NotFoundError)
        assert "ImportUpload" in err.message

    finally:
        await engine.dispose()
