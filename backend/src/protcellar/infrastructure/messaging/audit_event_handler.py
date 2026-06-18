"""Audit event handler — records domain events as audit operations.

Registered as a catch-all handler for DomainEvent. Each event dispatch
gets its own database session and transaction so audit records are
persisted independently of the use case's UoW.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from protcellar.domain.audit_compliance.enums import (
    ActorType,
    AuditAction,
    AuditStatus,
    OperationType,
)
from protcellar.domain.audit_compliance.models import AuditEntry, AuditOperation
from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.persistence.sqlalchemy.audit_compliance.audit_repository import (
    SQLAlchemyAuditRepository,
)

logger = structlog.get_logger(__name__)


class AuditEventHandler:
    """Catch-all event handler that creates audit records.

    Uses a dedicated session per event to ensure audit persistence
    is independent of the originating use case's transaction.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(self, event: DomainEvent) -> None:
        try:
            repo = SQLAlchemyAuditRepository(self._session_factory)
            await _record_event(repo, event)
        except Exception:
            # Audit failure must not break the business operation.
            # Log and continue — the primary use case already committed.
            logger.exception(
                "audit.record_failed",
                event_type=type(event).__name__,
                aggregate_id=str(event.aggregate_id),
            )


async def _record_event(repo: SQLAlchemyAuditRepository, event: DomainEvent) -> None:
    """Map a DomainEvent to a minimal AuditOperation and persist it."""
    now = datetime.now(UTC)
    operation = AuditOperation(
        id=uuid.uuid4(),
        workspace_id=getattr(event, "workspace_id", uuid.UUID(int=0)),
        operation_type=OperationType.DATA_ENTRY,
        user_id=getattr(event, "user_id", uuid.UUID(int=0)),
        actor_type=ActorType.SYSTEM,
        entity_type=event.aggregate_type,
        entity_id=event.aggregate_id,
        status=AuditStatus.COMPLETED,
        started_at=event.occurred_at,
        completed_at=now,
    )

    operation.add_entry(
        AuditEntry(
            entity_type=event.aggregate_type,
            entity_id=event.aggregate_id,
            field_name="event",
            action=AuditAction.CREATE,
            new_value=type(event).__name__,
            timestamp=event.occurred_at,
        )
    )

    await repo.save(operation)
