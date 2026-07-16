"""Unpublished Structure aggregate — an internal/unpublished structural model of a protein.

``ligands`` is a tuple of portable cross-cellar references to chem-cellar molecules
bound in the structure (no FK; daikon's link map resolves them).
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
    UnpublishedStructureCreated,
    UnpublishedStructureUpdated,
)


class UnpublishedStructure(AggregateRoot):
    def __init__(
        self,
        *,
        id: uuid.UUID | None = None,
        workspace_id: uuid.UUID,
        protein_id: uuid.UUID,
        provenance: Provenance,
        method: str | None = None,
        resolution: float | None = None,
        ligands: tuple[CompoundRef, ...] = (),
        is_published: bool = False,
        is_experimental: bool = True,
        extensions: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id=id, created_at=created_at, updated_at=updated_at, version=version)
        self._validate_resolution(resolution)
        self.workspace_id = workspace_id
        self.protein_id = protein_id
        self.provenance = provenance
        self.method = method
        self.resolution = resolution
        self.ligands = tuple(ligands)
        self.is_published = is_published
        self.is_experimental = is_experimental
        self.extensions = extensions if extensions is not None else {}

    @staticmethod
    def _validate_resolution(resolution: float | None) -> None:
        if resolution is not None and resolution <= 0:
            raise ValidationError("UnpublishedStructure resolution must be positive (Å)")

    @classmethod
    def create(
        cls,
        *,
        workspace_id: uuid.UUID,
        protein_id: uuid.UUID,
        provenance: Provenance,
        method: str | None = None,
        resolution: float | None = None,
        ligands: tuple[CompoundRef, ...] = (),
        is_published: bool = False,
        is_experimental: bool = True,
        extensions: dict[str, Any] | None = None,
    ) -> UnpublishedStructure:
        s = cls(
            workspace_id=workspace_id,
            protein_id=protein_id,
            provenance=provenance,
            method=method,
            resolution=resolution,
            ligands=ligands,
            is_published=is_published,
            is_experimental=is_experimental,
            extensions=extensions,
        )
        s.register_event(
            UnpublishedStructureCreated(
                aggregate_id=s.id,
                aggregate_type="UnpublishedStructure",
                workspace_id=workspace_id,
                protein_id=protein_id,
            )
        )
        return s

    def update(self, **fields: Any) -> None:
        if "resolution" in fields:
            self._validate_resolution(fields["resolution"])
            self.resolution = fields["resolution"]
        if "method" in fields:
            self.method = fields["method"]
        if "ligands" in fields:
            self.ligands = tuple(fields["ligands"] or ())
        if "is_published" in fields:
            self.is_published = bool(fields["is_published"])
        if "is_experimental" in fields:
            self.is_experimental = bool(fields["is_experimental"])
        if "provenance" in fields:
            self.provenance = fields["provenance"]
        if "extensions" in fields:
            self.extensions = dict(fields["extensions"] or {})
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now(UTC)
        self.register_event(
            UnpublishedStructureUpdated(
                aggregate_id=self.id,
                aggregate_type="UnpublishedStructure",
                workspace_id=self.workspace_id,
            )
        )
