"""Target domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent
from protcellar.domain.target.enums import TargetType


@dataclass(frozen=True, kw_only=True)
class TargetCreated(DomainEvent):
    workspace_id: uuid.UUID
    pref_name: str
    target_type: TargetType


@dataclass(frozen=True, kw_only=True)
class TargetUpdated(DomainEvent):
    workspace_id: uuid.UUID
