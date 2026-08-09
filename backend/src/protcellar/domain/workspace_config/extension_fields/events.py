"""Domain events for the extension-field-definition registry."""

from __future__ import annotations

from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ExtensionFieldDefCreated(DomainEvent):
    kind: str
    name: str
    label: str
    field_type: str
    options: list[str] | None
    position: int
    show_in_table: bool


@dataclass(frozen=True, kw_only=True)
class ExtensionFieldDefUpdated(DomainEvent):
    kind: str
    name: str
    label: str
    field_type: str
    options: list[str] | None
    position: int
    show_in_table: bool


@dataclass(frozen=True, kw_only=True)
class ExtensionFieldDefDeleted(DomainEvent):
    """Registered by the delete use case, mirroring ``TagDeleted`` — the aggregate
    itself has no ``delete()`` method (see ``tagging/tag.py`` for the precedent).
    """

    kind: str
    name: str
