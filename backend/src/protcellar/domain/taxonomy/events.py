"""Taxonomy domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class OrganismCreated(DomainEvent):
    scientific_name: str
    ncbi_tax_id: int | None


@dataclass(frozen=True, kw_only=True)
class OrganismUpdated(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class StrainCreated(DomainEvent):
    workspace_id: uuid.UUID
    name: str
    species_organism_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class StrainUpdated(DomainEvent):
    workspace_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ProteomeCreated(DomainEvent):
    uniprot_proteome_id: str
    organism_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ProteomeUpdated(DomainEvent):
    pass
