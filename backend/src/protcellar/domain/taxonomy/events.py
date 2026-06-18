"""Taxonomy domain events."""

from __future__ import annotations

from dataclasses import dataclass

from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class OrganismCreated(DomainEvent):
    scientific_name: str
    ncbi_tax_id: int | None


@dataclass(frozen=True, kw_only=True)
class OrganismUpdated(DomainEvent):
    pass
