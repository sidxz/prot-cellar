"""Service-level admin auth context for background workers and CLI scripts.

This satisfies the :class:`~protcellar.application.auth.AuthContext` Protocol and
grants full admin permissions under the global workspace.  It is intentionally
kept in the ``application`` layer so that infrastructure workers (e.g. the arq
worker) can import it without creating a reverse-layer dependency into
``scripts``.
"""

from __future__ import annotations

import uuid

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID

_ROLE_HIERARCHY: dict[str, int] = {"viewer": 0, "editor": 1, "admin": 2, "owner": 3}


class ServiceAuth:
    """Admin auth context for the import service (satisfies ``AuthContext``)."""

    workspace_role = "admin"

    @property
    def user_id(self) -> uuid.UUID:
        return SHARED_WORKSPACE_ID

    @property
    def workspace_id(self) -> uuid.UUID:
        return SHARED_WORKSPACE_ID

    @property
    def is_admin(self) -> bool:
        return True

    def has_role(self, minimum_role: str) -> bool:
        return _ROLE_HIERARCHY.get(self.workspace_role, -1) >= _ROLE_HIERARCHY.get(
            minimum_role, 99
        )
