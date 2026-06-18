"""API test fixtures — test-specific FastAPI app with FakeAuth, real DB."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

# Set sentinel env before any protcellar imports — allows module-level get_sentinel() to succeed.
# Must NOT use .env files (cross-contamination between DatabaseSettings and SentinelSettings).
os.environ["SENTINEL_SERVICE_KEY"] = "test-key-for-api-tests"
os.environ["SENTINEL_URL"] = "https://sentinel.example.com"
os.environ["SENTINEL_SERVICE_NAME"] = "protcellar"
# Required since Sentinel 0.11.0 (authz mode) — get_sentinel() raises ValueError without it.
os.environ["SENTINEL_IDP_AUDIENCE"] = "test-audience.apps.googleusercontent.com"

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.di.container import create_container
from protcellar.infrastructure.messaging.audit_event_handler import AuditEventHandler
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.interface.dependencies import get_auth
from protcellar.interface.error_handlers import register_error_handlers
from tests.fakes.fake_auth import FakeAuth


def _create_test_app(database_url: str, fake_auth: FakeAuth) -> FastAPI:
    """Build a FastAPI app for testing — no Sentinel middleware, FakeAuth for routes."""
    app = FastAPI()

    # DI container pointed at test DB — _env_file=None avoids loading .env
    db_settings = DatabaseSettings(database_url=database_url, _env_file=None)  # type: ignore[call-arg]
    container = create_container(db_settings)
    app.state.container = container

    # Wire the audit handler so domain events (e.g. OrganizationCreated) are persisted.
    dispatcher = container[EventDispatcher]
    session_factory = container[async_sessionmaker]
    dispatcher.register(DomainEvent, AuditEventHandler(session_factory))

    # Error handlers (so DomainError → proper HTTP status)
    register_error_handlers(app)

    # Routes
    from protcellar.interface.routes.organisms import router as organism_router
    from protcellar.interface.routes.organizations import router as org_router
    from protcellar.interface.routes.version import router as version_router

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(version_router)
    app.include_router(org_router)
    app.include_router(organism_router)

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
