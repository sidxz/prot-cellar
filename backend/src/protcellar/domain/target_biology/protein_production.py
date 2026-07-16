"""Protein Production aggregate — a recombinant-expression/purification record for a protein."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance
from protcellar.domain.target_biology.events import (
    ProteinProductionCreated,
    ProteinProductionUpdated,
)


class ProteinProduction(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        protein_id: uuid.UUID,
        status: str,
        provenance: Provenance,
        expression_host: str | None = None,
        purity: float | None = None,
        condition: str | None = None,
        method: str | None = None,
        extensions: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not status or not status.strip():
            raise ValidationError("ProteinProduction status must not be empty")
        self.workspace_id = workspace_id
        self.protein_id = protein_id
        self.status = status.strip()
        self.provenance = provenance
        self.expression_host = expression_host
        self.purity = purity
        self.condition = condition
        self.method = method
        self.extensions = extensions if extensions is not None else {}

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        protein_id: uuid.UUID,
        status: str,
        provenance: Provenance,
        expression_host: str | None = None,
        purity: float | None = None,
        condition: str | None = None,
        method: str | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> ProteinProduction:
        p = cls(
            workspace_id=workspace_id,
            protein_id=protein_id,
            status=status,
            provenance=provenance,
            expression_host=expression_host,
            purity=purity,
            condition=condition,
            method=method,
            extensions=extensions,
        )
        p.register_event(
            ProteinProductionCreated(
                aggregate_id=p.id,
                aggregate_type="ProteinProduction",
                workspace_id=workspace_id,
                protein_id=protein_id,
            )
        )
        return p

    def update(self, **fields: Any) -> None:
        if "status" in fields:
            value = fields["status"]
            if not value or not str(value).strip():
                raise ValidationError("ProteinProduction status must not be empty")
            self.status = str(value).strip()
        if "expression_host" in fields:
            self.expression_host = fields["expression_host"]
        if "purity" in fields:
            self.purity = fields["purity"]
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
            ProteinProductionUpdated(
                aggregate_id=self.id,
                aggregate_type="ProteinProduction",
                workspace_id=self.workspace_id,
            )
        )
