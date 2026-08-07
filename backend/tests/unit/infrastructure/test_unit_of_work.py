"""Aggregate-tracking semantics of AsyncUnitOfWork.

These pin the contract commit() relies on — one entry per aggregate identity,
first-tracked instance wins, insertion order preserved — so the tracking
container can change shape (list scan → hashed) without changing behavior.
"""

from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from protcellar.domain.shared.entity import AggregateRoot
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork


def _uow() -> AsyncUnitOfWork:
    # track() never touches the session, so no factory is needed here.
    return AsyncUnitOfWork(cast("async_sessionmaker[AsyncSession]", None))


def test_track_dedupes_and_preserves_insertion_order() -> None:
    uow = _uow()
    a, b, c = AggregateRoot(), AggregateRoot(), AggregateRoot()
    for aggregate in (a, b, a, c, b):
        uow.track(aggregate)
    assert list(uow._tracked_aggregates) == [a, b, c]


def test_track_keeps_first_instance_for_equal_id_rehydrations() -> None:
    uow = _uow()
    first = AggregateRoot()
    rehydrated = AggregateRoot(id=first.id)
    uow.track(first)
    uow.track(rehydrated)
    tracked = list(uow._tracked_aggregates)
    assert len(tracked) == 1
    assert tracked[0] is first
