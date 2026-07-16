"""Target-biology domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class EssentialityCreated(DomainEvent):
    workspace_id: uuid.UUID
    gene_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class EssentialityUpdated(DomainEvent):
    workspace_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class CrispriStrainCreated(DomainEvent):
    workspace_id: uuid.UUID
    target_gene_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class CrispriStrainUpdated(DomainEvent):
    workspace_id: uuid.UUID
