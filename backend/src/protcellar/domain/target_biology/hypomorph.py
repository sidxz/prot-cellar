"""Hypomorph aggregate — a knockdown-phenotype fact about a gene."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance
from protcellar.domain.target_biology.events import HypomorphCreated, HypomorphUpdated


class Hypomorph(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        gene_id: uuid.UUID,
        growth_defect: bool,
        provenance: Provenance,
        knockdown_strain_id: uuid.UUID | None = None,
        growth_defect_severity: str | None = None,
        condition: str | None = None,
        method: str | None = None,
        extensions: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self._validate(growth_defect, growth_defect_severity)
        self.workspace_id = workspace_id
        self.gene_id = gene_id
        self.growth_defect = growth_defect
        self.provenance = provenance
        self.knockdown_strain_id = knockdown_strain_id
        self.growth_defect_severity = growth_defect_severity
        self.condition = condition
        self.method = method
        self.extensions = extensions if extensions is not None else {}

    @staticmethod
    def _validate(growth_defect: bool, severity: str | None) -> None:
        if growth_defect is None:
            raise ValidationError("Hypomorph growth_defect must not be null")
        if severity is not None and not growth_defect:
            raise ValidationError("Hypomorph growth_defect_severity requires growth_defect=True")

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        gene_id: uuid.UUID,
        growth_defect: bool,
        provenance: Provenance,
        knockdown_strain_id: uuid.UUID | None = None,
        growth_defect_severity: str | None = None,
        condition: str | None = None,
        method: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> Hypomorph:
        h = cls(
            workspace_id=workspace_id,
            gene_id=gene_id,
            growth_defect=growth_defect,
            provenance=provenance,
            knockdown_strain_id=knockdown_strain_id,
            growth_defect_severity=growth_defect_severity,
            condition=condition,
            method=method,
            extensions=extensions,
        )
        h.register_event(
            HypomorphCreated(
                aggregate_id=h.id,
                aggregate_type="Hypomorph",
                workspace_id=workspace_id,
                gene_id=gene_id,
            )
        )
        return h

    def update(self, **fields: Any) -> None:
        new_defect = fields.get("growth_defect", self.growth_defect)
        new_severity = fields.get("growth_defect_severity", self.growth_defect_severity)
        self._validate(new_defect, new_severity)
        if "growth_defect" in fields:
            self.growth_defect = new_defect
        if "growth_defect_severity" in fields:
            self.growth_defect_severity = new_severity
        if "knockdown_strain_id" in fields:
            self.knockdown_strain_id = fields["knockdown_strain_id"]
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
            HypomorphUpdated(
                aggregate_id=self.id,
                aggregate_type="Hypomorph",
                workspace_id=self.workspace_id,
            )
        )
