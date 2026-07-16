"""Resistance Mutation aggregate — a heritable gene variant conferring drug resistance.

Catalogued with the genetics (on the gene), with a ``protein_coordinate`` cross-ref
(e.g. "L273A") so structure views can render it. ``compound`` is a portable
cross-cellar reference to the chem-cellar molecule the mutation resists.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance
from protcellar.domain.target_biology.events import (
    ResistanceMutationCreated,
    ResistanceMutationUpdated,
)


class ResistanceMutation(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        gene_id: uuid.UUID,
        mutation: str,
        provenance: Provenance,
        compound: CompoundRef | None = None,
        mic_shift: float | None = None,
        parent_strain: str | None = None,
        protein_coordinate: str | None = None,
        method: str | None = None,
        extensions: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not mutation or not mutation.strip():
            raise ValidationError("ResistanceMutation mutation must not be empty")
        self.workspace_id = workspace_id
        self.gene_id = gene_id
        self.mutation = mutation.strip()
        self.provenance = provenance
        self.compound = compound
        self.mic_shift = mic_shift
        self.parent_strain = parent_strain
        self.protein_coordinate = protein_coordinate
        self.method = method
        self.extensions = extensions if extensions is not None else {}

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        gene_id: uuid.UUID,
        mutation: str,
        provenance: Provenance,
        compound: CompoundRef | None = None,
        mic_shift: float | None = None,
        parent_strain: str | None = None,
        protein_coordinate: str | None = None,
        method: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> ResistanceMutation:
        rm = cls(
            workspace_id=workspace_id,
            gene_id=gene_id,
            mutation=mutation,
            provenance=provenance,
            compound=compound,
            mic_shift=mic_shift,
            parent_strain=parent_strain,
            protein_coordinate=protein_coordinate,
            method=method,
            extensions=extensions,
        )
        rm.register_event(
            ResistanceMutationCreated(
                aggregate_id=rm.id,
                aggregate_type="ResistanceMutation",
                workspace_id=workspace_id,
                gene_id=gene_id,
            )
        )
        return rm

    def update(self, **fields: Any) -> None:
        if "mutation" in fields:
            value = fields["mutation"]
            if not value or not str(value).strip():
                raise ValidationError("ResistanceMutation mutation must not be empty")
            self.mutation = str(value).strip()
        if "compound" in fields:
            self.compound = fields["compound"]
        if "mic_shift" in fields:
            self.mic_shift = fields["mic_shift"]
        if "parent_strain" in fields:
            self.parent_strain = fields["parent_strain"]
        if "protein_coordinate" in fields:
            self.protein_coordinate = fields["protein_coordinate"]
        if "method" in fields:
            self.method = fields["method"]
        if "provenance" in fields:
            self.provenance = fields["provenance"]
        if "extensions" in fields:
            self.extensions = dict(fields["extensions"] or {})
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            ResistanceMutationUpdated(
                aggregate_id=self.id,
                aggregate_type="ResistanceMutation",
                workspace_id=self.workspace_id,
            )
        )
