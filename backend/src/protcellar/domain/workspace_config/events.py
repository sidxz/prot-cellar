"""Domain events for workspace configuration context."""

from __future__ import annotations

from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent
from protcellar.domain.workspace_config.enums import OrganizationType


@dataclass(frozen=True, kw_only=True)
class OrganizationCreated(DomainEvent):
    name: str
    org_type: OrganizationType


@dataclass(frozen=True, kw_only=True)
class OrganizationUpdated(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class OrganizationDeactivated(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class OrganizationActivated(DomainEvent):
    pass
