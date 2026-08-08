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

target_biology was the first context with genuinely tenant-owned rows: §1.5
is about reference data, but target-biology records are the private
observations this whole design exists to protect (``source_type`` has
``private_comm``/``internal``/``patent`` values, and ``Unpublished
Structure`` is a whole record type). Its cases demonstrate the full shape —
invisibility, not just non-mutability — for the first time.

Tagging (Task 5) is the second: tags are workspace-owned configuration, not
reference data (§1.5) — unlike every other entity this file tags against, a
tag is never created under ``SHARED_WORKSPACE_ID``, so its cases below use
the same invisibility shape target_biology established rather than the
read-only-shared-row shape taxonomy/protein_catalog use.

Imports (Task 6) is the third and last: an import run is a workspace
artifact, not reference data (§1.6's Migration B) — like tags, it is never
created under ``SHARED_WORKSPACE_ID``, so its case also uses the
invisibility shape.
"""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.imports.job_enqueuer import JobEnqueuer
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    EssentialityRecordModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import readable_by
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


async def test_workspace_essentiality_is_invisible_to_a_second_workspaces_bulk_list(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """Same property as the bundle case above, for the bulk list route (Task 9):
    a record workspace A creates must not appear when workspace B lists the
    same kind in bulk, even filtered to the exact gene id.
    """
    gene_id = uuid.uuid4()
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/essentiality",
        json=_ISOLATION_ESSENTIALITY_BODY,
    )
    assert created.status_code == 201, created.text

    listed = await other_workspace_client.get(
        f"/api/v1/target-biology/essentiality?gene_id={gene_id}"
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []


async def _save_private_gene(database_url: str, workspace_id: uuid.UUID, organism_id: str) -> Gene:
    """Seed a gene owned by a real (non-SHARED) workspace directly through the
    repository. ``POST /genes`` always writes SHARED (genes are reference
    data), so this is the only way a tenant-private gene exists at all today —
    exactly the gap Task 10's parent validation targets, and the premise the
    oracle test below needs.
    """
    engine = create_async_engine(database_url)
    uow = AsyncUnitOfWork(async_sessionmaker(engine, expire_on_commit=False))
    gene = Gene.create(
        workspace_id=workspace_id, primary_name="privateGene", organism_id=uuid.UUID(organism_id)
    )
    async with uow:
        await SQLAlchemyGeneRepository(uow).save(gene)
        await uow.commit()
    await engine.dispose()
    return gene


async def test_bulk_list_organism_filter_does_not_leak_another_workspaces_gene(
    client: AsyncClient,
    other_workspace_client: AsyncClient,
    database_url: str,
    workspace_id: uuid.UUID,
) -> None:
    """The organism_id/strain_id join (Task 9) reaches the record's parent gene
    — that join must be scoped the same as the record itself, or organism_id
    becomes a match/no-match oracle for a private gene's organism, a fact
    ``GET /genes/{id}`` correctly 404s on. Task 10 (parent validation on
    attach) hasn't landed, so nothing stops a caller from attaching a record
    to a gene_id it cannot see in the first place — that half of the gap is
    expected here and is Task 10's job; this test is only about whether the
    *bulk list*'s organism filter then leaks that gene's organism/strain.
    """
    organism_id = await _seed_shared_organism(client)
    # workspace_id is the fixture `client` itself authenticates as — a private
    # gene "belonging to" the victim, unreachable via any HTTP create path.
    victim_gene = await _save_private_gene(database_url, workspace_id, organism_id)

    # The attacker (other_workspace_client) attaches a record to a gene_id it
    # cannot see — allowed today (Task 10 not landed), not what's under test.
    attached = await other_workspace_client.post(
        f"/api/v1/genes/{victim_gene.id}/target-biology/essentiality",
        json=_ISOLATION_ESSENTIALITY_BODY,
    )
    assert attached.status_code == 201, attached.text

    # Its own record is visible by gene_id alone...
    by_gene = await other_workspace_client.get(
        f"/api/v1/target-biology/essentiality?gene_id={victim_gene.id}"
    )
    assert by_gene.status_code == 200, by_gene.text
    assert len(by_gene.json()["items"]) == 1

    # ...but organism_id must not turn into an oracle for the victim's private
    # gene: the parent join has to be scoped too, or this returns the item.
    by_organism = await other_workspace_client.get(
        f"/api/v1/target-biology/essentiality?gene_id={victim_gene.id}&organism_id={organism_id}"
    )
    assert by_organism.status_code == 200, by_organism.text
    assert by_organism.json()["items"] == []


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


async def test_owned_essentiality_bundle_marks_is_shared_false(client: AsyncClient) -> None:
    """The other half of the ``is_shared`` contract: a record the caller's
    own workspace created — neither hidden (unlike the second-workspace case
    above) nor marked shared. Reads only ever return the caller's own rows
    plus shared ones, so these two tests exhaust the states the field can be
    in on a bundle the caller can actually see.
    """
    gene_id = uuid.uuid4()
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/essentiality",
        json=_ISOLATION_ESSENTIALITY_BODY,
    )
    assert created.status_code == 201, created.text

    bundle = await client.get(f"/api/v1/genes/{gene_id}/target-biology")
    assert bundle.status_code == 200, bundle.text
    [item] = bundle.json()["essentiality"]
    assert item["is_shared"] is False


async def _save_shared_essentiality(database_url: str) -> Essentiality:
    """Seed a SHARED, published essentiality record directly through the
    repository, the same way ``test_target_biology.py``'s ``_save`` does —
    every HTTP create path now writes the caller's own workspace (see the
    module docstring), so there is no API route left that produces a shared
    record to test PATCH/DELETE against. Returns the saved record (not just
    its id) so a caller needing ``gene_id`` — e.g. to fetch its bundle — does
    not need a second, near-identical helper.
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
    return record


