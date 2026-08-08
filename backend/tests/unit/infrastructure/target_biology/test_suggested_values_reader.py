"""SQLAlchemySuggestedValuesReader caches its query behind a short TTL, per workspace."""

from __future__ import annotations

import uuid

from protcellar.infrastructure.persistence.sqlalchemy.target_biology.suggested_values_reader import (  # noqa: E501
    SQLAlchemySuggestedValuesReader,
)

_WS = uuid.uuid4()


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _reader(clock: _FakeClock) -> tuple[SQLAlchemySuggestedValuesReader, list[uuid.UUID]]:
    calls: list[uuid.UUID] = []

    async def fake_fetch(workspace_id: uuid.UUID) -> dict[tuple[str, str], list[str]]:
        calls.append(workspace_id)
        return {("essentiality", "condition"): [f"call-{len(calls)}"]}

    reader = SQLAlchemySuggestedValuesReader(lambda: None, ttl_seconds=60.0, clock=clock)
    reader._fetch = fake_fetch  # type: ignore[method-assign]
    return reader, calls


async def test_repeated_calls_within_the_ttl_reuse_the_cached_result() -> None:
    clock = _FakeClock()
    reader, calls = _reader(clock)

    first = await reader.for_all_kinds(_WS)
    clock.now += 30  # still inside the 60s TTL
    second = await reader.for_all_kinds(_WS)

    assert len(calls) == 1
    assert first == second == {("essentiality", "condition"): ["call-1"]}


async def test_a_call_past_the_ttl_refetches() -> None:
    clock = _FakeClock()
    reader, calls = _reader(clock)

    await reader.for_all_kinds(_WS)
    clock.now += 61  # past the 60s TTL
    await reader.for_all_kinds(_WS)

    assert len(calls) == 2


async def test_a_different_workspace_never_sees_another_workspaces_cached_result() -> None:
    """The regression this reader exists to prevent: a process-wide cache keyed by
    nothing would hand workspace B whatever workspace A's call had just cached,
    inside the same TTL window, without ever re-querying.
    """
    clock = _FakeClock()
    reader, calls = _reader(clock)
    other_ws = uuid.uuid4()

    first = await reader.for_all_kinds(_WS)
    second = await reader.for_all_kinds(other_ws)  # still inside A's TTL window

    assert len(calls) == 2  # both workspaces hit the query — no cross-workspace reuse
    assert calls == [_WS, other_ws]
    assert first == {("essentiality", "condition"): ["call-1"]}
    assert second == {("essentiality", "condition"): ["call-2"]}
