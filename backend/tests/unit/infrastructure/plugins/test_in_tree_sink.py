import pytest

from protcellar.application.target_biology._import_support import ItemResult
from protcellar.infrastructure.plugins.in_tree_sink import InTreeSink


@pytest.mark.asyncio
async def test_routes_to_registered_upserter_and_accumulates() -> None:
    seen: list[list[object]] = []

    async def _fake(records):
        seen.append(list(records))
        return [ItemResult(index=0, status="created", id="abc")]

    sink = InTreeSink({"essentiality": _fake})
    out = await sink.upsert("essentiality", ["a", "b"])

    assert [r.status for r in out] == ["created"]
    assert sink.results == out  # accumulated for the run summary
    assert seen == [["a", "b"]]  # records handed straight to the upserter


@pytest.mark.asyncio
async def test_unknown_record_type_raises() -> None:
    sink = InTreeSink({})
    with pytest.raises(ValueError):
        await sink.upsert("nope", [])
