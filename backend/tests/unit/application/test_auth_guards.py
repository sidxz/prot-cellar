import uuid

import pytest

from protcellar.application.auth import require_editor, require_same_workspace
from protcellar.domain.shared.errors import AuthorizationError, NotFoundError


class _Auth:
    def __init__(self, role: str, ws: uuid.UUID) -> None:
        self._role, self._ws = role, ws

    @property
    def user_id(self) -> uuid.UUID: return uuid.uuid4()
    @property
    def workspace_id(self) -> uuid.UUID: return self._ws
    @property
    def workspace_role(self) -> str: return self._role
    @property
    def is_admin(self) -> bool: return self._role == "admin"
    def has_role(self, minimum_role: str) -> bool:
        order = {"viewer": 0, "editor": 1, "admin": 2}
        return order[self._role] >= order[minimum_role]


def test_require_editor_blocks_viewer() -> None:
    with pytest.raises(AuthorizationError):
        require_editor(_Auth("viewer", uuid.uuid4()))


def test_require_editor_allows_none_for_workers() -> None:
    require_editor(None)  # system calls bypass


def test_require_same_workspace_raises_notfound_on_mismatch() -> None:
    with pytest.raises(NotFoundError):
        require_same_workspace(_Auth("admin", uuid.uuid4()), uuid.uuid4())
