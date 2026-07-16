import uuid
from datetime import date

from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology._provenance_json import (
    provenance_from_json,
    provenance_to_json,
)


def test_provenance_round_trip() -> None:
    org = uuid.uuid4()
    original = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        citations=(Citation(pmid="28096490", label="DeJesus 2017"), Citation(doi="10.1/x")),
        contributor_researcher="Ada",
        contributor_organization_id=org,
        observed_on=date(2017, 1, 24),
        note="TnSeq",
    )
    restored = provenance_from_json(provenance_to_json(original))
    assert restored == original


def test_provenance_from_json_none() -> None:
    assert provenance_from_json(None) is None


def test_generation_method_round_trips() -> None:
    original = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        generation_method=GenerationMethod.AI_EXTRACTED,
    )
    restored = provenance_from_json(provenance_to_json(original))
    assert restored == original
    assert restored.generation_method is GenerationMethod.AI_EXTRACTED


def test_legacy_json_without_generation_method_defaults_to_manual() -> None:
    # A provenance blob written before the field existed.
    legacy = {"source_type": "published", "citations": []}
    restored = provenance_from_json(legacy)
    assert restored is not None
    assert restored.generation_method is GenerationMethod.MANUAL
