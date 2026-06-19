"""Protein Catalog domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class GeneCreated(DomainEvent):
    primary_name: str
    organism_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class GeneUpdated(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class ProteinCreated(DomainEvent):
    primary_accession: str
    organism_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class ProteinUpdated(DomainEvent):
    pass
