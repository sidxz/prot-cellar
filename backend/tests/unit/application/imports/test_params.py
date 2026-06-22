"""Unit tests for application.imports.params — param models, validate_params, target_key."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.imports.params import (
    GeneEnrichmentParams,
    GoOntologyParams,
    ProteomeParams,
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


def test_gene_enrichment_params_with_upload_ref() -> None:
    ref = uuid.uuid4()
    oid = uuid.uuid4()
    p = GeneEnrichmentParams(organism_id=oid, essentiality_upload_ref=ref)
    assert p.essentiality_upload_ref == ref


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
