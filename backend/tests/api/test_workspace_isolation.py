"""Cross-tenant isolation. These are the security tests; keep them in one file.

Each context adds its own case as it is converted. The general shape: a row
owned by workspace B must be invisible to workspace A, and a shared row must
be readable by both and mutable by neither.

Taxonomy and protein_catalog could only demonstrate half of that shape.
Organisms, strains, proteomes, genes and proteins are all reference data
(``docs/superpowers/specs/2026-08-08-workspace-scoping-design.md`` §1.5):
every create path — including the plain ``POST /organisms`` and
``POST /genes`` — writes ``SHARED_WORKSPACE_ID`` regardless of caller, so no
tenant-owned row of theirs ever exists to prove "invisible to a different
workspace" against. What those two contexts *can* and do demonstrate here: a
shared row is readable by more than one workspace, and mutable by none.

target_biology (this task) is the first context with genuinely tenant-owned
rows: §1.5 is about reference data, but target-biology records are the
private observations this whole design exists to protect (``source_type``
has ``private_comm``/``internal``/``patent`` values, and ``Unpublished
Structure`` is a whole record type). Its cases below demonstrate the full
shape — invisibility, not just non-mutability — for the first time. Tagging
(Task 5) is the one context left.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

# other_workspace_client (a second API client under a distinct workspace) lives
# in tests/api/conftest.py — shared with test_tag_filter.py and, per the
# workspace-scoping plan, every context Tasks 3-6 add here.

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


async def _seed_shared_gene(client: AsyncClient) -> str:
    """Create a gene via the plain create route. Unlike organisms, genes carry
    no natural-key conflict to dodge, and every create path writes SHARED
    regardless of caller (create_gene.py), so the plain POST suffices.
    """
    organism_id = await _seed_shared_organism(client)
    resp = await client.post(
        "/api/v1/genes",
        json={"primary_name": "isolationTestus", "organism_id": organism_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_shared_gene_is_readable_by_a_second_workspace(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """A gene created under one workspace's call is still visible to another —
    protein_catalog's proof of the same readable-by-all rule taxonomy already
    established for organisms.
    """
    gene_id = await _seed_shared_gene(client)

    resp = await other_workspace_client.get(f"/api/v1/genes/{gene_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == gene_id


async def test_shared_gene_cannot_be_mutated(client: AsyncClient) -> None:
    """Genes are reference data too: PATCH 404s unconditionally, admin or not."""
    gene_id = await _seed_shared_gene(client)

    resp = await client.patch(f"/api/v1/genes/{gene_id}", json={"hgnc_id": "HGNC:QA-TEMP"})
    assert resp.status_code == 404, resp.text


_ISOLATION_PROTEIN_ACCESSION = "P0DDT9"
_SHARED_PROTEIN_RECORD = {
    "primary_accession": _ISOLATION_PROTEIN_ACCESSION,
    "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDA",
    "is_reviewed": True,
    "source": "uniprot",
    "source_release": "isolation-test",
    "source_record_id": "workspace-isolation-fixture-protein",
    "source_record_checksum": "workspace-isolation-fixture-protein-checksum",
}


async def _seed_shared_protein(client: AsyncClient) -> str:
    """Create (or reuse) one SHARED_WORKSPACE_ID protein via the bulk-import
    endpoint — same reasoning as ``_seed_shared_organism``: unlike
    create_gene.py, create_protein.py's plain POST has a primary_accession
    dedupe check, so calling it twice from different tests would 409;
    bulk-import is idempotent on checksum instead. Returns the accession
    (proteins are looked up by accession, not id).
    """
    organism_id = await _seed_shared_organism(client)
    resp = await client.post(
        "/api/v1/proteins/bulk",
        json={"records": [{**_SHARED_PROTEIN_RECORD, "organism_id": organism_id}]},
    )
    assert resp.status_code == 200, resp.text
    return _ISOLATION_PROTEIN_ACCESSION


async def test_shared_protein_is_readable_by_a_second_workspace(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """Same proof as the gene case, on the other protein_catalog aggregate —
    find_owned_by_accession is a distinct code path from find_by_accession
    (Protein has no id-based find_readable/find_owned pair the way Gene does),
    so genes passing this shape says nothing about proteins.
    """
    accession = await _seed_shared_protein(client)

    resp = await other_workspace_client.get(f"/api/v1/proteins/{accession}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["primary_accession"] == accession


async def test_shared_protein_cannot_be_mutated(client: AsyncClient) -> None:
    """Proteins are reference data too: PATCH 404s unconditionally, admin or
    not — regression coverage for find_owned_by_accession specifically:
    reverting update_protein.py to the read-scoped find_by_accession would
    pass every other test in this file but fail this one.
    """
    accession = await _seed_shared_protein(client)

    resp = await client.patch(f"/api/v1/proteins/{accession}", json={"is_reviewed": False})
    assert resp.status_code == 404, resp.text


# --- target_biology: the first context with a genuinely tenant-owned row ----

_ISOLATION_ESSENTIALITY_BODY = {
    "classification": "essential",
    "provenance": {"source_type": "internal", "citations": []},
}


async def test_workspace_essentiality_is_invisible_to_a_second_workspace(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """A target-biology create lands in the caller's own workspace, not
    SHARED — the headline property this whole ten-task plan exists to prove.
    A record workspace A creates must not appear in workspace B's view of the
    same gene, even though the gene id itself is shared and visible to both.
    """
    gene_id = uuid.uuid4()
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/essentiality",
        json=_ISOLATION_ESSENTIALITY_BODY,
    )
    assert created.status_code == 201, created.text

    bundle = await other_workspace_client.get(f"/api/v1/genes/{gene_id}/target-biology")
    assert bundle.status_code == 200, bundle.text
    assert bundle.json()["essentiality"] == []


async def test_workspace_essentiality_cannot_be_mutated_by_a_second_workspace(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """Workspace B cannot PATCH or DELETE a record workspace A created. 404
    on both, not 403 — a 403 would confirm the row exists to a caller who
    cannot see it.
    """
    gene_id = uuid.uuid4()
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/essentiality",
        json=_ISOLATION_ESSENTIALITY_BODY,
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    patched = await other_workspace_client.patch(
        f"/api/v1/target-biology/essentiality/{record_id}",
        json={"classification": "non_essential"},
    )
    assert patched.status_code == 404, patched.text

    deleted = await other_workspace_client.delete(
        f"/api/v1/target-biology/essentiality/{record_id}"
    )
    assert deleted.status_code == 404, deleted.text


async def _save_shared_essentiality(database_url: str) -> uuid.UUID:
    """Seed a SHARED, published essentiality record directly through the
    repository, the same way ``test_target_biology.py``'s ``_save`` does —
    every HTTP create path now writes the caller's own workspace (see the
    module docstring), so there is no API route left that produces a shared
    record to test PATCH/DELETE against.
    """
    engine = create_async_engine(database_url)
    uow = AsyncUnitOfWork(async_sessionmaker(engine, expire_on_commit=False))
    record = Essentiality(
        workspace_id=SHARED_WORKSPACE_ID,
        gene_id=uuid.uuid4(),
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
    )
    async with uow:
        await SQLAlchemyEssentialityRepository(uow).save(record)
        await uow.commit()
    await engine.dispose()
    return record.id


async def test_shared_essentiality_cannot_be_mutated(
    client: AsyncClient, database_url: str
) -> None:
    """A published (shared) target-biology record is reference data too:
    PATCH and DELETE 404 unconditionally, admin or not — the same rule as
    every other context, now also covering DELETE (organisms, genes and
    proteins have no delete route to test it against).
    """
    record_id = await _save_shared_essentiality(database_url)

    patched = await client.patch(
        f"/api/v1/target-biology/essentiality/{record_id}",
        json={"classification": "non_essential"},
    )
    assert patched.status_code == 404, patched.text

    deleted = await client.delete(f"/api/v1/target-biology/essentiality/{record_id}")
    assert deleted.status_code == 404, deleted.text
