import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.events import (
    EssentialityCreated,
    EssentialityUpdated,
)


def _prov() -> Provenance:
    return Provenance(source_type=ProvenanceSourceType.PUBLISHED)


def test_create_essentiality() -> None:
    ws, gene = uuid.uuid4(), uuid.uuid4()
    e = Essentiality.create(
        workspace_id=ws,
        gene_id=gene,
        classification=EssentialityClass.ESSENTIAL,
        condition="in vitro 7H9",
        method="TnSeq",
        provenance=_prov(),
    )
    assert e.workspace_id == ws
    assert e.gene_id == gene
    assert e.classification is EssentialityClass.ESSENTIAL
    assert e.extensions == {}
    assert e.version == 1
    events = e.collect_events()
    assert len(events) == 1 and isinstance(events[0], EssentialityCreated)
    assert events[0].gene_id == gene


def test_confidence_must_be_normalized() -> None:
    with pytest.raises(ValidationError):
        Essentiality.create(
            workspace_id=uuid.uuid4(),
            gene_id=uuid.uuid4(),
            classification=EssentialityClass.ESSENTIAL,
            confidence=1.5,
            provenance=_prov(),
        )


def test_update_records_event_and_changes_fields() -> None:
    e = Essentiality.create(
        workspace_id=uuid.uuid4(),
        gene_id=uuid.uuid4(),
        classification=EssentialityClass.UNCERTAIN,
        provenance=_prov(),
    )
    e.clear_events()
    e.update(classification=EssentialityClass.NON_ESSENTIAL, extensions={"raw_call": "NE"})
    assert e.classification is EssentialityClass.NON_ESSENTIAL
    assert e.extensions == {"raw_call": "NE"}
    events = e.collect_events()
    assert len(events) == 1 and isinstance(events[0], EssentialityUpdated)
