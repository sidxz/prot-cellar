"""Param schemas and helpers for import use cases."""

from __future__ import annotations

import uuid
from typing import Any

import pydantic

from protcellar.domain.imports.enums import ImportType
from protcellar.domain.shared.errors import ValidationError as DomainValidationError


class ProteomeParams(pydantic.BaseModel):
    proteome_id: str
    force: bool = False
    dry_run: bool = False
    limit: int | None = None


class GeneEnrichmentParams(pydantic.BaseModel):
    tax_id: int | None = None
    organism_id: uuid.UUID | None = None
    gff_url: str | None = None
    essentiality_url: str | None = None
    essentiality_upload_ref: uuid.UUID | None = None
    force: bool = False

    @pydantic.model_validator(mode="after")
    def _require_organism_identifier(self) -> GeneEnrichmentParams:
        if self.organism_id is None and self.tax_id is None:
            raise ValueError("gene enrichment requires organism_id or tax_id")
        return self


class GoOntologyParams(pydantic.BaseModel):
    force: bool = False


_PARAM_MODELS: dict[ImportType, type[pydantic.BaseModel]] = {
    ImportType.PROTEOME: ProteomeParams,
    ImportType.GENE_ENRICHMENT: GeneEnrichmentParams,
    ImportType.GO_ONTOLOGY: GoOntologyParams,
}


def validate_params(import_type: ImportType, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise raw params for the given import type.

    Returns a JSON-serialisable dict (mode="json" model_dump).
    Raises ``protcellar.domain.shared.errors.ValidationError`` on bad input.
    """
    model_cls = _PARAM_MODELS[import_type]
    try:
        instance = model_cls(**raw)
    except pydantic.ValidationError as exc:
        raise DomainValidationError(str(exc)) from exc
    return instance.model_dump(mode="json")


def target_key(import_type: ImportType, params: dict[str, Any]) -> str:
    """Derive the target_key string for an import run from its normalised params."""
    if import_type is ImportType.PROTEOME:
        return str(params["proteome_id"])
    if import_type is ImportType.GENE_ENRICHMENT:
        return str(params.get("organism_id") or params.get("tax_id"))
    # GO_ONTOLOGY
    return "go"


def needs_upload(import_type: ImportType, params: dict[str, Any]) -> bool:
    """Return True if this import type + params require an upload reference."""
    if import_type is ImportType.GENE_ENRICHMENT:
        return bool(params.get("essentiality_upload_ref"))
    return False


def upload_ref_of(import_type: ImportType, params: dict[str, Any]) -> uuid.UUID | None:
    """Return the upload UUID for this run, or None."""
    if import_type is ImportType.GENE_ENRICHMENT:
        ref = params.get("essentiality_upload_ref")
        if ref is not None:
            return uuid.UUID(str(ref))
    return None
