import uuid
from datetime import date

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)


def test_citation_requires_at_least_one_identifier() -> None:
    with pytest.raises(ValidationError):
        Citation()


def test_citation_accepts_a_single_identifier() -> None:
    assert Citation(pmid="28096490").pmid == "28096490"
    assert Citation(label="internal notebook 2024").label == "internal notebook 2024"


def test_provenance_construction() -> None:
    p = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        citations=(Citation(pmid="28096490", label="DeJesus 2017"),),
        contributor_organization_id=uuid.uuid4(),
        observed_on=date(2017, 1, 24),
        note="TnSeq",
    )
    assert p.source_type is ProvenanceSourceType.PUBLISHED
    assert p.citations[0].pmid == "28096490"


def test_provenance_defaults_are_empty() -> None:
    p = Provenance(source_type=ProvenanceSourceType.INTERNAL)
    assert p.citations == ()
    assert p.contributor_organization_id is None


def test_generation_method_defaults_to_manual() -> None:
    p = Provenance(source_type=ProvenanceSourceType.PUBLISHED)
    assert p.generation_method is GenerationMethod.MANUAL


def test_generation_method_is_settable() -> None:
    p = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        generation_method=GenerationMethod.AI_EXTRACTED,
    )
    assert p.generation_method is GenerationMethod.AI_EXTRACTED
