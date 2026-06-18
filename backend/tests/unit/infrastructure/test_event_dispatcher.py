import uuid
from dataclasses import dataclass

import pytest

from protcellar.domain.shared.events import DomainEvent
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher


@pytest.mark.asyncio
async def test_dispatch_catchall_only() -> None:
    """Test that catch-all handler for DomainEvent receives base events."""
    seen: list[str] = []
    disp = EventDispatcher()

    async def catchall(ev: DomainEvent) -> None:
        seen.append("catchall")

    disp.register(DomainEvent, catchall)
    ev = DomainEvent(aggregate_id=uuid.uuid4(), aggregate_type="X", workspace_id=uuid.uuid4())
    await disp.dispatch_all([ev])
    assert seen == ["catchall"]


@pytest.mark.asyncio
async def test_dispatch_exact_match_and_catchall_no_double_dispatch() -> None:
    """Exact-match handler and catch-all both fire; no double-dispatch."""
    seen: list[str] = []
    disp = EventDispatcher()

    @dataclass(frozen=True, kw_only=True)
    class FooHappened(DomainEvent):
        """Concrete domain event subclass."""
        pass

    async def exact_handler(ev: DomainEvent) -> None:
        seen.append("exact")

    async def catchall_handler(ev: DomainEvent) -> None:
        seen.append("catchall")

    # Register exact-match handler for FooHappened and catch-all for DomainEvent
    disp.register(FooHappened, exact_handler)
    disp.register(DomainEvent, catchall_handler)

    # Dispatch a FooHappened instance
    ev = FooHappened(aggregate_id=uuid.uuid4(), aggregate_type="Foo", workspace_id=uuid.uuid4())
    await disp.dispatch_all([ev])

    # Both handlers should fire exactly once each (no double-dispatch)
    assert seen == ["exact", "catchall"]
