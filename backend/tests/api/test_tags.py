"""API tests for tag management + per-entity assignment routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient, tax_id: int) -> str:
    """Create a fresh organism — the simplest taggable entity.

    ``ncbi_tax_id`` is deliberately omitted. Organisms now save under the
    caller's own workspace (create_organism.py), but the tax-id dedupe check
    in that use case is still global — a tax id reused by another test file
    would 409 and resolve to an organism owned by an unrelated workspace,
    which then fails the tag-assignment "global-or-mine" ownership check.
    Tagging doesn't care what identifies the organism, so skip the dedupe
    path entirely rather than hunt for a tax id no other file has claimed.
    """
    resp = await client.post(
        "/api/v1/organisms",
        json={"rank": "species", "scientific_name": f"Testus organismus {tax_id}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_assign_tag_then_get_lists_it(client: AsyncClient) -> None:
    organism_id = await _organism(client, 990001)

    resp = await client.post(
        f"/api/v1/organisms/{organism_id}/tags",
        json={"key": "priority", "value": "high"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["key"] == "priority"
    assert body["value"] == "high"
    tag_id = body["id"]

    got = await client.get(f"/api/v1/organisms/{organism_id}/tags")
    assert got.status_code == 200
    tags = got.json()
    assert len(tags) == 1
    assert tags[0]["id"] == tag_id
    assert tags[0]["key"] == "priority"
    assert tags[0]["assigned_by"] is not None
    assert tags[0]["assigned_at"] is not None


@pytest.mark.asyncio
async def test_set_entity_tags_reconciles(client: AsyncClient) -> None:
    organism_id = await _organism(client, 990002)

    await client.post(f"/api/v1/organisms/{organism_id}/tags", json={"key": "a"})

    put_resp = await client.put(
        f"/api/v1/organisms/{organism_id}/tags",
        json={"tags": [{"key": "b"}, {"key": "c", "value": "1"}]},
    )
    assert put_resp.status_code == 200
    assert {t["key"] for t in put_resp.json()} == {"b", "c"}

    got = await client.get(f"/api/v1/organisms/{organism_id}/tags")
    got_keys = {t["key"] for t in got.json()}
    assert got_keys == {"b", "c"}  # "a" was removed, "b"/"c" added


@pytest.mark.asyncio
async def test_unassign_tag_removes_it(client: AsyncClient) -> None:
    organism_id = await _organism(client, 990003)

    assigned = await client.post(f"/api/v1/organisms/{organism_id}/tags", json={"key": "temp"})
    tag_id = assigned.json()["id"]

    del_resp = await client.delete(f"/api/v1/organisms/{organism_id}/tags/{tag_id}")
    assert del_resp.status_code == 204

    got = await client.get(f"/api/v1/organisms/{organism_id}/tags")
    assert all(t["id"] != tag_id for t in got.json())


@pytest.mark.asyncio
async def test_list_tags_search_finds_created_tag(client: AsyncClient) -> None:
    organism_id = await _organism(client, 990004)
    await client.post(
        f"/api/v1/organisms/{organism_id}/tags",
        json={"key": "uniquekeyxyz", "value": "v1"},
    )

    listed = await client.get("/api/v1/tags", params={"q": "uniquekeyxyz"})
    assert listed.status_code == 200
    assert any(t["key"] == "uniquekeyxyz" for t in listed.json())


@pytest.mark.asyncio
async def test_viewer_cannot_assign_tag(client: AsyncClient, viewer_client: AsyncClient) -> None:
    organism_id = await _organism(client, 990005)

    resp = await viewer_client.post(
        f"/api/v1/organisms/{organism_id}/tags",
        json={"key": "nope"},
    )
    assert resp.status_code == 403
