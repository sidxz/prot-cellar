import uuid

import pytest

from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.events import (
    ResistanceMutationCreated,
    ResistanceMutationUpdated,
)
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation


def _prov() -> Provenance:
    return Provenance(source_type=ProvenanceSourceType.PUBLISHED)


def test_create_resistance_mutation() -> None:
    ws, gene, compound = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rm = ResistanceMutation.create(
        workspace_id=ws,
        gene_id=gene,
        mutation="S315T",
        compound=CompoundRef(compound_id=compound, name="isoniazid"),
        mic_shift=64.0,
        parent_strain="H37Rv",
        protein_coordinate="S315T",
        provenance=_prov(),
    )
    assert rm.gene_id == gene
    assert rm.mutation == "S315T"
    assert rm.compound is not None and rm.compound.compound_id == compound
    assert rm.mic_shift == 64.0
    events = rm.collect_events()
    assert len(events) == 1 and isinstance(events[0], ResistanceMutationCreated)
    assert events[0].gene_id == gene


def test_mutation_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        ResistanceMutation.create(
            workspace_id=uuid.uuid4(),
            gene_id=uuid.uuid4(),
            mutation="  ",
            provenance=_prov(),
        )


def test_update_records_event() -> None:
    rm = ResistanceMutation.create(
        workspace_id=uuid.uuid4(),
        gene_id=uuid.uuid4(),
        mutation="D94G",
        provenance=_prov(),
    )
    rm.clear_events()
    rm.update(mic_shift=8.0)
    assert rm.mic_shift == 8.0
    events = rm.collect_events()
    assert len(events) == 1 and isinstance(events[0], ResistanceMutationUpdated)
