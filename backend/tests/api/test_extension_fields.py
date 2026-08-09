"""API tests for the extension-field registry (admin CRUD)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_admin_can_declare_a_field(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/extension-fields",
        json={
            "kind": "vulnerability",
            "name": "vi_lower_bound",
            "label": "VI lower bound",
            "field_type": "number",
            "options": None,
            "position": 0,
            "show_in_table": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "vi_lower_bound"
    assert body["version"] == 1


async def test_duplicate_name_for_a_kind_conflicts(client: AsyncClient) -> None:
    body = {
        "kind": "hypomorph",
        "name": "phenotype",
        "label": "Phenotype",
        "field_type": "string",
        "options": None,
        "position": 0,
        "show_in_table": False,
    }
    assert (await client.post("/api/v1/extension-fields", json=body)).status_code == 201
    assert (await client.post("/api/v1/extension-fields", json=body)).status_code == 409


async def test_same_name_on_a_different_kind_is_fine(client: AsyncClient) -> None:
    for kind in ("essentiality", "vulnerability"):
        r = await client.post(
            "/api/v1/extension-fields",
            json={
                "kind": kind,
                "name": "note_code",
                "label": "Note code",
                "field_type": "string",
                "options": None,
                "position": 0,
                "show_in_table": False,
            },
        )
        assert r.status_code == 201, r.text


async def test_name_cannot_be_changed(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/extension-fields",
        json={
            "kind": "vulnerability",
            "name": "bin",
            "label": "Bin",
            "field_type": "string",
            "options": None,
            "position": 0,
            "show_in_table": False,
        },
    )
    fid = created.json()["id"]
    resp = await client.patch(f"/api/v1/extension-fields/{fid}", json={"name": "bin_v2"})
    assert resp.status_code == 422, resp.text


async def test_unknown_kind_is_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/extension-fields",
        json={
            "kind": "nonsense",
            "name": "x",
            "label": "X",
            "field_type": "string",
            "options": None,
            "position": 0,
            "show_in_table": False,
        },
    )
    assert resp.status_code == 422


async def test_a_second_workspace_sees_none_of_it(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    await client.post(
        "/api/v1/extension-fields",
        json={
            "kind": "vulnerability",
            "name": "isolation_probe",
            "label": "Probe",
            "field_type": "string",
            "options": None,
            "position": 0,
            "show_in_table": False,
        },
    )
    theirs = await other_workspace_client.get("/api/v1/extension-fields?kind=vulnerability")
    assert theirs.status_code == 200
    assert [f["name"] for f in theirs.json()] == []


async def test_update_changes_only_the_provided_fields(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/extension-fields",
        json={
            "kind": "vulnerability",
            "name": "risk_tier",
            "label": "Risk tier",
            "field_type": "enum",
            "options": ["low", "high"],
            "position": 2,
            "show_in_table": True,
        },
    )
    fid = created.json()["id"]

    # A label-only patch must not disturb field_type/options/position/show_in_table —
    # ExtensionFieldDef.update() is total, so the use case has to read the current
    # values off the loaded aggregate for everything the request didn't send.
    resp = await client.patch(f"/api/v1/extension-fields/{fid}", json={"label": "Risk tier v2"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["label"] == "Risk tier v2"
    assert body["field_type"] == "enum"
    assert body["options"] == ["low", "high"]
    assert body["position"] == 2
    assert body["show_in_table"] is True
    assert body["version"] == 2


async def test_delete_removes_it(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/extension-fields",
        json={
            "kind": "hypomorph",
            "name": "to_delete",
            "label": "To delete",
            "field_type": "boolean",
            "options": None,
            "position": 0,
            "show_in_table": False,
        },
    )
    fid = created.json()["id"]

    assert (await client.delete(f"/api/v1/extension-fields/{fid}")).status_code == 204
    assert (await client.delete(f"/api/v1/extension-fields/{fid}")).status_code == 404

    listed = await client.get("/api/v1/extension-fields?kind=hypomorph")
    assert "to_delete" not in [f["name"] for f in listed.json()]


async def test_editor_cannot_create_a_field_def(editor_client: AsyncClient) -> None:
    resp = await editor_client.post(
        "/api/v1/extension-fields",
        json={
            "kind": "vulnerability",
            "name": "nope",
            "label": "Nope",
            "field_type": "string",
            "options": None,
            "position": 0,
            "show_in_table": False,
        },
    )
    assert resp.status_code == 403
