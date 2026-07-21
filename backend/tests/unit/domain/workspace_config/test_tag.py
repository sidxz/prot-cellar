import uuid

from protcellar.domain.workspace_config.tagging.events import TagCreated, TagRenamed
from protcellar.domain.workspace_config.tagging.tag import (
    Tag,
    TaggableEntityType,
    TagName,
)


def test_create_emits_tag_created() -> None:
    ws = uuid.uuid4()
    created_by = uuid.uuid4()
    tag = Tag.create(workspace_id=ws, key="Priority", value="High", created_by=created_by)

    assert tag.workspace_id == ws
    assert tag.created_by == created_by
    assert tag.key == "Priority"
    assert tag.value == "High"
    assert tag.normalized_key == "priority"
    assert tag.normalized_value == "high"

    events = tag.collect_events()
    assert len(events) == 1
    assert isinstance(events[0], TagCreated)
    assert events[0].key == "Priority"
    assert events[0].value == "High"


def test_rename_emits_tag_renamed() -> None:
    tag = Tag.create(
        workspace_id=uuid.uuid4(), key="Priority", value="High", created_by=uuid.uuid4()
    )
    tag.clear_events()

    tag.rename(TagName(key="Priority", value="Low"))

    assert tag.key == "Priority"
    assert tag.value == "Low"
    events = tag.collect_events()
    assert len(events) == 1
    assert isinstance(events[0], TagRenamed)
    assert events[0].value == "Low"


def test_rename_noop_when_unchanged_emits_no_event() -> None:
    tag = Tag.create(
        workspace_id=uuid.uuid4(), key="Priority", value="High", created_by=uuid.uuid4()
    )
    tag.clear_events()

    tag.rename(TagName(key="Priority", value="High"))

    assert tag.collect_events() == []


def test_taggable_entity_type_members() -> None:
    assert {member.value for member in TaggableEntityType} == {
        "Protein",
        "Gene",
        "Target",
        "Organism",
        "Strain",
        "Proteome",
    }
    assert TaggableEntityType.PROTEIN == "Protein"
    assert TaggableEntityType.GENE == "Gene"
    assert TaggableEntityType.TARGET == "Target"
    assert TaggableEntityType.ORGANISM == "Organism"
    assert TaggableEntityType.STRAIN == "Strain"
    assert TaggableEntityType.PROTEOME == "Proteome"