async def test_shared_essentiality_cannot_be_mutated(
    client: AsyncClient, database_url: str
) -> None:
    """A published (shared) target-biology record is reference data too:
    PATCH and DELETE 404 unconditionally, admin or not — the same rule as
    every other context, now also covering DELETE (organisms, genes and
    proteins have no delete route to test it against).
    """
    record = await _save_shared_essentiality(database_url)

    patched = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"classification": "non_essential"},
    )
    assert patched.status_code == 404, patched.text

    deleted = await client.delete(f"/api/v1/target-biology/essentiality/{record.id}")
    assert deleted.status_code == 404, deleted.text


async def test_shared_essentiality_bundle_marks_is_shared(
    client: AsyncClient, database_url: str
) -> None:
    """The client needs ``is_shared`` to hide the edit/provenance/delete
    controls it would otherwise offer in vain on a row whose mutations always
    404 (``test_shared_essentiality_cannot_be_mutated`` above). Asserts
    against the per-gene bundle rather than ``GET /target-biology/{kind}`` —
    that bulk route is Task 9's and does not exist on this branch yet.
    """
    record = await _save_shared_essentiality(database_url)

    bundle = await client.get(f"/api/v1/genes/{record.gene_id}/target-biology")
    assert bundle.status_code == 200, bundle.text
    [item] = bundle.json()["essentiality"]
    assert item["id"] == str(record.id)
    assert item["is_shared"] is True


