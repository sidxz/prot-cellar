"""API tests for tag-faceted filtering (`?tags=<id>&tag_logic=any|all`) on the
6 taggable entities' list endpoints.

One test per entity proves the ``any`` case (tag one of two entities, list
filtered by that tag returns only the tagged one); a single ``all`` case
(on targets) proves the two-tag intersection semantics, since the underlying
``tag_filter_subquery`` logic is shared across all six repos.

``test_genes_tag_filter_ignores_foreign_workspace_tag`` covers the
workspace-scope guard: genes are global reference data (visible from every
workspace), but a *tag* belongs to exactly one workspace — filtering by a tag
id that belongs to a different workspace must not leak the tagged entity.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.conftest import _create_test_app
from tests.fakes.fake_auth import FakeAuth


async def _organism(client: AsyncClient, tax_id: int) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": tax_id,
            "rank": "species",
            "scientific_name": f"Tagfiltera testa {tax_id}",
        },
    )
    if resp.status_code == 409:
        return (await client.get(f"/api/v1/organisms/resolve/{tax_id}")).json()["id"]
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _protein(client: AsyncClient, organism_id: str, accession: str) -> str:
    resp = await client.post(
        "/api/v1/proteins",
        json={
            "primary_accession": accession,
            "organism_id": organism_id,
            "sequence": "MKTAYIAKQR",
            "is_reviewed": True,
        },
    )
    if resp.status_code == 409:
        return (await client.get(f"/api/v1/proteins/{accession}")).json()["id"]
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _tag(client: AsyncClient, collection: str, entity_id: str, key: str) -> str:
    resp = await client.post(f"/api/v1/{collection}/{entity_id}/tags", json={"key": key})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture
async def other_workspace_client(
    database_url: str, _run_migrations: None
) -> AsyncIterator[AsyncClient]:
    """A second API client hitting the same DB, but under a different workspace
    from ``client`` — used to prove a tag created in one workspace cannot be
    used to filter entities from another.
    """
    other_auth = FakeAuth(role="admin", workspace_id=uuid.uuid4())
    app = _create_test_app(database_url, other_auth)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    engine = app.state.container[AsyncEngine]
    await engine.dispose()


@pytest.mark.asyncio
async def test_targets_tag_filter_any(client: AsyncClient) -> None:
    organism_id = await _organism(client, 993001)
    p1 = await _protein(client, organism_id, "P90001")
    p2 = await _protein(client, organism_id, "P90002")

    t1 = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "Tagged Target",
            "target_type": "single_protein",
            "components": [{"protein_id": p1, "relationship": "single_protein"}],
        },
    )
    assert t1.status_code == 201
    t1_id = t1.json()["id"]

    t2 = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "Untagged Target",
            "target_type": "single_protein",
            "components": [{"protein_id": p2, "relationship": "single_protein"}],
        },
    )
    assert t2.status_code == 201
    t2_id = t2.json()["id"]

    tag_id = await _tag(client, "targets", t1_id, "hot")

    resp = await client.get("/api/v1/targets", params={"tags": tag_id})
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()["items"]}
    assert ids == {t1_id}
    assert t2_id not in ids


@pytest.mark.asyncio
async def test_targets_tag_filter_all_requires_every_tag(client: AsyncClient) -> None:
    organism_id = await _organism(client, 993002)
    p1 = await _protein(client, organism_id, "P90003")
    p2 = await _protein(client, organism_id, "P90004")

    both = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "Both Tags Target",
            "target_type": "single_protein",
            "components": [{"protein_id": p1, "relationship": "single_protein"}],
        },
    )
    assert both.status_code == 201
    both_id = both.json()["id"]

    one = await client.post(
        "/api/v1/targets",
        json={
            "pref_name": "One Tag Target",
            "target_type": "single_protein",
            "components": [{"protein_id": p2, "relationship": "single_protein"}],
        },
    )
    assert one.status_code == 201
    one_id = one.json()["id"]

    tag_a = await _tag(client, "targets", both_id, "alpha")
    tag_b = await _tag(client, "targets", both_id, "beta")
    await _tag(client, "targets", one_id, "alpha")

    # any: both targets carry "alpha", so both come back
    any_resp = await client.get(
        "/api/v1/targets", params={"tags": [tag_a, tag_b], "tag_logic": "any"}
    )
    assert any_resp.status_code == 200
    any_ids = {t["id"] for t in any_resp.json()["items"]}
    assert any_ids == {both_id, one_id}

    # all: only the target carrying BOTH tags comes back
    all_resp = await client.get(
        "/api/v1/targets", params={"tags": [tag_a, tag_b], "tag_logic": "all"}
    )
    assert all_resp.status_code == 200
    all_ids = {t["id"] for t in all_resp.json()["items"]}
    assert all_ids == {both_id}


@pytest.mark.asyncio
async def test_genes_tag_filter_any(client: AsyncClient) -> None:
    organism_id = await _organism(client, 993003)

    g1 = await client.post(
        "/api/v1/genes",
        json={"primary_name": "TAGF1", "organism_id": organism_id},
    )
    assert g1.status_code == 201
    g1_id = g1.json()["id"]

    g2 = await client.post(
        "/api/v1/genes",
        json={"primary_name": "TAGF2", "organism_id": organism_id},
    )
    assert g2.status_code == 201
    g2_id = g2.json()["id"]

    tag_id = await _tag(client, "genes", g1_id, "hot")

    resp = await client.get("/api/v1/genes", params={"tags": tag_id})
    assert resp.status_code == 200
    ids = {g["id"] for g in resp.json()["items"]}
    assert ids == {g1_id}
    assert g2_id not in ids


@pytest.mark.asyncio
async def test_strains_tag_filter_any(client: AsyncClient) -> None:
    species_id = await _organism(client, 993004)

    s1 = await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_id, "name": "Tagfilter strain 1"},
    )
    assert s1.status_code == 201
    s1_id = s1.json()["id"]

    s2 = await client.post(
        "/api/v1/strains",
        json={"species_organism_id": species_id, "name": "Tagfilter strain 2"},
    )
    assert s2.status_code == 201
    s2_id = s2.json()["id"]

    tag_id = await _tag(client, "strains", s1_id, "hot")

    resp = await client.get("/api/v1/strains", params={"tags": tag_id})
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()["items"]}
    assert ids == {s1_id}
    assert s2_id not in ids


@pytest.mark.asyncio
async def test_proteomes_tag_filter_any(client: AsyncClient) -> None:
    organism_id = await _organism(client, 993005)

    pr1 = await client.post(
        "/api/v1/proteomes",
        json={
            "uniprot_proteome_id": "UP900000001",
            "organism_id": organism_id,
            "proteome_type": "reference",
            "is_reference": True,
        },
    )
    assert pr1.status_code == 201
    pr1_id = pr1.json()["id"]

    pr2 = await client.post(
        "/api/v1/proteomes",
        json={
            "uniprot_proteome_id": "UP900000002",
            "organism_id": organism_id,
            "proteome_type": "reference",
            "is_reference": False,
        },
    )
    assert pr2.status_code == 201
    pr2_id = pr2.json()["id"]

    tag_id = await _tag(client, "proteomes", pr1_id, "hot")

    resp = await client.get("/api/v1/proteomes", params={"tags": tag_id})
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()["items"]}
    assert ids == {pr1_id}
    assert pr2_id not in ids


@pytest.mark.asyncio
async def test_organisms_tag_filter_any(client: AsyncClient) -> None:
    org1 = await _organism(client, 993006)
    org2 = await _organism(client, 993007)

    tag_id = await _tag(client, "organisms", org1, "hot")

    resp = await client.get("/api/v1/organisms", params={"tags": tag_id})
    assert resp.status_code == 200
    ids = {o["id"] for o in resp.json()["items"]}
    assert ids == {org1}
    assert org2 not in ids


@pytest.mark.asyncio
async def test_proteins_tag_filter_any(client: AsyncClient) -> None:
    organism_id = await _organism(client, 993008)
    p1 = await _protein(client, organism_id, "P90005")
    p2 = await _protein(client, organism_id, "P90006")

    tag_id = await _tag(client, "proteins", p1, "hot")

    resp = await client.get("/api/v1/proteins", params={"tags": tag_id})
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()["items"]}
    assert ids == {p1}
    assert p2 not in ids


@pytest.mark.asyncio
async def test_genes_tag_filter_ignores_foreign_workspace_tag(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """Genes are global reference data — visible from every workspace's
    listing — but a tag belongs to exactly one workspace. Filtering by a tag
    id that belongs to a *different* workspace must not surface the gene:
    the foreign tag id is ignored rather than honored via the shared link row.
    """
    organism_id = await _organism(client, 993009)

    g = await client.post(
        "/api/v1/genes",
        json={"primary_name": "TAGF3", "organism_id": organism_id},
    )
    assert g.status_code == 201, g.text
    g_id = g.json()["id"]

    # Tag created + assigned in workspace A ("client").
    tag_id = await _tag(client, "genes", g_id, "workspace-a-secret")

    # Sanity: workspace B *can* see the gene unfiltered — it's global reference data.
    unfiltered = await other_workspace_client.get(
        "/api/v1/genes", params={"organism_id": organism_id}
    )
    assert unfiltered.status_code == 200
    assert g_id in {gn["id"] for gn in unfiltered.json()["items"]}

    # But filtering by workspace A's tag id, from workspace B, must not leak the gene.
    resp = await other_workspace_client.get(
        "/api/v1/genes", params={"organism_id": organism_id, "tags": tag_id}
    )
    assert resp.status_code == 200
    ids = {gn["id"] for gn in resp.json()["items"]}
    assert g_id not in ids
