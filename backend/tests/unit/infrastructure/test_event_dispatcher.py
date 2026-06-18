import uuid

import pytest

from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher


@pytest.mark.asyncio
async def test_dispatch_calls_exact_and_catchall_handlers() -> None:
    seen: list[str] = []
    disp = EventDispatcher()

    async def catchall(ev: DomainEvent) -> None:
        seen.append("catchall")

    disp.register(DomainEvent, catchall)
    ev = DomainEvent(aggregate_id=uuid.uuid4(), aggregate_type="X", workspace_id=uuid.uuid4())
    await disp.dispatch_all([ev])
    assert seen == ["catchall"]