async def test_workspace_essentiality_condition_does_not_leak_into_another_workspaces_schema(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """GET /target-biology/schema surfaces suggested free-text values via a
    process-wide singleton cache (SQLAlchemySuggestedValuesReader) — scoping
    its query alone is not enough, since a cache keyed by nothing would still
    hand workspace A's distinctive value to workspace B for the rest of the
    TTL window. ``internal`` provenance is exactly the private-observation
    case this whole plan protects.
    """
    distinctive_condition = f"isolation-condition-{uuid.uuid4()}"
    created = await client.post(
        f"/api/v1/genes/{uuid.uuid4()}/target-biology/essentiality",
        json={
            "classification": "essential",
            "condition": distinctive_condition,
            "provenance": {"source_type": "internal", "citations": []},
        },
    )
    assert created.status_code == 201, created.text

    schema = await other_workspace_client.get("/api/v1/target-biology/schema")
    assert schema.status_code == 200, schema.text
    condition_field = next(
        f for f in schema.json()["kinds"]["essentiality"]["fields"] if f["name"] == "condition"
    )
    assert distinctive_condition not in condition_field["suggested_values"]


# --- tagging: the second (and last) context with genuinely tenant-owned rows


async def _create_tag(client: AsyncClient, organism_id: str, key: str) -> str:
    """Create (and assign) a tag under ``client``'s own workspace via the
    per-entity assignment route — tags have no standalone create endpoint;
    ``AssignTag`` resolves the tag through ``get_or_create`` under the hood,
    scoped to the caller's workspace (assign_tag.py).
    """
    resp = await client.post(
        f"/api/v1/organisms/{organism_id}/tags", json={"key": key, "value": None}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_workspace_tag_is_invisible_to_a_second_workspace(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """A tag create lands in the caller's own workspace, never SHARED — tags
    are workspace-owned configuration (design doc §1.5), not reference data,
    unlike the shared organism it's attached to. Workspace B must not see a
    tag workspace A created, whether by listing tags directly or by reading
    the shared entity's tag list.
    """
    organism_id = await _seed_shared_organism(client)
    tag_id = await _create_tag(client, organism_id, f"isolation-tag-{uuid.uuid4()}")

    listed = await other_workspace_client.get("/api/v1/tags")
    assert listed.status_code == 200, listed.text
    assert tag_id not in {t["id"] for t in listed.json()}

    entity_tags = await other_workspace_client.get(f"/api/v1/organisms/{organism_id}/tags")
    assert entity_tags.status_code == 200, entity_tags.text
    assert entity_tags.json() == []


async def test_workspace_tag_cannot_be_renamed_merged_or_deleted_by_a_second_workspace(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    """Workspace B cannot rename, merge or delete a tag workspace A owns. 404
    on all three, not 403 — a 403 would confirm the row exists to a caller
    who cannot see it. Merge needs a target tag B actually owns, so the
    source lookup — the one this test cares about — is what has to 404.
    """
    organism_id = await _seed_shared_organism(client)
    tag_id = await _create_tag(client, organism_id, f"isolation-tag-{uuid.uuid4()}")
    b_tag_id = await _create_tag(
        other_workspace_client, organism_id, f"isolation-tag-b-{uuid.uuid4()}"
    )

    renamed = await other_workspace_client.patch(
        f"/api/v1/tags/{tag_id}", json={"key": "renamed", "value": None}
    )
    assert renamed.status_code == 404, renamed.text

    merged = await other_workspace_client.post(
        f"/api/v1/tags/{tag_id}/merge", json={"target_tag_id": b_tag_id}
    )
    assert merged.status_code == 404, merged.text

    deleted = await other_workspace_client.delete(f"/api/v1/tags/{tag_id}")
    assert deleted.status_code == 404, deleted.text


# --- imports: the third (and last) context with genuinely tenant-owned rows -


class _NoopEnqueuer:
    """Satisfies JobEnqueuer without touching Redis. These tests only care
    about DB-level visibility, not job execution — same reasoning as
    ``test_imports_api.py``'s ``fake_enqueuer`` fixture, which every test
    that calls ``POST /imports`` in this codebase uses for the same reason.
    """

    async def enqueue_import(self, import_run_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        return None

    async def aclose(self) -> None:
        return None


def _skip_real_enqueue(app: FastAPI) -> None:
    """Swap JobEnqueuer for a no-op on ``app``'s container, in place."""
    cloned = app.state.container.clone()
    cloned.define(JobEnqueuer, lambda c: _NoopEnqueuer())
    app.state.container = cloned


async def test_workspace_import_run_is_invisible_to_a_second_workspace(
    client: AsyncClient, other_workspace_client: AsyncClient, api_app: FastAPI
) -> None:
    """An import run started by workspace A lands in the caller's own
    workspace, never SHARED — import runs are workspace artifacts (who ran
    what), not reference data, unlike the genes/proteins/organisms an import
    ultimately writes. Workspace B must not see it, by listing or by
    fetching it directly.
    """
    _skip_real_enqueue(api_app)
    proteome_id = f"UP{uuid.uuid4().hex[:9].upper()}"
    created = await client.post(
        "/api/v1/imports",
        json={"import_type": "proteome", "params": {"proteome_id": proteome_id}},
    )
    assert created.status_code == 202, created.text
    run_id = created.json()["id"]

    listed = await other_workspace_client.get("/api/v1/imports")
    assert listed.status_code == 200, listed.text
    assert run_id not in {r["id"] for r in listed.json()["items"]}

    got = await other_workspace_client.get(f"/api/v1/imports/{run_id}")
    assert got.status_code == 404, got.text


# --- Migration B: the reclassification is what makes any of the above real ---

_RECLASSIFY_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "alembic/versions/d2b5f9c8e314_reclassify_workspaces.py"
)


def _load_reclassify_migration() -> object:
    """Import Migration B by file path, the same way Alembic itself loads
    version files (they are not a package). Loading the real module — rather
    than a copy of its SQL — is what makes this a regression test for the
    migration and not just for the ``readable_by`` predicate Task 1 already
    covers.
    """
    spec = importlib.util.spec_from_file_location(
        "_migration_d2b5f9c8e314", _RECLASSIFY_MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_migration_reclassifies_private_provenance_but_not_published(
    database_url: str, _run_migrations: None
) -> None:
    """The property Migration B exists for: once it runs, a private-provenance
    record is no longer readable by a workspace that isn't its new owner,
    while a published one stays readable by everyone — mirroring the one real
    row (a ``private_comm`` vulnerability) this migration moves in production.

    Runs the actual migration module inside a transaction rolled back at the
    end. `_run_migrations` (requested explicitly — this test has no other
    fixture that would pull the schema in, unlike every other test in this
    file) already applied it once, session-wide, before any row existed to
    reclassify; calling `upgrade()` unscoped a second time against the live
    session database would sweep every other test's SHARED-workspace row too
    (e.g. test_target_biology.py's INTERNAL-provenance UnpublishedStructure) —
    the rollback is what keeps this test from disturbing them, not test file
    ordering.
    """
    migration = _load_reclassify_migration()
    other_workspace = uuid.uuid4()
    published_id, published_gene = uuid.uuid4(), uuid.uuid4()
    private_id, private_gene = uuid.uuid4(), uuid.uuid4()

    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(
                insert(EssentialityRecordModel),
                [
                    {
                        "id": published_id,
                        "workspace_id": SHARED_WORKSPACE_ID,
                        "gene_id": published_gene,
                        "classification": "essential",
                        "provenance": {"source_type": "published", "citations": []},
                        "version": 1,
                    },
                    {
                        "id": private_id,
                        "workspace_id": SHARED_WORKSPACE_ID,
                        "gene_id": private_gene,
                        "classification": "essential",
                        "provenance": {"source_type": "internal", "citations": []},
                        "version": 1,
                    },
                ],
            )

            def _run_upgrade(sync_conn):  # type: ignore[no-untyped-def]
                ctx = MigrationContext.configure(sync_conn)
                with Operations.context(ctx):
                    migration.upgrade()  # type: ignore[attr-defined]

            await conn.run_sync(_run_upgrade)

            visible = await conn.execute(
                select(EssentialityRecordModel.id).where(
                    EssentialityRecordModel.id.in_([published_id, private_id]),
                    readable_by(EssentialityRecordModel, other_workspace),
                )
            )
            visible_ids = {row[0] for row in visible}
        finally:
            await trans.rollback()
    await engine.dispose()

    assert published_id in visible_ids
    assert private_id not in visible_ids
