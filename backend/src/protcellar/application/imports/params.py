"""Param schemas and helpers for import use cases."""

from __future__ import annotations

import uuid
from typing import Any, Literal

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
    force: bool = False

    @pydantic.model_validator(mode="after")
    def _require_organism_identifier(self) -> GeneEnrichmentParams:
        if self.organism_id is None and self.tax_id is None:
            raise ValueError("gene enrichment requires organism_id or tax_id")
        return self


class GoOntologyParams(pydantic.BaseModel):
    force: bool = False


class TargetBiologyParams(pydantic.BaseModel):
    """Params for :class:`ImportType.TARGET_BIOLOGY`. Deliberately has no
    ``target_workspace_id`` field: that value is never client-settable — the
    adapter derives it server-side from the run's own ``workspace_id`` (see
    ``ImportRuntime.workspace_id`` in ``infrastructure/ingestion/import_adapters.py``),
    which is itself set from the *caller's* ``auth.workspace_id`` at
    ``StartImport`` time, never from this params bag.
    """

    upload_ref: uuid.UUID
    organism_id: uuid.UUID
    match_by: Literal["locus_tag", "gene_name"] = "locus_tag"
    update_existing: bool = False
    dry_run: bool = True  # preview is the default; applying is the deliberate act


_PARAM_MODELS: dict[ImportType, type[pydantic.BaseModel]] = {
    ImportType.PROTEOME: ProteomeParams,
    ImportType.GENE_ENRICHMENT: GeneEnrichmentParams,
    ImportType.GO_ONTOLOGY: GoOntologyParams,
    ImportType.TARGET_BIOLOGY: TargetBiologyParams,
}


def validate_params(import_type: ImportType, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise raw params for the given import type.

    Returns a JSON-serialisable dict (mode="json" model_dump).
    Raises ``protcellar.domain.shared.errors.ValidationError`` on bad input.
    """
    if import_type is ImportType.PLUGIN:
        # Already validated against the plugin manifest at the route boundary.
        return dict(raw)
    model_cls = _PARAM_MODELS[import_type]
    try:
        instance = model_cls(**raw)
    except pydantic.ValidationError as exc:
        raise DomainValidationError(str(exc)) from exc
    return instance.model_dump(mode="json")


def target_key(import_type: ImportType, params: dict[str, Any]) -> str:
    """Derive the target_key string for an import run from its normalised params."""
    if import_type is ImportType.PLUGIN:
        strain = params.get("organism_id") or params.get("tax_id") or "global"
        return f"{params['plugin_id']}:{strain}:{'dry' if params.get('dry_run') else 'run'}"
    if import_type is ImportType.PROTEOME:
        return str(params["proteome_id"])
    if import_type is ImportType.GENE_ENRICHMENT:
        return str(params.get("organism_id") or params.get("tax_id"))
    if import_type is ImportType.TARGET_BIOLOGY:
        # organism + upload identify the target; dry/run keeps a preview from
        # colliding with the apply that follows it (both target the same upload).
        dry = "dry" if params.get("dry_run") else "run"
        return f"{params['organism_id']}:{params['upload_ref']}:{dry}"
    # GO_ONTOLOGY
    return "go"


def upload_ref_of(import_type: ImportType, params: dict[str, Any]) -> uuid.UUID | None:
    """Return the upload UUID for this run, or None."""
    if import_type in (ImportType.PLUGIN, ImportType.TARGET_BIOLOGY):
        ref = params.get("upload_ref")
        return uuid.UUID(str(ref)) if ref else None
    return None
