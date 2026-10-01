"""API test fixtures — test-specific FastAPI app with FakeAuth, real DB."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

# Set duar env before any protcellar imports — allows module-level get_duar() to succeed.
# Must NOT use .env files (cross-contamination between DatabaseSettings and DuarSettings).
os.environ["DUAR_SERVICE_KEY"] = "test-key-for-api-tests"
os.environ["DUAR_URL"] = "https://duar.example.com"
os.environ["DUAR_SERVICE_NAME"] = "protcellar"
# Required since Duar 0.11.0 (authz mode) — get_duar() raises ValueError without it.
os.environ["DUAR_IDP_AUDIENCE"] = "test-audience.apps.googleusercontent.com"

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from protcellar.application.imports.job_enqueuer import JobEnqueuer
from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.di.container import create_container
from protcellar.infrastructure.messaging.audit_event_handler import AuditEventHandler
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.interface.dependencies import get_auth
from protcellar.interface.error_handlers import register_error_handlers
from tests.fakes.fake_auth import FakeAuth


class _NoopEnqueuer:
    """No arq worker consumes the queue in tests (they drive the worker directly),
    so POST /imports must not need a live Redis."""

    async def enqueue_import(self, import_run_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        return None


def _create_test_app(database_url: str, fake_auth: FakeAuth) -> FastAPI:
    """Build a FastAPI app for testing — no Duar middleware, FakeAuth for routes."""
    app = FastAPI()

    # DI container pointed at test DB — _env_file=None avoids loading .env
    db_settings = DatabaseSettings(database_url=database_url, _env_file=None)  # type: ignore[call-arg]
    # clone(): lagom refuses to redefine a type on the container that defined it.
    container = create_container(db_settings).clone()
    container.define(JobEnqueuer, lambda c: _NoopEnqueuer())
    app.state.container = container

    # Wire the audit handler so domain events (e.g. OrganizationCreated) are persisted.
    dispatcher = container[EventDispatcher]
    session_factory = container[async_sessionmaker]
    dispatcher.register(DomainEvent, AuditEventHandler(session_factory))

    # Error handlers (so DomainError → proper HTTP status)
    register_error_handlers(app)

    # Routes
    from protcellar.interface.routes.extension_fields import router as extension_fields_router
    from protcellar.interface.routes.genes import router as gene_router
    from protcellar.interface.routes.imports import router as imports_router
    from protcellar.interface.routes.organisms import router as organism_router
    from protcellar.interface.routes.organizations import router as org_router
    from protcellar.interface.routes.plugins import router as plugins_router
    from protcellar.interface.routes.proteins import (
        router as protein_router,
    )
    from protcellar.interface.routes.proteomes import router as proteome_router
    from protcellar.interface.routes.strains import router as strain_router
    from protcellar.interface.routes.tags import assignment_router as tags_assignment_router
    from protcellar.interface.routes.tags import router as tags_router
    from protcellar.interface.routes.target_biology import router as target_biology_router
    from protcellar.interface.routes.targets import router as target_router
    from protcellar.interface.routes.version import router as version_router

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(version_router)
    app.include_router(org_router)
    app.include_router(organism_router)
    app.include_router(strain_router)
    app.include_router(proteome_router)
    app.include_router(gene_router)
    app.include_router(protein_router)
    app.include_router(target_router)
    app.include_router(imports_router)
    app.include_router(plugins_router)
    app.include_router(target_biology_router)
    app.include_router(tags_router)
    app.include_router(tags_assignment_router)
    app.include_router(extension_fields_router)

    # Override the stable auth wrapper (not the sentinel SDK directly)
    app.dependency_overrides[get_auth] = lambda: fake_auth

    return app


@pytest.fixture
def workspace_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def fake_auth(workspace_id: uuid.UUID, user_id: uuid.UUID) -> FakeAuth:
    return FakeAuth(role="admin", workspace_id=workspace_id, user_id=user_id)


@pytest.fixture
async def api_app(
    database_url: str, _run_migrations: None, fake_auth: FakeAuth
) -> AsyncIterator[FastAPI]:
    """Function-scoped test app with FakeAuth. Depends on _run_migrations from root conftest."""
    app = _create_test_app(database_url, fake_auth)
    yield app
    # Cleanup engine
    container = app.state.container
    engine = container[AsyncEngine]
    await engine.dispose()


@pytest.fixture
async def client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client for API tests (admin auth)."""
    transport = ASGITransport(app=api_app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def editor_client(
    database_url: str, _run_migrations: None, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> AsyncIterator[AsyncClient]:
    """Async HTTP client scoped to an editor role (for 403 tests)."""
    editor_auth = FakeAuth(role="editor", workspace_id=workspace_id, user_id=user_id)
    app = _create_test_app(database_url, editor_auth)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    engine = app.state.container[AsyncEngine]
    await engine.dispose()


@pytest.fixture
async def viewer_client(
    database_url: str, _run_migrations: None, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> AsyncIterator[AsyncClient]:
    """Async HTTP client scoped to a viewer role (for editor-required 403 tests)."""
    viewer_auth = FakeAuth(role="viewer", workspace_id=workspace_id, user_id=user_id)
    app = _create_test_app(database_url, viewer_auth)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    engine = app.state.container[AsyncEngine]
    await engine.dispose()


@pytest.fixture
async def other_workspace_client(
    database_url: str, _run_migrations: None
) -> AsyncIterator[AsyncClient]:
    """A second API client hitting the same DB, but under a workspace distinct
    from ``client`` — proves something is visible/invisible/mutable-or-not from
    a *different* tenant's perspective, not just the one that created it.
    Shared by every cross-tenant test (``test_tag_filter.py``,
    ``test_workspace_isolation.py`` and, per the workspace-scoping plan,
    whichever context each of Tasks 3-6 adds next).
    """
    other_auth = FakeAuth(role="admin", workspace_id=uuid.uuid4())
    app = _create_test_app(database_url, other_auth)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    engine = app.state.container[AsyncEngine]
    await engine.dispose()
