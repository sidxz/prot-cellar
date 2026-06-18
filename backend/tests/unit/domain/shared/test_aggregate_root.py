import uuid

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.domain.shared.events import DomainEvent


def test_register_and_collect_events_then_clear() -> None:
    agg = AggregateRoot()
    assert agg.version == 1
    ev = DomainEvent(aggregate_id=agg.id, aggregate_type="X", workspace_id=uuid.uuid4())
    agg.register_event(ev)
    collected = agg.collect_events()
    assert collected == [ev]
    agg.clear_events()
    assert agg.collect_events() == []
