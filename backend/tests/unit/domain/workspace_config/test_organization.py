import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.workspace_config.enums import OrganizationType
from protcellar.domain.workspace_config.events import OrganizationCreated
from protcellar.domain.workspace_config.organization import Organization


def test_create_sets_fields_and_emits_event() -> None:
    ws = uuid.uuid4()
    org = Organization.create(workspace_id=ws, name="EBI", org_type=OrganizationType.ACADEMIC)
    assert org.name == "EBI"
    assert org.version == 1
    events = org.collect_events()
    assert len(events) == 1 and isinstance(events[0], OrganizationCreated)


def test_empty_name_raises() -> None:
    with pytest.raises(ValidationError):
        Organization.create(workspace_id=uuid.uuid4(), name="", org_type=OrganizationType.ACADEMIC)
