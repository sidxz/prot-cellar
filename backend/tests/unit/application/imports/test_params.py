"""Unit tests for application.imports.params — param models, validate_params, target_key."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.imports.params import (
    GeneEnrichmentParams,
    GoOntologyParams,
    ProteomeParams,
    TargetBiologyParams,
    target_key,
    validate_params,
)
from protcellar.domain.imports.enums import ImportType
from protcellar.domain.shared.errors import ValidationError

# ---------------------------------------------------------------------------
# ProteomeParams
# ---------------------------------------------------------------------------


def test_proteome_params_valid_minimal() -> None:
    p = ProteomeParams(proteome_id="UP000001584")
    assert p.proteome_id == "UP000001584"
    assert p.force is False
    assert p.dry_run is False
    assert p.limit is None


def test_proteome_params_valid_full() -> None:
    p = ProteomeParams(proteome_id="UP000001584", force=True, dry_run=True, limit=10)
    assert p.force is True
    assert p.dry_run is True
    assert p.limit == 10


def test_proteome_params_missing_proteome_id_raises() -> None:
    with pytest.raises(ValidationError):
        validate_params(ImportType.PROTEOME, {})


# ---------------------------------------------------------------------------
# GeneEnrichmentParams
# ---------------------------------------------------------------------------


def test_gene_enrichment_params_with_organism_id() -> None:
    oid = uuid.uuid4()
    p = GeneEnrichmentParams(organism_id=oid)
    assert p.organism_id == oid
    assert p.tax_id is None


def test_gene_enrichment_params_with_tax_id() -> None:
    p = GeneEnrichmentParams(tax_id=1773)
    assert p.tax_id == 1773


def test_gene_enrichment_params_all_none_raises() -> None:
    with pytest.raises(ValidationError):
        validate_params(ImportType.GENE_ENRICHMENT, {})


# ---------------------------------------------------------------------------
# GoOntologyParams
# ---------------------------------------------------------------------------


def test_go_ontology_params_defaults() -> None:
    p = GoOntologyParams()
    assert p.force is False


def test_go_ontology_params_force() -> None:
    p = GoOntologyParams(force=True)
    assert p.force is True


# ---------------------------------------------------------------------------
# TargetBiologyParams
# ---------------------------------------------------------------------------


def test_target_biology_params_valid_minimal() -> None:
    upload_ref = uuid.uuid4()
    proteome_id = uuid.uuid4()
    p = TargetBiologyParams(upload_ref=upload_ref, proteome_id=proteome_id)
    assert p.upload_ref == upload_ref
    assert p.proteome_id == proteome_id
    assert p.match_by == "locus_tag"
    assert p.update_existing is False
    assert p.dry_run is True


def test_target_biology_params_has_no_organism_id_field() -> None:
    """organism_id was replaced by proteome_id — an organism alone cannot pin
    a locus/name namespace when the organism holds multiple strains."""
    assert "organism_id" not in TargetBiologyParams.model_fields
    assert "proteome_id" in TargetBiologyParams.model_fields


def test_target_biology_params_missing_proteome_id_raises() -> None:
    with pytest.raises(ValidationError):
        validate_params(ImportType.TARGET_BIOLOGY, {"upload_ref": str(uuid.uuid4())})


def test_target_biology_params_rejects_a_non_uuid_proteome_id() -> None:
    """The Pydantic layer only rejects malformed input — an unknown-but-well-formed
    UUID is rejected later, by the adapter's own find_readable lookup (see
    test_target_biology_import.py::test_an_unknown_proteome_fails_the_run),
    since proteome existence is a DB fact this layer has no access to."""
    with pytest.raises(ValidationError):
        validate_params(
            ImportType.TARGET_BIOLOGY,
            {"upload_ref": str(uuid.uuid4()), "proteome_id": "not-a-uuid"},
        )


# ---------------------------------------------------------------------------
# validate_params
# ---------------------------------------------------------------------------


def test_validate_params_proteome_returns_dict() -> None:
    result = validate_params(ImportType.PROTEOME, {"proteome_id": "UP000001584"})
    assert isinstance(result, dict)
    assert result["proteome_id"] == "UP000001584"
    assert result["force"] is False


def test_validate_params_gene_enrichment_returns_dict() -> None:
    oid = uuid.uuid4()
    result = validate_params(ImportType.GENE_ENRICHMENT, {"organism_id": str(oid)})
    assert isinstance(result, dict)
    # UUIDs are serialized as strings in mode="json"
    assert result["organism_id"] == str(oid)


def test_validate_params_go_ontology_returns_dict() -> None:
    result = validate_params(ImportType.GO_ONTOLOGY, {})
    assert isinstance(result, dict)
    assert result["force"] is False


def test_validate_params_proteome_missing_id_raises_domain_error() -> None:
    with pytest.raises(ValidationError):
        validate_params(ImportType.PROTEOME, {})


def test_validate_params_proteome_wrong_type_raises_domain_error() -> None:
    with pytest.raises(ValidationError):
        validate_params(ImportType.PROTEOME, {"proteome_id": 123})


def test_validate_params_gene_enrichment_no_identifier_raises_domain_error() -> None:
    with pytest.raises(ValidationError):
        validate_params(ImportType.GENE_ENRICHMENT, {})


def test_validate_params_gene_enrichment_bad_tax_id_type_raises_domain_error() -> None:
    with pytest.raises(ValidationError):
        validate_params(ImportType.GENE_ENRICHMENT, {"tax_id": "not-an-int"})


def test_validate_params_go_ontology_bad_force_type_raises_domain_error() -> None:
    with pytest.raises(ValidationError):
        validate_params(ImportType.GO_ONTOLOGY, {"force": "not-a-bool"})


# ---------------------------------------------------------------------------
# target_key
# ---------------------------------------------------------------------------


def test_target_key_proteome() -> None:
    params = {"proteome_id": "UP000001584", "force": False, "dry_run": False, "limit": None}
    assert target_key(ImportType.PROTEOME, params) == "UP000001584"


def test_target_key_gene_enrichment_organism_id() -> None:
    oid = uuid.uuid4()
    params = {"organism_id": str(oid), "tax_id": None, "force": False}
    assert target_key(ImportType.GENE_ENRICHMENT, params) == str(oid)


def test_target_key_gene_enrichment_tax_id_fallback() -> None:
    params = {"organism_id": None, "tax_id": 1773, "force": False}
    assert target_key(ImportType.GENE_ENRICHMENT, params) == "1773"


def test_target_key_go_ontology() -> None:
    params = {"force": False}
    assert target_key(ImportType.GO_ONTOLOGY, params) == "go"


def test_target_key_target_biology_dry_run() -> None:
    proteome_id = uuid.uuid4()
    upload_ref = uuid.uuid4()
    params = {"proteome_id": str(proteome_id), "upload_ref": str(upload_ref), "dry_run": True}
    assert target_key(ImportType.TARGET_BIOLOGY, params) == f"{proteome_id}:{upload_ref}:dry"


def test_target_key_target_biology_apply() -> None:
    """Same upload, dry_run=False — a distinct key from the preview above so
    apply is never mistaken for an already-active run of its own preview."""
    proteome_id = uuid.uuid4()
    upload_ref = uuid.uuid4()
    params = {"proteome_id": str(proteome_id), "upload_ref": str(upload_ref), "dry_run": False}
    assert target_key(ImportType.TARGET_BIOLOGY, params) == f"{proteome_id}:{upload_ref}:run"
