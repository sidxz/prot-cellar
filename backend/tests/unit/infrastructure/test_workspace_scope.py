"""The two predicates are the security core: reads see shared, mutations do not."""

from __future__ import annotations

import uuid

from sqlalchemy.dialects import postgresql

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    EssentialityRecordModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import (
    owned_by,
    readable_by,
)


def test_shared_workspace_is_not_the_null_uuid() -> None:
    """A forgotten assignment must not silently mean 'visible to everyone'."""
    assert uuid.UUID(int=0) != SHARED_WORKSPACE_ID


def test_shared_workspace_id_is_stable() -> None:
    assert str(SHARED_WORKSPACE_ID) == "a577f0f9-b1fb-53b6-be5d-49bcb500adeb"


def test_readable_by_admits_the_caller_and_shared() -> None:
    ws = uuid.uuid4()
    # Compiled against the postgresql dialect (this service's only runtime
    # target) so the UUID literal renders dashed, matching str(uuid.UUID) —
    # the dialect-less default compiler hex-encodes it instead.
    rendered = str(
        readable_by(EssentialityRecordModel, ws).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert str(ws) in rendered
    assert str(SHARED_WORKSPACE_ID) in rendered


def test_owned_by_admits_only_the_caller() -> None:
    ws = uuid.uuid4()
    rendered = str(
        owned_by(EssentialityRecordModel, ws).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert str(ws) in rendered
    assert str(SHARED_WORKSPACE_ID) not in rendered
