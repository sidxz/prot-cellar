"""Application-layer auth context protocol and guards."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from protcellar.domain.shared.errors import AuthorizationError, NotFoundError


@runtime_checkable
class AuthContext(Protocol):
    """Auth context available to use cases. Satisfied by Sentinel's RequestAuth."""

    @property
    def user_id(self) -> uuid.UUID: ...
    @property
    def workspace_id(self) -> uuid.UUID: ...
    @property
    def workspace_role(self) -> str: ...
    @property
    def is_admin(self) -> bool: ...
    def has_role(self, minimum_role: str) -> bool: ...


def require_workspace_role(auth: AuthContext | None, minimum_role: str) -> None:
    if auth is None:
        return
    if not auth.has_role(minimum_role):
        raise AuthorizationError(
            f"Requires at least '{minimum_role}' role",
            detail=f"Current role: '{auth.workspace_role}'",
        )


def require_editor(auth: AuthContext | None) -> None:
    require_workspace_role(auth, "editor")


def require_admin(auth: AuthContext | None) -> None:
    require_workspace_role(auth, "admin")


def require_authenticated(auth: AuthContext | None) -> None:
    if auth is None:
        raise AuthorizationError("Authentication required")


def require_same_workspace(auth: AuthContext | None, workspace_id: uuid.UUID | None) -> None:
    if auth is None:
        return
    if workspace_id is None:
        raise AuthorizationError("workspace_id must not be None")
    if auth.workspace_id != workspace_id:
        raise NotFoundError("Entity")


def require_same_user(auth: AuthContext | None, user_id: uuid.UUID) -> None:
    if auth is None:
        return
    if auth.user_id != user_id:
        raise AuthorizationError("Cannot act on another user's personal data")
