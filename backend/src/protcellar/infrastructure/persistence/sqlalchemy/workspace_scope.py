"""The two workspace predicates. Reads and mutations use different ones.

Keeping these apart is the security core of the tenancy model. `readable_by`
admits shared reference data so every tenant can see it; `owned_by` does not, so
no tenant can mutate reference data for the others. Collapsing them into one
predicate would hand every workspace admin write access to every other tenant's
reference data — Duar exposes only per-workspace roles, so there is no
realm-admin concept that could make that safe.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.sql.elements import ColumnElement

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID


def readable_by(model: Any, workspace_id: uuid.UUID) -> ColumnElement[bool]:
    """Rows this workspace may read: its own, plus shared reference data."""
    predicate: ColumnElement[bool] = model.workspace_id.in_((workspace_id, SHARED_WORKSPACE_ID))
    return predicate


def owned_by(model: Any, workspace_id: uuid.UUID) -> ColumnElement[bool]:
    """Rows this workspace may mutate: its own only.

    Shared rows are excluded on purpose — reference data is import-managed.
    """
    predicate: ColumnElement[bool] = model.workspace_id == workspace_id
    return predicate
