"""Async engine + sessionmaker factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from protcellar.infrastructure.persistence.settings import DatabaseSettings


def create_engine_and_sessionmaker(
    settings: DatabaseSettings | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    settings = settings or DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=settings.pool_pre_ping,
        echo=settings.echo,
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)
