"""arq-backed JobEnqueuer — infrastructure implementation of the application protocol.

The enqueuer is *lazy*: it does NOT connect to Redis at construction time so
that building the DI container (and running tests) does not require a Redis
instance.  The pool is created on the first call to :meth:`enqueue_import`.
"""

from __future__ import annotations

import os
import uuid

import arq
import arq.connections


def redis_settings_from_env() -> arq.connections.RedisSettings:
    """Return RedisSettings parsed from ``$REDIS_URL`` (default: ``redis://localhost:6380``)."""
    dsn = os.environ.get("REDIS_URL", "redis://localhost:6380")
    return arq.connections.RedisSettings.from_dsn(dsn)


class ArqJobEnqueuer:
    """Enqueue import jobs via arq (implements the :class:`JobEnqueuer` protocol).

    The Redis connection pool is created lazily on the first
    :meth:`enqueue_import` call and cached for reuse.  This means constructing
    the DI container — or instantiating this class — does **not** require Redis
    to be available.
    """

    def __init__(self) -> None:
        self._pool: arq.ArqRedis | None = None

    async def _get_pool(self) -> arq.ArqRedis:
        if self._pool is None:
            self._pool = await arq.create_pool(redis_settings_from_env())
        return self._pool

    async def enqueue_import(self, import_run_id: uuid.UUID) -> None:
        """Enqueue a ``run_import`` job for the given import run ID."""
        pool = await self._get_pool()
        await pool.enqueue_job("run_import", str(import_run_id))

    async def aclose(self) -> None:
        """Close the Redis pool if it was created."""
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
