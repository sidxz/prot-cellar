"""Cross-tenant isolation. These are the security tests; keep them in one file.

Each context adds its own case as it is converted. The general shape: a row
owned by workspace B must be invisible to workspace A, and a shared row must
be readable by both and mutable by neither.

Taxonomy (this file's first contributor) can only demonstrate half of that
shape. Organisms, strains and proteomes are reference data
(``docs/superpowers/specs/2026-08-08-workspace-scoping-design.md`` §1.5):
every create path — including the plain ``POST /organisms`` — writes
``SHARED_WORKSPACE_ID`` regardless of caller, so no tenant-owned organism
ever exists to prove "invisible to a different workspace" against. That case
belongs to Tasks 4 and 5 (target_biology, tagging), whose contexts have rows
a single workspace actually owns. What taxonomy *can* and does demonstrate
here: a shared row is readable by more than one workspace, and mutable by
none.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.conftest import _create_test_app
from tests.fakes.fake_auth import FakeAuth

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


@pytest.fixture
async def other_workspace_client(
    database_url: str, _run_migrations: None
) -> AsyncIterator[AsyncClient]:
    """A second API client on the same DB, under a workspace distinct from
    ``client`` — proves a shared row is readable from a workspace that had no
    hand in creating it, not just whichever one happened to seed it.

    Copied from ``tests/api/test_tag_filter.py``'s fixture of the same name
    rather than imported, so this file stays self-contained for Tasks 3-6 to
    extend; the shape is identical.
    """
    other_auth = FakeAuth(role="admin", workspace_id=uuid.uuid4())
    app = _create_test_app(database_url, other_auth)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    engine = app.state.container[AsyncEngine]
    await engine.dispose()


async def _seed_shared_organism(client: AsyncClient) -> str:
    """Create (or reuse) one SHARED_WORKSPACE_ID organism via the bulk-import
    endpoint. Every organism create path writes SHARED regardless of caller
    (see module docstring), so any of them would do; bulk-import is used here
    because it's idempotent on checksum, which keeps this helper safe to call
    from every test in the file without needing a fresh identifier each time.
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


async def test_shared_organism_is_readable_by_a_second_workspace(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """The same shared row, read by a workspace that had no hand in creating
    it — the case ``test_shared_organism_is_readable`` alone can't rule out,
    since one workspace reading what it just created proves nothing about
    sharing.
    """
    organism_id = await _seed_shared_organism(client)

    resp = await other_workspace_client.get(f"/api/v1/organisms/{organism_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == organism_id


async def test_shared_organism_cannot_be_mutated(client: AsyncClient) -> None:
    """Reference data is import-managed: no API caller may change it, admin or not."""
    organism_id = await _seed_shared_organism(client)

    resp = await client.patch(f"/api/v1/organisms/{organism_id}", json={"division": "QA-TEMP"})
    assert resp.status_code == 404, resp.text
