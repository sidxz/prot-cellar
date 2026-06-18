"""Framework + cross-cutting deps and the generic use-case factory.

Everything else in the dependencies package imports :func:`_get_use_case` from here.
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import Depends, Request
from lagom import Container
from pydantic import ValidationError

from protcellar.application.shared.unit_of_work import (
    UnitOfWork,  # noqa: F401  (re-exported for compat)
)
from protcellar.infrastructure.logging import bind_user_context
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from protcellar.infrastructure.sentinel.auth import get_sentinel

__all__ = [
    "AuthDep",
    "EventDispatcherDep",
    "UoWDep",
    "_get_use_case",
    "get_auth",
    "get_container",
    "get_event_dispatcher",
    "get_uow",
]


def get_container(request: Request) -> Container:
    """Retrieve the DI container from app state."""
    return request.app.state.container  # type: ignore[no-any-return]


def get_uow(
    container: Annotated[Container, Depends(get_container)],
) -> AsyncUnitOfWork:
    """Request-scoped Unit of Work."""
    return container[AsyncUnitOfWork]


def get_event_dispatcher(
    container: Annotated[Container, Depends(get_container)],
) -> EventDispatcher:
    """Singleton event dispatcher."""
    return container[EventDispatcher]


# Sentinel auth dependency — stable wrapper so dependency_overrides work in tests.
# Lazy init: don't crash at import time if Sentinel env vars aren't set.
# Uses a reject-all stub when Sentinel is unavailable so auth is never bypassed.


async def _sentinel_not_configured() -> None:
    """Stub dependency that rejects all requests when Sentinel is not configured."""
    from fastapi import HTTPException

    raise HTTPException(
        status_code=503,
        detail="Sentinel auth not configured. Set SENTINEL_URL and SENTINEL_SERVICE_KEY.",
    )


# Sentinel is "configured" only when SENTINEL_SERVICE_KEY is explicitly set —
# the pydantic-settings default ("") is a missing-config signal, not a usable
# service key. The URL has a localhost default so dev still works; if you want
# prod fail-fast on missing URL too, set it explicitly in the deployment env.
_sentinel: object | None = None
if not os.environ.get("SENTINEL_SERVICE_KEY"):
    _sentinel_get_auth = _sentinel_not_configured
else:
    try:
        _sentinel = get_sentinel()
        _sentinel_get_auth = _sentinel.get_auth  # type: ignore[union-attr]
    except (ValueError, ValidationError):
        # Sentinel env vars malformed — fall back to a reject-all stub.
        _sentinel = None
        _sentinel_get_auth = _sentinel_not_configured


async def get_auth(
    request: Request,
    auth: Annotated[Any, Depends(_sentinel_get_auth)],
) -> Any:
    """Stable auth dependency wrapper — overridable via dependency_overrides.

    Also binds the authenticated user/workspace into the logging context and
    onto ``request.state`` so the access-log line can include them.
    """
    user_id = getattr(auth, "user_id", None)
    workspace_id = getattr(auth, "workspace_id", None)
    user_id = str(user_id) if user_id is not None else None
    workspace_id = str(workspace_id) if workspace_id is not None else None
    bind_user_context(user_id=user_id, workspace_id=workspace_id)
    request.state.user_id = user_id
    request.state.workspace_id = workspace_id
    return auth


# Convenience type aliases for route handler signatures
AuthDep = Annotated[Any, Depends(get_auth)]
UoWDep = Annotated[AsyncUnitOfWork, Depends(get_uow)]
EventDispatcherDep = Annotated[EventDispatcher, Depends(get_event_dispatcher)]


# --- Generic use-case dependency factory ---
def _get_use_case(uc_type: type) -> Any:
    def _dep(container: Annotated[Container, Depends(get_container)]) -> Any:
        return container[uc_type]

    return _dep
