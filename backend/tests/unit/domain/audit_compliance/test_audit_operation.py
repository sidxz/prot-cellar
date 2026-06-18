import uuid

from protcellar.domain.audit_compliance.enums import AuditAction
from protcellar.domain.audit_compliance.models import AuditEntry, AuditOperation


def test_add_entry_sets_operation_id() -> None:
    op = AuditOperation(workspace_id=uuid.uuid4(), entity_type="Organism")
    entry = AuditEntry(entity_type="Organism", field_name="name", action=AuditAction.CREATE)
    op.add_entry(entry)
    assert op.entries[0].operation_id == op.id
