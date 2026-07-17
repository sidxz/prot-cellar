import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_list_plugins_includes_dejesus(client) -> None:
    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    manifests = resp.json()
    dejesus = next(m for m in manifests if m["id"] == "dejesus_essentiality")
    assert dejesus["target_records"] == ["essentiality"]
    assert {p["key"] for p in dejesus["params"]} == {"organism_id", "upload", "condition"}
    assert dejesus["enabled"] is False  # opt-in: disabled until an admin enables it


async def test_unknown_plugin_run_is_404(client) -> None:
    resp = await client.post("/api/v1/plugins/nope/runs", json={"params": {}})
    assert resp.status_code == 404


async def test_missing_required_param_is_422(client) -> None:
    # organism_id + upload are required; omit them (validation runs before the enable gate).
    resp = await client.post("/api/v1/plugins/dejesus_essentiality/runs", json={"params": {}})
    assert resp.status_code == 422


async def test_enable_then_disable_reflected_in_list(client) -> None:
    r = await client.put("/api/v1/plugins/dejesus_essentiality/enabled", json={"enabled": True})
    assert r.status_code == 204
    resp = await client.get("/api/v1/plugins")
    dejesus = next(m for m in resp.json() if m["id"] == "dejesus_essentiality")
    assert dejesus["enabled"] is True

    r = await client.put("/api/v1/plugins/dejesus_essentiality/enabled", json={"enabled": False})
    assert r.status_code == 204
    resp = await client.get("/api/v1/plugins")
    dejesus = next(m for m in resp.json() if m["id"] == "dejesus_essentiality")
    assert dejesus["enabled"] is False


async def test_run_blocked_when_plugin_not_enabled(client) -> None:
    # Params pass manifest validation, but the plugin is not enabled -> 403.
    resp = await client.post(
        "/api/v1/plugins/dejesus_essentiality/runs",
        json={"params": {"organism_id": str(uuid.uuid4()), "upload": str(uuid.uuid4())}},
    )
    assert resp.status_code == 403


async def test_enable_unknown_plugin_is_404(client) -> None:
    resp = await client.put("/api/v1/plugins/nope/enabled", json={"enabled": True})
    assert resp.status_code == 404
