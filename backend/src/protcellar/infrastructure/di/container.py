"""Lagom composition root — wires foundation dependencies.

Context-specific use-case bindings are registered by
``interface/dependencies/_*.py`` modules (Task 10).

Usage::

    container = create_container()
    engine = container[AsyncEngine]
"""

from __future__ import annotations

from lagom import Container, Singleton
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.database import create_engine_and_sessionmaker
from protcellar.infrastructure.persistence.settings import DatabaseSettings


def create_container(db_settings: DatabaseSettings | None = None) -> Container:
    """Build and return the DI container with foundation singletons.

    The ``AsyncEngine`` and ``async_sessionmaker`` are constructed lazily on
    first resolution so that merely importing this module — or calling
    ``create_container()`` — does NOT require ``DATABASE_URL`` to be set in the
    environment. The engine is built only when the container is first asked for
    ``AsyncEngine`` or ``async_sessionmaker``.
    """
    container = Container()

    # --- DatabaseSettings ---
    # Capture the caller-supplied settings (or defer to env-defaults at
    # resolution time). We store the resolved settings in a closure so both
    # engine and session_factory share the same instance.
    _db_settings: DatabaseSettings | None = db_settings

    def _get_db_settings() -> DatabaseSettings:
        nonlocal _db_settings
        if _db_settings is None:
            _db_settings = DatabaseSettings()  # type: ignore[call-arg]
        return _db_settings

    container.define(DatabaseSettings, Singleton(_get_db_settings))

    # --- Engine + session factory (lazily constructed) ---
    # We use a shared closure variable so both bindings call
    # create_engine_and_sessionmaker exactly once.
    _engine_and_factory: tuple[AsyncEngine, async_sessionmaker[AsyncSession]] | None = None

    def _build_engine_and_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
        nonlocal _engine_and_factory
        if _engine_and_factory is None:
            settings = _get_db_settings()
            _engine_and_factory = create_engine_and_sessionmaker(settings)
        return _engine_and_factory

    container.define(AsyncEngine, Singleton(lambda: _build_engine_and_factory()[0]))
    container.define(async_sessionmaker, Singleton(lambda: _build_engine_and_factory()[1]))

    # --- Event Dispatcher ---
    container.define(EventDispatcher, Singleton(EventDispatcher))

    # --- Identifier Registry ---
    container.define(IdentifierRegistry, Singleton(IdentifierRegistry))

    return container
