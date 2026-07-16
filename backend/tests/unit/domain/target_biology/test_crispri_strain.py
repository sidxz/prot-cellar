import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.events import (
    CrispriStrainCreated,
    CrispriStrainUpdated,
)


def _prov() -> Provenance:
    return Provenance(source_type=ProvenanceSourceType.INTERNAL)


def test_create_crispri_strain() -> None:
    ws, gene = uuid.uuid4(), uuid.uuid4()
    s = CrispriStrain.create(
        workspace_id=ws,
        name="sgRNA-rpoB-1",
        target_gene_id=gene,
        provenance=_prov(),
        extensions={"promoter": "P606"},
    )
    assert s.name == "sgRNA-rpoB-1"
    assert s.target_gene_id == gene
    assert s.extensions == {"promoter": "P606"}
    events = s.collect_events()
    assert len(events) == 1 and isinstance(events[0], CrispriStrainCreated)
    assert events[0].target_gene_id == gene


def test_name_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        CrispriStrain.create(
            workspace_id=uuid.uuid4(),
            name="   ",
            target_gene_id=uuid.uuid4(),
            provenance=_prov(),
        )


def test_update_records_event() -> None:
    s = CrispriStrain.create(
        workspace_id=uuid.uuid4(),
        name="s1",
        target_gene_id=uuid.uuid4(),
        provenance=_prov(),
    )
    s.clear_events()
    s.update(name="s1-rev2")
    assert s.name == "s1-rev2"
    events = s.collect_events()
    assert len(events) == 1 and isinstance(events[0], CrispriStrainUpdated)
