"""Target aggregate — the pharmacological entity a compound acts on (workspace-scoped).

A Target references 1..n TargetComponents, each pointing at a canonical Protein.
The cardinality of that collection must agree with `target_type` (the core invariant).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.events import TargetCreated, TargetUpdated

# target_types whose component cardinality is constrained by the invariant.
_EXACTLY_ONE = {TargetType.SINGLE_PROTEIN, TargetType.DOMAIN}
_AT_LEAST_TWO = {
    TargetType.PROTEIN_COMPLEX,
    TargetType.PROTEIN_FAMILY,
    TargetType.PROTEIN_PROTEIN_INTERACTION,
}


@dataclass
class TargetComponent:
    """A protein constituent of a Target (entity within the Target aggregate)."""

    protein_id: uuid.UUID
    relationship: ComponentRelationship
    id: uuid.UUID = field(default_factory=uuid.uuid4)


class Target(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        pref_name: str,
        target_type: TargetType,
        components: list[TargetComponent] | None = None,
        organism_id: uuid.UUID | None = None,
        chembl_id: str | None = None,
        pharmacological_class: str | None = None,
        cross_references: list[CrossReference] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not pref_name or not pref_name.strip():
            raise ValidationError("Target pref_name must not be empty")
        self.workspace_id = workspace_id
        self.pref_name = pref_name.strip()
        self.target_type = target_type
        self.components: list[TargetComponent] = components if components is not None else []
        self.organism_id = organism_id
        self.chembl_id = chembl_id
        self.pharmacological_class = pharmacological_class
        self.cross_references = cross_references if cross_references is not None else []
        self._validate_cardinality(self.target_type, len(self.components))

    @staticmethod
    def _validate_cardinality(target_type: TargetType, n_components: int) -> None:
        if target_type in _EXACTLY_ONE and n_components != 1:
            raise ValidationError(
                f"{target_type.value} target requires exactly 1 component, got {n_components}"
            )
        if target_type in _AT_LEAST_TWO and n_components < 2:
            raise ValidationError(
                f"{target_type.value} target requires at least 2 components, got {n_components}"
            )

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        pref_name: str,
        target_type: TargetType,
        components: list[TargetComponent] | None = None,
        organism_id: uuid.UUID | None = None,
        chembl_id: str | None = None,
        pharmacological_class: str | None = None,
        cross_references: list[CrossReference] | None = None,
    ) -> Target:
        target = cls(
            workspace_id=workspace_id,
            pref_name=pref_name,
            target_type=target_type,
            components=components,
            organism_id=organism_id,
            chembl_id=chembl_id,
            pharmacological_class=pharmacological_class,
            cross_references=cross_references,
        )
        target.register_event(
            TargetCreated(
                aggregate_id=target.id,
                aggregate_type="Target",
                workspace_id=workspace_id,
                pref_name=target.pref_name,
                target_type=target.target_type,
            )
        )
        return target

    def set_components(self, components: list[TargetComponent]) -> None:
        """Replace the component collection, re-validating the cardinality invariant first."""
        self._validate_cardinality(self.target_type, len(components))
        self.components = list(components)
        self._touch()

    def update(self, **fields: Any) -> None:
        """Partial update. Accepted keys: pref_name, target_type, components,
        organism_id, chembl_id, pharmacological_class, cross_references.

        If target_type and/or components change, the cardinality invariant is
        re-validated against the resulting combination before it is committed.
        """
        new_type = fields.get("target_type", self.target_type)
        new_components = (
            list(fields["components"]) if "components" in fields else list(self.components)
        )
        # Validate the prospective combination before mutating any state.
        self._validate_cardinality(new_type, len(new_components))

        if "pref_name" in fields:
            value = fields["pref_name"]
            if not value or not str(value).strip():
                raise ValidationError("Target pref_name must not be empty")
            self.pref_name = str(value).strip()
        if "target_type" in fields:
            self.target_type = new_type
        if "components" in fields:
            self.components = new_components
        if "organism_id" in fields:
            self.organism_id = fields["organism_id"]
        if "chembl_id" in fields:
            self.chembl_id = fields["chembl_id"]
        if "pharmacological_class" in fields:
            self.pharmacological_class = fields["pharmacological_class"]
        if "cross_references" in fields:
            self.cross_references = list(fields["cross_references"] or [])
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            TargetUpdated(
                aggregate_id=self.id,
                aggregate_type="Target",
                workspace_id=self.workspace_id,
            )
        )
