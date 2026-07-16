"""Essentiality aggregate — a typed, provenance-stamped essentiality fact about a gene."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.events import (
    EssentialityCreated,
    EssentialityUpdated,
)


class Essentiality(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        gene_id: uuid.UUID,
        classification: EssentialityClass,
        provenance: Provenance,
        condition: str | None = None,
        method: str | None = None,
        confidence: float | None = None,
        extensions: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self._validate_confidence(confidence)
        self.workspace_id = workspace_id
        self.gene_id = gene_id
        self.classification = classification
        self.provenance = provenance
        self.condition = condition
        self.method = method
        self.confidence = confidence
        self.extensions = extensions if extensions is not None else {}

    @staticmethod
    def _validate_confidence(confidence: float | None) -> None:
        if confidence is not None and not (0.0 <= confidence <= 1.0):
            raise ValidationError("Essentiality confidence must be within [0, 1]")

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        gene_id: uuid.UUID,
        classification: EssentialityClass,
        provenance: Provenance,
        condition: str | None = None,
        method: str | None = None,
        confidence: float | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> Essentiality:
        e = cls(
            workspace_id=workspace_id,
            gene_id=gene_id,
            classification=classification,
            provenance=provenance,
            condition=condition,
            method=method,
            confidence=confidence,
            extensions=extensions,
        )
        e.register_event(
            EssentialityCreated(
                aggregate_id=e.id,
                aggregate_type="Essentiality",
                workspace_id=workspace_id,
                gene_id=gene_id,
            )
        )
        return e

    def update(self, **fields: Any) -> None:
        if "confidence" in fields:
            self._validate_confidence(fields["confidence"])
            self.confidence = fields["confidence"]
        if "classification" in fields:
            self.classification = fields["classification"]
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
            EssentialityUpdated(
                aggregate_id=self.id,
                aggregate_type="Essentiality",
                workspace_id=self.workspace_id,
            )
        )
