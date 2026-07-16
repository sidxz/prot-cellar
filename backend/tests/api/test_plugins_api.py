import pytest

pytestmark = pytest.mark.asyncio


async def test_list_plugins_includes_dejesus(client) -> None:
    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    manifests = resp.json()
    dejesus = next(m for m in manifests if m["id"] == "dejesus_essentiality")
    assert dejesus["target_records"] == ["essentiality"]
    assert {p["key"] for p in dejesus["params"]} == {"organism_id", "upload", "condition"}


async def test_unknown_plugin_run_is_404(client) -> None:
    resp = await client.post("/api/v1/plugins/nope/runs", json={"params": {}})
    assert resp.status_code == 404


async def test_missing_required_param_is_422(client) -> None:
    # organism_id + upload are required; omit them.
    resp = await client.post("/api/v1/plugins/dejesus_essentiality/runs", json={"params": {}})
    assert resp.status_code == 422
