"""FastAPI application factory: Sentinel auth, DI container, error handlers."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from protcellar.application.imports.job_enqueuer import JobEnqueuer
from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.di.container import create_container
from protcellar.infrastructure.logging import configure_logging
from protcellar.infrastructure.messaging.audit_event_handler import AuditEventHandler
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.sentinel.auth import (
    get_sentinel,
    register_service_actions,
)
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
        # ponytail: cross-service notification deliberately not built — no consumer yet.
        # An external publisher registers here as one more subscriber (Redis Streams on
        # valkey, not Kafka). NOTE: events also dispatch in the arq worker
        # (infrastructure/ingestion/worker.py) — register in BOTH or bulk imports won't
        # publish. See docs/superpowers/specs/2026-07-21-cross-service-event-notifications-decision.md

        # sentinel.lifespan fetches the JWKS signing key (fatal if it fails —
        # auth can't work without it). Action registration is best-effort and
        # must not block boot, so it lives here rather than in the SDK lifespan.
        async with sentinel.lifespan(app):
            await register_service_actions(sentinel)
            yield

        enq = container[JobEnqueuer]  # type: ignore[type-abstract]
        if hasattr(enq, "aclose"):
            with contextlib.suppress(Exception):
                await enq.aclose()

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

    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3001").split(",")
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

    from protcellar.interface.routes.targets import router as target_router

    app.include_router(target_router)

    from protcellar.interface.routes.imports import router as imports_router

    app.include_router(imports_router)

    from protcellar.interface.routes.plugins import router as plugins_router

    app.include_router(plugins_router)

    from protcellar.interface.routes.target_biology import router as target_biology_router

    app.include_router(target_biology_router)

    from protcellar.interface.routes.tags import assignment_router as tags_assignment_router
    from protcellar.interface.routes.tags import router as tags_router

    app.include_router(tags_router)
    app.include_router(tags_assignment_router)

    from protcellar.interface.routes.extension_fields import router as extension_fields_router

    app.include_router(extension_fields_router)

    return app


app = create_app()
