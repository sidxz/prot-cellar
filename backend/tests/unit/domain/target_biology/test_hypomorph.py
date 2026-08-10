import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.events import HypomorphCreated, HypomorphUpdated
from protcellar.domain.target_biology.hypomorph import Hypomorph


def _prov() -> Provenance:
    return Provenance(source_type=ProvenanceSourceType.INTERNAL)


def test_create_hypomorph() -> None:
    ws, gene, strain = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    h = Hypomorph.create(
        workspace_id=ws,
        gene_id=gene,
        growth_defect=True,
        growth_defect_severity="severe",
        knockdown_strain_id=strain,
        provenance=_prov(),
    )
    assert h.gene_id == gene
    assert h.growth_defect is True
    assert h.knockdown_strain_id == strain
    events = h.collect_events()
    assert len(events) == 1 and isinstance(events[0], HypomorphCreated)
    assert events[0].gene_id == gene


def test_severity_requires_growth_defect() -> None:
    with pytest.raises(ValidationError):
        Hypomorph.create(
            workspace_id=uuid.uuid4(),
            gene_id=uuid.uuid4(),
            growth_defect=False,
            growth_defect_severity="mild",
            provenance=_prov(),
        )


def test_growth_defect_is_optional() -> None:
    h = Hypomorph.create(workspace_id=uuid.uuid4(), gene_id=uuid.uuid4(), provenance=_prov())
    assert h.growth_defect is None


def test_growth_defect_true_and_false_both_round_trip() -> None:
    yes = Hypomorph.create(
        workspace_id=uuid.uuid4(), gene_id=uuid.uuid4(), growth_defect=True, provenance=_prov()
    )
    assert yes.growth_defect is True
    no = Hypomorph.create(
        workspace_id=uuid.uuid4(), gene_id=uuid.uuid4(), growth_defect=False, provenance=_prov()
    )
    assert no.growth_defect is False


def test_severity_requires_growth_defect_true_not_merely_not_false() -> None:
    """None ("not determined") is treated the same as False for this rule — a
    severity claim makes no more sense for an undetermined defect than for a
    confirmed-absent one."""
    with pytest.raises(ValidationError):
        Hypomorph.create(
            workspace_id=uuid.uuid4(),
            gene_id=uuid.uuid4(),
            growth_defect=None,
            growth_defect_severity="severe",
            provenance=_prov(),
        )


def test_update_revalidates_and_records_event() -> None:
    h = Hypomorph.create(
        workspace_id=uuid.uuid4(),
        gene_id=uuid.uuid4(),
        growth_defect=True,
        growth_defect_severity="mild",
        provenance=_prov(),
    )
    h.clear_events()
    # Clearing the defect while a severity is still set must fail.
    with pytest.raises(ValidationError):
        h.update(growth_defect=False)
    h.update(growth_defect=False, growth_defect_severity=None)
    assert h.growth_defect is False
    events = h.collect_events()
    assert len(events) == 1 and isinstance(events[0], HypomorphUpdated)


def test_update_can_clear_growth_defect_to_not_determined() -> None:
    h = Hypomorph.create(
        workspace_id=uuid.uuid4(), gene_id=uuid.uuid4(), growth_defect=True, provenance=_prov()
    )
    h.update(growth_defect=None)
    assert h.growth_defect is None
