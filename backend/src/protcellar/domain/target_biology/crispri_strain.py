"""CRISPRi strain aggregate — a physical knockdown reagent targeting a gene."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance
from protcellar.domain.target_biology.events import (
    CrispriStrainCreated,
    CrispriStrainUpdated,
)


class CrispriStrain(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        name: str,
        target_gene_id: uuid.UUID,
        provenance: Provenance,
        extensions: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        if not name or not name.strip():
            raise ValidationError("CrispriStrain name must not be empty")
        self.workspace_id = workspace_id
        self.name = name.strip()
        self.target_gene_id = target_gene_id
        self.provenance = provenance
        self.extensions = extensions if extensions is not None else {}

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        name: str,
        target_gene_id: uuid.UUID,
        provenance: Provenance,
        extensions: dict[str, Any] | None = None,
    ) -> CrispriStrain:
        s = cls(
            workspace_id=workspace_id,
            name=name,
            target_gene_id=target_gene_id,
            provenance=provenance,
            extensions=extensions,
        )
        s.register_event(
            CrispriStrainCreated(
                aggregate_id=s.id,
                aggregate_type="CrispriStrain",
                workspace_id=workspace_id,
                target_gene_id=target_gene_id,
            )
        )
        return s

    def update(self, **fields: Any) -> None:
        if "name" in fields:
            value = fields["name"]
            if not value or not str(value).strip():
                raise ValidationError("CrispriStrain name must not be empty")
            self.name = str(value).strip()
        if "target_gene_id" in fields:
            self.target_gene_id = fields["target_gene_id"]
        if "provenance" in fields:
            self.provenance = fields["provenance"]
        if "extensions" in fields:
            self.extensions = dict(fields["extensions"] or {})
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            CrispriStrainUpdated(
                aggregate_id=self.id,
                aggregate_type="CrispriStrain",
                workspace_id=self.workspace_id,
            )
        )
