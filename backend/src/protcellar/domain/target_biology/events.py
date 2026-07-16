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


@dataclass(frozen=True, kw_only=True)
class VulnerabilityCreated(DomainEvent):
    workspace_id: uuid.UUID
    gene_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class VulnerabilityUpdated(DomainEvent):
    workspace_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class HypomorphCreated(DomainEvent):
    workspace_id: uuid.UUID
    gene_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class HypomorphUpdated(DomainEvent):
    workspace_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ResistanceMutationCreated(DomainEvent):
    workspace_id: uuid.UUID
    gene_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ResistanceMutationUpdated(DomainEvent):
    workspace_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ProteinProductionCreated(DomainEvent):
    workspace_id: uuid.UUID
    protein_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ProteinProductionUpdated(DomainEvent):
    workspace_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ProteinActivityAssayCreated(DomainEvent):
    workspace_id: uuid.UUID
    protein_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ProteinActivityAssayUpdated(DomainEvent):
    workspace_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class UnpublishedStructureCreated(DomainEvent):
    workspace_id: uuid.UUID
    protein_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class UnpublishedStructureUpdated(DomainEvent):
    workspace_id: uuid.UUID
