"""Audit & compliance enums."""

from enum import StrEnum


class OperationType(StrEnum):
    """Types of auditable operations across all bounded contexts."""

    DATA_ENTRY = "data_entry"
    PROPERTY_EDIT = "property_edit"
    BULK_IMPORT = "bulk_import"
    ACCESS_CHANGE = "access_change"
    REFERENCE_SYNC = "reference_sync"  # NEW — UniProt/NCBI/ChEMBL refresh
    ADMIN_HARD_DELETE = "admin_hard_delete"


class ActorType(StrEnum):
    """Who initiated the auditable operation."""

    USER = "user"
    SYSTEM = "system"
    INTEGRATION = "integration"


class AuditStatus(StrEnum):
    """Outcome of the auditable operation."""

    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class AuditAction(StrEnum):
    """Field-level change type within an AuditEntry."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class AuthMethod(StrEnum):
    """Authentication method for electronic signatures (21 CFR Part 11)."""

    PASSWORD = "password"
    MFA = "mfa"
    BIOMETRIC = "biometric"
