"""SQLAlchemySuggestedValuesReader caches its query behind a short TTL."""

from __future__ import annotations

from protcellar.infrastructure.persistence.sqlalchemy.target_biology.suggested_values_reader import (  # noqa: E501
    SQLAlchemySuggestedValuesReader,
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _reader(clock: _FakeClock) -> tuple[SQLAlchemySuggestedValuesReader, list[int]]:
    calls: list[int] = []

    async def fake_fetch() -> dict[tuple[str, str], list[str]]:
        calls.append(1)
        return {("essentiality", "condition"): [f"call-{len(calls)}"]}

    reader = SQLAlchemySuggestedValuesReader(lambda: None, ttl_seconds=60.0, clock=clock)
    reader._fetch = fake_fetch  # type: ignore[method-assign]
    return reader, calls


async def test_repeated_calls_within_the_ttl_reuse_the_cached_result() -> None:
    clock = _FakeClock()
    reader, calls = _reader(clock)

    first = await reader.for_all_kinds()
    clock.now += 30  # still inside the 60s TTL
    second = await reader.for_all_kinds()

    assert len(calls) == 1
    assert first == second == {("essentiality", "condition"): ["call-1"]}


async def test_a_call_past_the_ttl_refetches() -> None:
    clock = _FakeClock()
    reader, calls = _reader(clock)

    await reader.for_all_kinds()
    clock.now += 61  # past the 60s TTL
    await reader.for_all_kinds()

    assert len(calls) == 2
