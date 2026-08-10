"""Protein Activity Assay aggregate — a biochemical activity assay defined for a protein."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.provenance import Provenance
from protcellar.domain.target_biology.events import (
    ProteinActivityAssayCreated,
    ProteinActivityAssayUpdated,
)


class ProteinActivityAssay(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        protein_id: uuid.UUID,
        activity_measured: str | None = None,
        provenance: Provenance,
        readout: str | None = None,
        throughput: str | None = None,
        condition: str | None = None,
        method: str | None = None,
        extensions: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self.workspace_id = workspace_id
        self.protein_id = protein_id
        # No longer required — the source corpus this optionality exists for records no
        # short activity label at all, and one isn't invented. A supplied value is still
        # normalised: stripped, and blank/whitespace-only collapses to None so "absent"
        # has one representation, not two ("" and None).
        self.activity_measured = (activity_measured.strip() or None) if activity_measured else None
        self.provenance = provenance
        self.readout = readout
        self.throughput = throughput
        self.condition = condition
        self.method = method
        self.extensions = extensions if extensions is not None else {}

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        protein_id: uuid.UUID,
        activity_measured: str | None = None,
        provenance: Provenance,
        readout: str | None = None,
        throughput: str | None = None,
        condition: str | None = None,
        method: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> ProteinActivityAssay:
        a = cls(
            workspace_id=workspace_id,
            protein_id=protein_id,
            activity_measured=activity_measured,
            provenance=provenance,
            readout=readout,
            throughput=throughput,
            condition=condition,
            method=method,
            extensions=extensions,
        )
        a.register_event(
            ProteinActivityAssayCreated(
                aggregate_id=a.id,
                aggregate_type="ProteinActivityAssay",
                workspace_id=workspace_id,
                protein_id=protein_id,
            )
        )
        return a

    def update(self, **fields: Any) -> None:
        if "activity_measured" in fields:
            value = fields["activity_measured"]
            self.activity_measured = (str(value).strip() or None) if value else None
        if "readout" in fields:
            self.readout = fields["readout"]
        if "throughput" in fields:
            self.throughput = fields["throughput"]
        if "condition" in fields:
            self.condition = fields["condition"]
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
            ProteinActivityAssayUpdated(
                aggregate_id=self.id,
                aggregate_type="ProteinActivityAssay",
                workspace_id=self.workspace_id,
            )
        )
