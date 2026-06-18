"""Organism aggregate — a mirror of an NCBI Taxonomy node (shared reference data)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import NameClass, OrganismSource
from protcellar.domain.taxonomy.events import OrganismCreated, OrganismUpdated


@dataclass
class OrganismName:
    """A name for an organism (NCBI names.dmp row)."""

    name: str
    name_class: NameClass
    unique_name: str | None = None
    is_preferred: bool = False
    id: uuid.UUID = field(default_factory=uuid.uuid4)


class Organism(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        ncbi_tax_id: int | None = None,
        parent_id: uuid.UUID | None = None,
        rank: str,
        scientific_name: str,
        division: str | None = None,
        is_merged: bool = False,
        merged_into_id: uuid.UUID | None = None,
        is_deleted: bool = False,
        source: OrganismSource = OrganismSource.NCBI,
        source_version: str | None = None,
        source_record_id: str | None = None,
        source_record_checksum: str | None = None,
        source_release: str | None = None,
        imported_at: datetime | None = None,
        names: list[OrganismName] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not scientific_name or not scientific_name.strip():
            raise ValidationError("Organism scientific_name must not be empty")
        if not rank or not rank.strip():
            raise ValidationError("Organism rank must not be empty")
        # Reference data lives under the reserved GLOBAL workspace.
        self.workspace_id = GLOBAL_WORKSPACE_ID
        self.ncbi_tax_id = ncbi_tax_id
        self.parent_id = parent_id
        self.rank = rank.strip()
        self.scientific_name = scientific_name.strip()
        self.division = division
        self.is_merged = is_merged
        self.merged_into_id = merged_into_id
        self.is_deleted = is_deleted
        self.source = source
        self.source_version = source_version
        self.source_record_id = source_record_id
        self.source_record_checksum = source_record_checksum
        self.source_release = source_release
        self.imported_at = imported_at
        self.names: list[OrganismName] = names if names is not None else []

    @classmethod
    def create(
        cls,
        *,
        ncbi_tax_id: int | None,
        rank: str,
        scientific_name: str,
        source: OrganismSource = OrganismSource.NCBI,
        parent_id: uuid.UUID | None = None,
        division: str | None = None,
        source_version: str | None = None,
    ) -> Organism:
        org = cls(
            ncbi_tax_id=ncbi_tax_id,
            rank=rank,
            scientific_name=scientific_name,
            source=source,
            parent_id=parent_id,
            division=division,
            source_version=source_version,
        )
        # The scientific name is also a name row (NCBI models it this way).
        org.names.append(
            OrganismName(
                name=org.scientific_name,
                name_class=NameClass.SCIENTIFIC_NAME,
                is_preferred=True,
            )
        )
        org.register_event(
            OrganismCreated(
                aggregate_id=org.id,
                aggregate_type="Organism",
                workspace_id=org.workspace_id,
                scientific_name=org.scientific_name,
                ncbi_tax_id=org.ncbi_tax_id,
            )
        )
        return org

    def add_name(
        self, name: str, name_class: NameClass, *, unique_name: str | None = None
    ) -> None:
        if not name or not name.strip():
            raise ValidationError("Organism name must not be empty")
        self.names.append(
            OrganismName(name=name.strip(), name_class=name_class, unique_name=unique_name)
        )
        self._touch()

    def update(self, **fields: Any) -> None:
        if "scientific_name" in fields:
            value = fields["scientific_name"]
            if not value or not str(value).strip():
                raise ValidationError("Organism scientific_name must not be empty")
            self.scientific_name = str(value).strip()
        if "rank" in fields:
            value = fields["rank"]
            if not value or not str(value).strip():
                raise ValidationError("Organism rank must not be empty")
            self.rank = str(value).strip()
        if "parent_id" in fields:
            self.parent_id = fields["parent_id"]
        if "division" in fields:
            self.division = fields["division"]
        if "source_version" in fields:
            self.source_version = fields["source_version"]
        self._touch()

    def mark_merged_into(self, target_id: uuid.UUID) -> None:
        self.is_merged = True
        self.merged_into_id = target_id
        self._touch()

    def mark_deleted(self) -> None:
        self.is_deleted = True
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            OrganismUpdated(
                aggregate_id=self.id,
                aggregate_type="Organism",
                workspace_id=self.workspace_id,
            )
        )
