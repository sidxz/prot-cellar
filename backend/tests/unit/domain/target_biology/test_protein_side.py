import uuid

import pytest

from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.events import (
    ProteinActivityAssayCreated,
    ProteinProductionCreated,
    UnpublishedStructureCreated,
)
from protcellar.domain.target_biology.protein_activity_assay import ProteinActivityAssay
from protcellar.domain.target_biology.protein_production import ProteinProduction
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure


def _prov() -> Provenance:
    return Provenance(source_type=ProvenanceSourceType.INTERNAL)


def test_create_protein_production() -> None:
    ws, protein = uuid.uuid4(), uuid.uuid4()
    p = ProteinProduction.create(
        workspace_id=ws,
        protein_id=protein,
        status="produced",
        expression_host="E. coli BL21",
        purity=95.0,
        provenance=_prov(),
    )
    assert p.protein_id == protein
    assert p.status == "produced"
    events = p.collect_events()
    assert len(events) == 1 and isinstance(events[0], ProteinProductionCreated)
    assert events[0].protein_id == protein


def test_production_status_required() -> None:
    with pytest.raises(ValidationError):
        ProteinProduction.create(
            workspace_id=uuid.uuid4(), protein_id=uuid.uuid4(), status="  ", provenance=_prov()
        )


def test_create_activity_assay() -> None:
    ws, protein = uuid.uuid4(), uuid.uuid4()
    a = ProteinActivityAssay.create(
        workspace_id=ws,
        protein_id=protein,
        activity_measured="ATPase",
        readout="fluorescence",
        throughput="384-well",
        provenance=_prov(),
    )
    assert a.activity_measured == "ATPase"
    events = a.collect_events()
    assert len(events) == 1 and isinstance(events[0], ProteinActivityAssayCreated)


def test_activity_measured_required() -> None:
    with pytest.raises(ValidationError):
        ProteinActivityAssay.create(
            workspace_id=uuid.uuid4(),
            protein_id=uuid.uuid4(),
            activity_measured="",
            provenance=_prov(),
        )


def test_create_unpublished_structure_with_ligands() -> None:
    ws, protein, ligand = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    s = UnpublishedStructure.create(
        workspace_id=ws,
        protein_id=protein,
        method="X-ray",
        resolution=1.9,
        ligands=(CompoundRef(compound_id=ligand, name="ATP"),),
        provenance=_prov(),
    )
    assert s.resolution == 1.9
    assert s.is_published is False and s.is_experimental is True
    assert s.ligands[0].compound_id == ligand
    events = s.collect_events()
    assert len(events) == 1 and isinstance(events[0], UnpublishedStructureCreated)


def test_structure_resolution_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        UnpublishedStructure.create(
            workspace_id=uuid.uuid4(),
            protein_id=uuid.uuid4(),
            resolution=0.0,
            provenance=_prov(),
        )
