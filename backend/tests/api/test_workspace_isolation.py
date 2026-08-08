"""Cross-tenant isolation. These are the security tests; keep them in one file.

Each context adds its own case as it is converted. The shape is always the same:
a row owned by workspace B must be invisible to workspace A, and a shared row
must be readable by both and mutable by neither.
"""

from __future__ import annotations

from httpx import AsyncClient

_SHARED_ORGANISM_RECORD = {
    # No ncbi_tax_id — Postgres treats multiple NULLs as distinct, so this
    # can't collide with another test's tax id under ix_organisms_ncbi_tax_id.
    "ncbi_tax_id": None,
    "rank": "no rank",
    "scientific_name": "Isolation testus",
    "source": "ncbi",
    "source_release": "isolation-test",
    "source_record_id": "workspace-isolation-fixture",
    "source_record_checksum": "workspace-isolation-fixture-checksum",
}


async def _seed_shared_organism(client: AsyncClient) -> str:
    """Create (or reuse) one SHARED_WORKSPACE_ID organism via the bulk-import
    endpoint — the only path that writes the shared workspace; a plain
    ``POST /organisms`` creates in the caller's own workspace instead. Bulk
    upsert is idempotent on checksum, so calling this from every test in the
    file is safe and keeps each test independent of run order.
    """
    resp = await client.post("/api/v1/organisms/bulk", json={"records": [_SHARED_ORGANISM_RECORD]})
    assert resp.status_code == 200, resp.text
    return resp.json()["results"][0]["id"]


async def test_shared_organism_is_readable(client: AsyncClient) -> None:
    """Reference data stays visible to every workspace after scoping."""
    await _seed_shared_organism(client)

    resp = await client.get("/api/v1/organisms")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) > 0


async def test_shared_organism_cannot_be_mutated(client: AsyncClient) -> None:
    """Reference data is import-managed: no API caller may change it, admin or not."""
    organism_id = await _seed_shared_organism(client)

    resp = await client.patch(f"/api/v1/organisms/{organism_id}", json={"division": "QA-TEMP"})
    assert resp.status_code == 404, resp.text
