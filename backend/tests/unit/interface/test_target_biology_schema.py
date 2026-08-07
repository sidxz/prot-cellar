"""The published write contract is derived from the write-body models, never restated."""

from __future__ import annotations

from protcellar.application.target_biology.crud import RecordKind
from protcellar.interface.target_biology_schema import describe_write_surface


def test_describes_every_record_kind() -> None:
    schema = describe_write_surface({})
    assert set(schema["kinds"]) == {k.value for k in RecordKind}


def test_essentiality_classification_is_an_enum_with_domain_values() -> None:
    field = _field(describe_write_surface({}), "essentiality", "classification")
    assert field["type"] == "enum"
    assert field["required"] is True
    assert set(field["options"]) == {
        "essential",
        "growth_defect",
        "non_essential",
        "growth_advantage",
        "uncertain",
    }


def test_optional_fields_are_not_required() -> None:
    field = _field(describe_write_surface({}), "essentiality", "condition")
    assert field["type"] == "string"
    assert field["required"] is False


def test_confidence_carries_its_domain_bounds() -> None:
    field = _field(describe_write_surface({}), "essentiality", "confidence")
    assert field["type"] == "number"
    assert field["min"] == 0.0
    assert field["max"] == 1.0


def test_kinds_declare_which_parent_they_attach_to() -> None:
    schema = describe_write_surface({})
    assert schema["kinds"]["essentiality"]["attaches_to"] == "gene"
    assert schema["kinds"]["protein_production"]["attaches_to"] == "protein"


def test_reference_fields_name_their_target() -> None:
    compound = _field(describe_write_surface({}), "resistance_mutation", "compound")
    assert compound["type"] == "reference"
    assert compound["target"] == "compound"

    ligands = _field(describe_write_surface({}), "unpublished_structure", "ligands")
    assert ligands["type"] == "list"
    assert ligands["item_type"] == "reference"
    assert ligands["target"] == "compound"

    strain = _field(describe_write_surface({}), "hypomorph", "knockdown_strain_id")
    assert strain["type"] == "reference"
    assert strain["target"] == "strain"


def test_provenance_exposes_every_field_including_repeatable_citations() -> None:
    prov = describe_write_surface({})["provenance"]
    names = [f["name"] for f in prov["fields"]]
    assert names == [
        "source_type",
        "citations",
        "contributor_researcher",
        "observed_on",
        "note",
    ]
    citations = next(f for f in prov["fields"] if f["name"] == "citations")
    assert citations["type"] == "list"
    assert [f["name"] for f in citations["item_fields"]] == ["pmid", "doi", "url", "label"]
    # generation_method is deliberately absent: an edit re-attributes to a human.
    assert "generation_method" not in names


def test_suggested_values_are_attached_to_their_field() -> None:
    schema = describe_write_surface({("essentiality", "condition"): ["7H9", "cholesterol"]})
    field = _field(schema, "essentiality", "condition")
    assert field["suggested_values"] == ["7H9", "cholesterol"]


def test_extensions_is_reported_read_only_on_every_kind() -> None:
    schema = describe_write_surface({})
    for kind in RecordKind:
        assert "extensions" in schema["kinds"][kind.value]["read_only"]


def test_concurrency_field_is_discoverable() -> None:
    # PATCH bodies carry `version` for optimistic locking but aren't modeled in
    # `kinds` (which is derived from the POST bodies) — a client must be able to
    # learn the field name from the descriptor instead of hardcoding it.
    schema = describe_write_surface({})
    assert schema["concurrency"] == {"field": "version"}


def test_vocabulary_annotations_match_the_suggested_values_reader() -> None:
    """The interface's `vocabulary` flags and the reader's queried columns restate the
    same field list twice; nothing but this test keeps the two from drifting apart —
    a flag with no column means dead `suggested_values: []`, a column with no flag
    means a wasted query whose result no client ever sees."""
    from protcellar.infrastructure.persistence.sqlalchemy.target_biology.suggested_values_reader import (  # noqa: E501
        _VOCABULARY_COLUMNS,
    )

    schema = describe_write_surface({})
    for kind in RecordKind:
        descriptor_fields = {
            f["name"] for f in schema["kinds"][kind.value]["fields"] if "suggested_values" in f
        }
        assert descriptor_fields == set(_VOCABULARY_COLUMNS[kind]), kind


def _field(schema: dict, kind: str, name: str) -> dict:
    return next(f for f in schema["kinds"][kind]["fields"] if f["name"] == name)
