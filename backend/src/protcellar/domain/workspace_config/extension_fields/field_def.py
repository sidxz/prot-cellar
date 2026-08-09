"""ExtensionFieldDef aggregate — a workspace's declaration of one extra field on
one target-biology record kind.

Field types mirror this service's own descriptor vocabulary for core fields:
STRING, TEXT, NUMBER, INTEGER, BOOLEAN, DATE, ENUM. No ``list``, ``reference`` or
``object`` — those exist for core value objects and have no meaning inside a
free-form JSONB bag.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.workspace_config.extension_fields.events import (
    ExtensionFieldDefCreated,
    ExtensionFieldDefUpdated,
)

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ExtensionFieldType(StrEnum):
    STRING = "string"
    TEXT = "text"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    ENUM = "enum"


def _validate_shape(name: str, field_type: ExtensionFieldType, options: list[str] | None) -> None:
    """Shared by ``create`` and ``update`` — ``name`` never changes but is cheap
    to re-check, so one validator covers both call sites.
    """
    if not _NAME_RE.match(name):
        raise ValidationError(
            f"Extension field name {name!r} must match ^[a-z][a-z0-9_]*$ — it is "
            "a JSONB key, a column header, and part of a URL"
        )
    if field_type is ExtensionFieldType.ENUM:
        if not options:
            raise ValidationError("An enum extension field requires non-empty options")
    elif options is not None:
        raise ValidationError(f"A {field_type.value} extension field must not carry options")


class ExtensionFieldDef(AggregateRoot):
    """A workspace's declaration of one extra field on one target-biology record kind.

    ``name`` is the key inside that kind's ``extensions`` JSONB bag. It is
    immutable once created — renaming it would orphan every stored value — so it
    is exposed as a read-only property backed by a private attribute; assigning
    to it raises ``AttributeError``. ``kind`` is immutable for the same reason
    ``name`` is: both are part of the ``(workspace_id, kind, name)`` identity, and
    neither ``create`` nor ``update`` offers a way to change either one.
    """

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        kind: str,
        name: str,
        label: str,
        field_type: ExtensionFieldType,
        options: list[str] | None,
        position: int,
        show_in_table: bool,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self.workspace_id = workspace_id
        self._kind = kind
        self._name = name
        self.label = label
        self.field_type = field_type
        self.options = options
        self.position = position
        self.show_in_table = show_in_table

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def name(self) -> str:
        return self._name

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        kind: str,
        name: str,
        label: str,
        field_type: ExtensionFieldType,
        options: list[str] | None,
        position: int,
        show_in_table: bool,
    ) -> ExtensionFieldDef:
        _validate_shape(name, field_type, options)
        field_def = cls(
            workspace_id=workspace_id,
            kind=kind,
            name=name,
            label=label,
            field_type=field_type,
            options=options,
            position=position,
            show_in_table=show_in_table,
        )
        field_def.register_event(
            ExtensionFieldDefCreated(
                aggregate_id=field_def.id,
                aggregate_type="ExtensionFieldDef",
                workspace_id=workspace_id,
                kind=kind,
                name=name,
                label=label,
                field_type=field_type.value,
                options=options,
                position=position,
                show_in_table=show_in_table,
            )
        )
        return field_def

    def update(
        self,
        *,
        label: str,
        field_type: ExtensionFieldType,
        options: list[str] | None,
        position: int,
        show_in_table: bool,
    ) -> None:
        """Change label and shape. ``name`` and ``kind`` are not parameters here —
        there is no way to reach them through this method.
        """
        _validate_shape(self._name, field_type, options)
        self.label = label
        self.field_type = field_type
        self.options = options
        self.position = position
        self.show_in_table = show_in_table
        self.updated_at = datetime.now(UTC)
        self.register_event(
            ExtensionFieldDefUpdated(
                aggregate_id=self.id,
                aggregate_type="ExtensionFieldDef",
                workspace_id=self.workspace_id,
                kind=self.kind,
                name=self._name,
                label=label,
                field_type=field_type.value,
                options=options,
                position=position,
                show_in_table=show_in_table,
            )
        )
