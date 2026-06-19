"""FastAPI application factory: Sentinel auth, DI container, error handlers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.di.container import create_container
from protcellar.infrastructure.logging import configure_logging
from protcellar.infrastructure.messaging.audit_event_handler import AuditEventHandler
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.sentinel.auth import get_sentinel
from protcellar.interface.error_handlers import register_error_handlers
from protcellar.interface.middleware.request_context import RequestContextMiddleware
from protcellar.version import build_info


def create_app() -> FastAPI:
    sentinel = get_sentinel()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        container = create_container()
        app.state.container = container

        # Wire append-only audit as a catch-all domain-event handler
        dispatcher = container[EventDispatcher]
        session_factory = container[async_sessionmaker]
        dispatcher.register(DomainEvent, AuditEventHandler(session_factory))

        async with sentinel.lifespan(app):
            yield

        engine = container[AsyncEngine]
        await engine.dispose()

    app = FastAPI(
        title="prot-cellar",
        version=build_info().version,
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    sentinel.protect(app, exclude_paths=["/health", "/version", "/docs", "/openapi.json"])

    import os

    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    from protcellar.interface.routes.version import router as version_router

    app.include_router(version_router)

    from protcellar.interface.routes.organizations import router as org_router

    app.include_router(org_router)

    from protcellar.interface.routes.organisms import router as organism_router

    app.include_router(organism_router)

    from protcellar.interface.routes.strains import router as strain_router

    app.include_router(strain_router)

    from protcellar.interface.routes.proteomes import router as proteome_router

    app.include_router(proteome_router)

    from protcellar.interface.routes.genes import router as gene_router

    app.include_router(gene_router)

    from protcellar.interface.routes.proteins import router as protein_router

    app.include_router(protein_router)

    return app


app = create_app()
