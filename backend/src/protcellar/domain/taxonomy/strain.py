"""Strain aggregate — workspace-scoped entity anchored to a species Organism."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.taxonomy.events import StrainCreated, StrainUpdated


class Strain(AggregateRoot):
    """A microbial strain registered in a workspace.

    Workspace-scoped — carries a ``workspace_id`` and is anchored to a
    species-rank ``Organism`` via ``species_organism_id``.
    """

    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        species_organism_id: uuid.UUID,
        name: str,
        strain_organism_id: uuid.UUID | None = None,
        isolate: str | None = None,
        biosample_acc: str | None = None,
        assembly_acc: str | None = None,
        culture_collection: str | None = None,
        host_organism_id: uuid.UUID | None = None,
        metadata: dict[str, object] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not name or not name.strip():
            raise ValidationError("Strain name must not be empty")
        self.workspace_id = workspace_id
        self.species_organism_id = species_organism_id
        self.strain_organism_id = strain_organism_id
        self.name = name.strip()
        self.isolate = isolate
        self.biosample_acc = biosample_acc
        self.assembly_acc = assembly_acc
        self.culture_collection = culture_collection
        self.host_organism_id = host_organism_id
        self.metadata: dict[str, object] | None = metadata

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        species_organism_id: uuid.UUID,
        name: str,
        strain_organism_id: uuid.UUID | None = None,
        isolate: str | None = None,
        biosample_acc: str | None = None,
        assembly_acc: str | None = None,
        culture_collection: str | None = None,
        host_organism_id: uuid.UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Strain:
        strain = cls(
            workspace_id=workspace_id,
            species_organism_id=species_organism_id,
            name=name,
            strain_organism_id=strain_organism_id,
            isolate=isolate,
            biosample_acc=biosample_acc,
            assembly_acc=assembly_acc,
            culture_collection=culture_collection,
            host_organism_id=host_organism_id,
            metadata=metadata,
        )
        strain.register_event(
            StrainCreated(
                aggregate_id=strain.id,
                aggregate_type="Strain",
                workspace_id=workspace_id,
                name=strain.name,
                species_organism_id=species_organism_id,
            )
        )
        return strain

    def update(self, **fields: object) -> None:
        """Partial update — only keys present in ``fields`` are changed.

        Accepted keys: name, strain_organism_id, isolate, biosample_acc,
        assembly_acc, culture_collection, host_organism_id, metadata.
        """
        if "name" in fields:
            name = fields["name"]
            if not name or not str(name).strip():
                raise ValidationError("Strain name must not be empty")
            self.name = str(name).strip()
        if "strain_organism_id" in fields:
            self.strain_organism_id = fields["strain_organism_id"]  # type: ignore[assignment]
        if "isolate" in fields:
            self.isolate = fields["isolate"]  # type: ignore[assignment]
        if "biosample_acc" in fields:
            self.biosample_acc = fields["biosample_acc"]  # type: ignore[assignment]
        if "assembly_acc" in fields:
            self.assembly_acc = fields["assembly_acc"]  # type: ignore[assignment]
        if "culture_collection" in fields:
            self.culture_collection = fields["culture_collection"]  # type: ignore[assignment]
        if "host_organism_id" in fields:
            self.host_organism_id = fields["host_organism_id"]  # type: ignore[assignment]
        if "metadata" in fields:
            self.metadata = fields["metadata"]  # type: ignore[assignment]
        self.updated_at = datetime.now(UTC)
        self.register_event(
            StrainUpdated(
                aggregate_id=self.id,
                aggregate_type="Strain",
                workspace_id=self.workspace_id,
            )
        )
