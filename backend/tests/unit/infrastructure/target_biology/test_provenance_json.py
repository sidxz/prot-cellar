import uuid
from datetime import date

from protcellar.domain.shared.provenance import Citation, Provenance, ProvenanceSourceType
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
