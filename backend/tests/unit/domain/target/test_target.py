import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.events import TargetCreated, TargetUpdated
from protcellar.domain.target.target import Target, TargetComponent


def _component(
    rel: ComponentRelationship = ComponentRelationship.SINGLE_PROTEIN,
) -> TargetComponent:
    return TargetComponent(protein_id=uuid.uuid4(), relationship=rel)


def test_create_single_protein_target() -> None:
    ws = uuid.uuid4()
    target = Target.create(
        workspace_id=ws,
        pref_name="EGFR",
        target_type=TargetType.SINGLE_PROTEIN,
        components=[_component()],
    )
    assert target.workspace_id == ws
    assert target.pref_name == "EGFR"
    assert target.version == 1
    assert len(target.components) == 1
    events = target.collect_events()
    assert len(events) == 1 and isinstance(events[0], TargetCreated)


def test_create_requires_pref_name() -> None:
    with pytest.raises(ValidationError):
        Target.create(
            workspace_id=uuid.uuid4(),
            pref_name="  ",
            target_type=TargetType.UNKNOWN,
            components=[],
        )


def test_single_protein_requires_exactly_one_component() -> None:
    ws = uuid.uuid4()
    with pytest.raises(ValidationError):  # zero
        Target.create(
            workspace_id=ws, pref_name="X", target_type=TargetType.SINGLE_PROTEIN, components=[]
        )
    with pytest.raises(ValidationError):  # two
        Target.create(
            workspace_id=ws,
            pref_name="X",
            target_type=TargetType.SINGLE_PROTEIN,
            components=[_component(), _component()],
        )


@pytest.mark.parametrize(
    "ttype",
    [
        TargetType.PROTEIN_COMPLEX,
        TargetType.PROTEIN_FAMILY,
        TargetType.PROTEIN_PROTEIN_INTERACTION,
    ],
)
def test_multi_protein_types_require_at_least_two(ttype: TargetType) -> None:
    ws = uuid.uuid4()
    with pytest.raises(ValidationError):  # one is not enough
        Target.create(workspace_id=ws, pref_name="X", target_type=ttype, components=[_component()])
    # two is fine
    target = Target.create(
        workspace_id=ws, pref_name="X", target_type=ttype, components=[_component(), _component()]
    )
    assert len(target.components) == 2


def test_non_protein_type_allows_zero_components() -> None:
    target = Target.create(
        workspace_id=uuid.uuid4(),
        pref_name="Liver tissue",
        target_type=TargetType.TISSUE,
        components=[],
    )
    assert target.components == []


def test_update_revalidates_cardinality() -> None:
    target = Target.create(
        workspace_id=uuid.uuid4(),
        pref_name="X",
        target_type=TargetType.SINGLE_PROTEIN,
        components=[_component()],
    )
    # Adding a second component while still SINGLE_PROTEIN violates the invariant
    with pytest.raises(ValidationError):
        target.set_components([_component(), _component()])
    assert target.target_type == TargetType.SINGLE_PROTEIN
    assert len(target.components) == 1
    # Promoting to a complex with two components is valid
    target.update(target_type=TargetType.PROTEIN_COMPLEX, components=[_component(), _component()])
    assert target.target_type == TargetType.PROTEIN_COMPLEX
    assert len(target.components) == 2
    assert any(isinstance(e, TargetUpdated) for e in target.collect_events())


def test_update_rejection_leaves_aggregate_unchanged() -> None:
    target = Target.create(
        workspace_id=uuid.uuid4(),
        pref_name="X",
        target_type=TargetType.SINGLE_PROTEIN,
        components=[_component()],
    )
    with pytest.raises(ValidationError):
        target.update(components=[_component(), _component()])
    assert target.target_type == TargetType.SINGLE_PROTEIN
    assert len(target.components) == 1
    assert not any(isinstance(e, TargetUpdated) for e in target.collect_events())
