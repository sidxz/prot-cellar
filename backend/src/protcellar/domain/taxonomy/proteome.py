"""Proteome aggregate — a UniProt proteome record (shared reference data)."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.taxonomy.enums import ProteomeType
from protcellar.domain.taxonomy.events import ProteomeCreated, ProteomeUpdated

_PROTEOME_ID_RE: re.Pattern[str] = re.compile(r"^UP\d{9}$")


def _validate_proteome_id(value: str) -> str:
    if not _PROTEOME_ID_RE.match(value):
        raise ValidationError(f"Invalid UniProt proteome ID '{value}': must match ^UP\\d{{9}}$")
    return value


class Proteome(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        uniprot_proteome_id: str,
        organism_id: uuid.UUID,
        strain_id: uuid.UUID | None = None,
        proteome_type: ProteomeType,
        is_reference: bool,
        assembly_acc: str | None = None,
        source_version: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        _validate_proteome_id(uniprot_proteome_id)
        self.workspace_id = workspace_id
        self.uniprot_proteome_id = uniprot_proteome_id
        self.organism_id = organism_id
        self.strain_id = strain_id
        self.proteome_type = proteome_type
        self.is_reference = is_reference
        self.assembly_acc = assembly_acc
        self.source_version = source_version

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        uniprot_proteome_id: str,
        organism_id: uuid.UUID,
        proteome_type: ProteomeType,
        is_reference: bool,
        strain_id: uuid.UUID | None = None,
        assembly_acc: str | None = None,
        source_version: str | None = None,
    ) -> Proteome:
        proteome = cls(
            workspace_id=workspace_id,
            uniprot_proteome_id=uniprot_proteome_id,
            organism_id=organism_id,
            strain_id=strain_id,
            proteome_type=proteome_type,
            is_reference=is_reference,
            assembly_acc=assembly_acc,
            source_version=source_version,
        )
        proteome.register_event(
            ProteomeCreated(
                aggregate_id=proteome.id,
                aggregate_type="Proteome",
                workspace_id=proteome.workspace_id,
                uniprot_proteome_id=proteome.uniprot_proteome_id,
                organism_id=proteome.organism_id,
            )
        )
        return proteome

    def update(self, **fields: Any) -> None:
        if "proteome_type" in fields:
            self.proteome_type = fields["proteome_type"]
        if "is_reference" in fields:
            self.is_reference = fields["is_reference"]
        if "assembly_acc" in fields:
            self.assembly_acc = fields["assembly_acc"]
        if "source_version" in fields:
            self.source_version = fields["source_version"]
        if "strain_id" in fields:
            self.strain_id = fields["strain_id"]
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            ProteomeUpdated(
                aggregate_id=self.id,
                aggregate_type="Proteome",
                workspace_id=self.workspace_id,
            )
        )
