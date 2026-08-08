# Workspace Scoping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every row in prot-cellar owned by a real workspace and every read filter by it, so a record whose provenance says `private_comm` stops being readable by everyone — then add the bulk target-biology read and parent validation that the same visibility predicate makes possible.

**Architecture:** The tenancy machinery already exists and the Target context already uses it correctly; the other contexts opt out at ~70 call sites by passing a sentinel. This replaces the sentinel with a real shared-reference workspace, splits the repository's single lookup into a *readable* form (`IN (caller, shared)`) and an *owned* form (`== caller`), and moves each context onto `auth.workspace_id`. Reference data stays in one shared workspace rather than being duplicated per tenant.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, `returns` Result, pytest (`asyncio_mode = "auto"`), Next.js 15 + orval, biome, vitest.

**Spec:** `docs/superpowers/specs/2026-08-08-workspace-scoping-design.md`. Read §1.2 (the two predicates) and §6 (concurrent history) before Task 1.

## Global Constraints

- **Branch `feat/workspace-scoping`, based on `63ddcfb`.** Do not merge or rebase; do not touch `feat/target-biology-hardening`.
- **This branch has concurrent history. Specify changes as deltas against HEAD; never reproduce a surrounding function.** `10735a1` (another session's whole-branch review) changed `interface/routes/target_biology.py`, `domain/target_biology/essentiality.py`, `domain/target_biology/hypomorph.py` and `provenance-dialog.tsx`. In particular `_patch_updates`'s null branch now keeps `compound` (a null **clears** the reference) while `provenance` and `ligands` keep null-means-leave-alone. Rewriting that function from memory silently deletes a real fix that no test in this plan covers. **Open the file, change the lines you own, leave the rest.**
- **The two predicates are the security core.** Reads use `readable_by` (`IN (caller, shared)`); every mutation uses `owned_by` (`== caller`). Collapsing them lets any tenant edit reference data for every other tenant.
- **`save()` is not to be changed.** It is called by the ingestion paths with shared aggregates and cannot tell an import from an API call. Mutation safety comes from loading through `find_owned`.
- `SHARED_WORKSPACE_ID = uuid.UUID("a577f0f9-b1fb-53b6-be5d-49bcb500adeb")` — `uuid5(NAMESPACE_DNS, "shared.protcellar")`. Never the null UUID.
- `saclab-dev` is `442df0cf-e618-4938-a089-80ae2f1e43e7`. Migrations read it from a required `MIGRATION_TARGET_WORKSPACE_ID` env var with **no default**.
- mypy is strict; `ruff format` uses `line-length = 99`; `alembic/` is not in the lint path and its 34 migrations use the `typing.Sequence`/`Union` template style — match them.
- Verify with `make test` (unit + import-linter), `make test-api`, `make lint`, `make test-fe`, `make lint-fe`, `make migrate`.
- **Baseline failures — never treat as yours:** `make lint` stops at 3 pre-existing `E501` (`interface/app.py`, `tests/api/test_genes.py`, `tests/unit/.../test_bulk_upsert_genes.py`); `ruff format --check` has ~13 candidates; `mypy src` has 53 errors in 12 files, all the lagom `Container.define()` pattern; `make test-api` has 2 order-dependent failures (`test_organisms.py`, `test_plugin_run.py`). `make test` passes clean.
- Test fixtures already available: `client` (admin), `editor_client`, `viewer_client`, `database_url`, `admin_auth`. `tests/api/test_target_biology.py` defines `_save(database_url, repo_cls, aggregate)` and `WS`.
- **This service must remain unaware of any consumer.** The realm name is a Sentinel config fact; naming a downstream application in code you write is not.
- Dev is the only deployment and its data is re-importable. Write `downgrade()`, but do not build rollback tooling.
- Commit once per task.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/src/protcellar/domain/shared/global_workspace.py` | *Modify.* `GLOBAL_WORKSPACE_ID` → `SHARED_WORKSPACE_ID` with a new value. |
| `backend/src/protcellar/infrastructure/persistence/sqlalchemy/workspace_scope.py` | *Create.* The two predicates, and nothing else. SQLAlchemy-specific, so infrastructure, not domain. |
| `backend/src/protcellar/infrastructure/persistence/sqlalchemy/base_repository.py` | *Modify.* `find_by_id_in_workspace` → `find_readable` + `find_owned`. |
| `backend/alembic/versions/*_rename_sentinel_workspace.py` | *Create.* Migration A. |
| `backend/alembic/versions/*_reclassify_workspaces.py` | *Create.* Migration B. |
| The 6 list repositories | *Modify.* Apply `readable_by` in query builders. |
| Per-context application + domain files (Tasks 2–6) | *Modify.* Sentinel → `auth.workspace_id` or `SHARED_WORKSPACE_ID`. |
| `backend/src/protcellar/interface/routes/target_biology.py` | *Modify* (Tasks 4, 9, 10). **Has concurrent history.** |
| `backend/tests/api/test_workspace_isolation.py` | *Create.* The security tests, in one file rather than scattered. |

---

### Task 1: The shared workspace, the two predicates, and Migration A

**Files:**
- Modify: `backend/src/protcellar/domain/shared/global_workspace.py`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/workspace_scope.py`
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/base_repository.py`
- Create: `backend/alembic/versions/c1a4e8b7d203_rename_sentinel_workspace.py`
- Test: `backend/tests/unit/infrastructure/test_workspace_scope.py`

**Interfaces:**
- Produces: `SHARED_WORKSPACE_ID: uuid.UUID`; `readable_by(model, workspace_id)` and `owned_by(model, workspace_id)` returning SQLAlchemy predicates; `BaseRepository.find_readable(workspace_id, id) -> T | None` and `BaseRepository.find_owned(workspace_id, id) -> T | None`.
- Consumes: nothing.

**Why the constant and the migration ship together:** the new value is wrong until the data carries it, and the data is orphaned if it carries a value no code knows. Splitting them leaves a commit where every query looks for rows under an id nothing has.

- [ ] **Step 1: Write the failing predicate test**

Create `backend/tests/unit/infrastructure/test_workspace_scope.py`:

```python
"""The two predicates are the security core: reads see shared, mutations do not."""

from __future__ import annotations

import uuid

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    EssentialityRecordModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.workspace_scope import (
    owned_by,
    readable_by,
)


def test_shared_workspace_is_not_the_null_uuid() -> None:
    """A forgotten assignment must not silently mean 'visible to everyone'."""
    assert SHARED_WORKSPACE_ID != uuid.UUID(int=0)


def test_shared_workspace_id_is_stable() -> None:
    assert str(SHARED_WORKSPACE_ID) == "a577f0f9-b1fb-53b6-be5d-49bcb500adeb"


def test_readable_by_admits_the_caller_and_shared() -> None:
    ws = uuid.uuid4()
    rendered = str(readable_by(EssentialityRecordModel, ws).compile(
        compile_kwargs={"literal_binds": True}
    ))
    assert str(ws) in rendered
    assert str(SHARED_WORKSPACE_ID) in rendered


def test_owned_by_admits_only_the_caller() -> None:
    ws = uuid.uuid4()
    rendered = str(owned_by(EssentialityRecordModel, ws).compile(
        compile_kwargs={"literal_binds": True}
    ))
    assert str(ws) in rendered
    assert str(SHARED_WORKSPACE_ID) not in rendered
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/unit/infrastructure/test_workspace_scope.py -v`
Expected: FAIL — `ModuleNotFoundError` for `workspace_scope`, and `ImportError` for `SHARED_WORKSPACE_ID`.

- [ ] **Step 3: Rename the constant**

Replace the body of `domain/shared/global_workspace.py`:

```python
"""The workspace that owns shared reference data."""

from __future__ import annotations

import uuid

# Reference data (organisms, genes, proteins, proteomes) is shared across tenants.
# It is owned by this workspace rather than exempted from the tenancy check, so
# every read filters and no table is special-cased.
#
# Deliberately NOT the null UUID: that value is indistinguishable from "unset", so
# a forgotten assignment would make a row readable by everyone. With a distinct id
# the same mistake makes it readable by nobody — safe, and loud enough to find.
# Value is uuid5(NAMESPACE_DNS, "shared.protcellar").
SHARED_WORKSPACE_ID: uuid.UUID = uuid.UUID("a577f0f9-b1fb-53b6-be5d-49bcb500adeb")
```

Then rename every import and reference across `src`, `tests` and `scripts`. `GLOBAL_WORKSPACE_ID` must not survive anywhere — grep for it and expect zero hits. Semantics are unchanged at this step: every site still passes the shared id, so behaviour does not move.

- [ ] **Step 4: Write the predicates**

Create `infrastructure/persistence/sqlalchemy/workspace_scope.py`:

```python
"""The two workspace predicates. Reads and mutations use different ones.

Keeping these apart is the security core of the tenancy model. `readable_by`
admits shared reference data so every tenant can see it; `owned_by` does not, so
no tenant can mutate reference data for the others. Collapsing them into one
predicate would hand every workspace admin write access to every other tenant's
reference data — Sentinel exposes only per-workspace roles, so there is no
realm-admin concept that could make that safe.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.sql.elements import ColumnElement

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID


def readable_by(model: Any, workspace_id: uuid.UUID) -> ColumnElement[bool]:
    """Rows this workspace may read: its own, plus shared reference data."""
    predicate: ColumnElement[bool] = model.workspace_id.in_(
        (workspace_id, SHARED_WORKSPACE_ID)
    )
    return predicate


def owned_by(model: Any, workspace_id: uuid.UUID) -> ColumnElement[bool]:
    """Rows this workspace may mutate: its own only.

    Shared rows are excluded on purpose — reference data is import-managed.
    """
    predicate: ColumnElement[bool] = model.workspace_id == workspace_id
    return predicate
```

- [ ] **Step 5: Split the repository lookup**

In `base_repository.py`, replace `find_by_id_in_workspace` with two methods. Keep every other method — including `save()` — untouched.

```python
    async def find_readable(self, workspace_id: uuid.UUID, id: uuid.UUID) -> T | None:
        """Load an aggregate the workspace may READ: its own, or shared.

        Use for GET paths. Returns ``None`` when the row does not exist or
        belongs to a different workspace.
        """
        stmt = select(self.model_class).where(
            self.model_class.id == id,  # type: ignore[attr-defined]
            readable_by(self.model_class, workspace_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain_tracked(model)

    async def find_owned(self, workspace_id: uuid.UUID, id: uuid.UUID) -> T | None:
        """Load an aggregate the workspace may MUTATE: its own only.

        Use for update and delete paths. A shared row is deliberately not found,
        which is what makes reference data read-only through the API.
        """
        stmt = select(self.model_class).where(
            self.model_class.id == id,  # type: ignore[attr-defined]
            owned_by(self.model_class, workspace_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain_tracked(model)
```

Import both predicates at the top. Every existing caller of `find_by_id_in_workspace` must be pointed at one of the two — **GET use cases → `find_readable`; update/delete use cases → `find_owned`**. Grep for callers and decide each by whether it leads to a mutation. Leave `_owns`, `_find_by_id_unscoped` and the deprecated `find_by_id` exactly as they are.

- [ ] **Step 6: Run the unit test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/infrastructure/test_workspace_scope.py -v`
Expected: PASS.

- [ ] **Step 7: Write Migration A**

Create `backend/alembic/versions/c1a4e8b7d203_rename_sentinel_workspace.py`. The head at time of writing is `b3d7f1c9a204` (the json→jsonb migration) and that is what `down_revision` below carries — re-run `uv run alembic heads` and correct it if another migration has landed since. A pure value swap; no row changes owner and no read filters yet, so visibility is provably unchanged.

```python
"""rename the sentinel workspace to a distinct shared workspace id

Revision ID: c1a4e8b7d203
Revises: b3d7f1c9a204
Create Date: 2026-08-08 00:00:00.000000

The reserved sentinel was the null UUID, which is indistinguishable from an
unset column. Under a real tenancy check that is a leak waiting to happen: a
forgotten assignment would make the row readable by every tenant. Swap it for a
distinct id so the same mistake makes a row readable by nobody instead.

Pure value swap. No read path filters by workspace yet, so visibility is
unchanged by construction.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1a4e8b7d203'
down_revision: Union[str, None] = 'b3d7f1c9a204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = '00000000-0000-0000-0000-000000000000'
_NEW = 'a577f0f9-b1fb-53b6-be5d-49bcb500adeb'

# Every table carrying workspace_id. Taken from the live catalog, not the models:
#   SELECT c.relname FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
#    WHERE a.attname = 'workspace_id' AND c.relkind = 'r' AND NOT a.attisdropped;
_TABLES: list[str] = [
    "audit_operations",
    "essentiality_records",
    "crispri_strains",
    "vulnerability_records",
    "hypomorphs",
    "resistance_mutations",
    "protein_productions",
    "protein_activity_assays",
    "unpublished_structures",
    "genes",
    "proteins",
    "organisms",
    "strains",
    "proteomes",
    "targets",
    "tags",
    "import_runs",
    "import_uploads",
    "organizations",
]


def _swap(old: str, new: str) -> None:
    for table in _TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = :new WHERE workspace_id = :old"
            ).bindparams(new=new, old=old)
        )


def upgrade() -> None:
    _swap(_OLD, _NEW)


def downgrade() -> None:
    _swap(_NEW, _OLD)
```

Before writing `_TABLES`, run that catalog query against the dev database and reconcile — if it returns a table this list omits, the list is wrong, not the query.

- [ ] **Step 8: Apply the migration and verify no row is left behind**

```bash
make migrate
docker compose exec -T postgres psql -U protcellar -d protcellar -t -A -c \
  "SELECT count(*) FROM genes WHERE workspace_id = '00000000-0000-0000-0000-000000000000';"
```
Expected: `0`. Repeat for `proteins` and `essentiality_records`, and confirm each now shows the new id.

- [ ] **Step 9: Verify nothing regressed**

Run: `make test && make test-api && make lint`
Expected: unit + import-linter clean; API at the known 2 pre-existing failures and no others; lint at its 3 pre-existing `E501`.

- [ ] **Step 10: Commit**

```bash
git add backend/src/protcellar backend/alembic backend/tests scripts 2>/dev/null; \
git commit -m "feat(tenancy): a distinct shared workspace, and the two predicates

The reserved sentinel was the null UUID — indistinguishable from an unset
column, so under a real tenancy check a forgotten assignment would make a row
readable by every tenant rather than none.

Splits the repository's single scoped lookup into find_readable (the caller's
rows plus shared) and find_owned (the caller's rows only). Reads use the first,
mutations the second; that separation is what stops a tenant editing reference
data for everyone else.

Migration ships with the constant because the two are only correct together.
No read path filters yet, so visibility is unchanged."
```

---

### Tasks 2–6: Move each context onto the caller's workspace

These five tasks share one shape. **Task 2 is written out in full; Tasks 3–6 apply the identical shape to a different file set**, listed per task below. Each is independently shippable — after each, reads filter for that context but every row is still shared, so nothing disappears.

The rule for every sentinel site: **does this path serve an HTTP caller, or an import?**

| Path | Writes |
|---|---|
| Use cases reached from a route (`get_*`, `create_*`, `update_*`, `delete_*`) | `auth.workspace_id` |
| Ingestion, the arq worker, `bulk_upsert_*`, `scripts/` | `SHARED_WORKSPACE_ID` |

### Task 2: Taxonomy

**Files:**
- Modify: `application/taxonomy/get_organism.py`, `get_proteome.py`, `update_organism.py`
- Modify: `domain/taxonomy/organism.py`, `proteome.py`
- Modify: `infrastructure/persistence/sqlalchemy/taxonomy/strain_repository.py`, `organism_repository.py`, `proteome_repository.py`
- Test: `backend/tests/api/test_workspace_isolation.py` (create)

**Interfaces:**
- Consumes: `readable_by`, `owned_by`, `find_readable`, `find_owned`, `SHARED_WORKSPACE_ID` from Task 1.
- Produces: the shape Tasks 3–6 follow, and `test_workspace_isolation.py`, which they extend.

- [ ] **Step 1: Write the failing isolation test**

Create `backend/tests/api/test_workspace_isolation.py`:

```python
"""Cross-tenant isolation. These are the security tests; keep them in one file.

Each context adds its own case as it is converted. The shape is always the same:
a row owned by workspace B must be invisible to workspace A, and a shared row
must be readable by both and mutable by neither.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID


async def test_shared_organism_is_readable(client: AsyncClient) -> None:
    """Reference data stays visible to every workspace after scoping."""
    resp = await client.get("/api/v1/organisms")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) > 0


async def test_shared_organism_cannot_be_mutated(client: AsyncClient) -> None:
    """Reference data is import-managed: no API caller may change it, admin or not."""
    listed = await client.get("/api/v1/organisms")
    organism_id = listed.json()["items"][0]["id"]

    resp = await client.patch(
        f"/api/v1/organisms/{organism_id}", json={"division": "QA-TEMP"}
    )
    assert resp.status_code == 404, resp.text
```

The mutation assertion is **404, not 403** — a 403 would confirm the row exists to a caller who cannot see it.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_workspace_isolation.py -v`
Expected: the read test passes; the mutation test FAILS with 200, because `update_organism` still loads through the sentinel and mutates happily.

- [ ] **Step 3: Convert the three application use cases**

In each of `get_organism.py`, `get_proteome.py`, `update_organism.py`: replace the `SHARED_WORKSPACE_ID` argument with `auth.workspace_id`, and point the lookup at `find_readable` for the two getters and `find_owned` for the updater. Read each file and change only those lines — do not restructure the use case.

- [ ] **Step 4: Convert the domain factories**

`domain/taxonomy/organism.py` and `proteome.py` reference the sentinel in their `create()` defaults. A domain factory must not choose a workspace: make `workspace_id` a required keyword argument and let the caller supply it. Every existing caller already has one in scope.

- [ ] **Step 5: Filter the list repositories**

In `organism_repository.py` and `proteome_repository.py`, add `readable_by(<Model>, workspace_id)` to each list/search query builder, threading `workspace_id` through the method signature where it is not already a parameter. `strain_repository.py` has sentinel references but no list method — convert its lookups the same way.

- [ ] **Step 6: Run the tests**

Run: `cd backend && uv run pytest tests/api/test_workspace_isolation.py tests/api/test_organisms.py -v`
Expected: PASS. (`test_organisms.py::test_create_and_resolve_organism` is a known pre-existing full-suite pollution failure; it passes in isolation.)

- [ ] **Step 7: Full verification**

Run: `make test && make test-api`
Expected: no new failures beyond the known 2.

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/application/taxonomy backend/src/protcellar/domain/taxonomy \
        backend/src/protcellar/infrastructure/persistence/sqlalchemy/taxonomy \
        backend/tests/api/test_workspace_isolation.py
git commit -m "feat(tenancy): scope the taxonomy context to the caller's workspace

Reads filter to the caller's rows plus shared; mutations to the caller's only,
so reference organisms and proteomes become import-managed. Every row is still
shared at this point, so nothing disappears from any view."
```

### Task 3: Protein catalog

Identical shape to Task 2, applied to:
- `application/protein_catalog/get_gene.py`, `get_gene_neighborhood.py`, `update_gene.py`
- `domain/protein_catalog/gene.py`, `protein.py` (factory defaults → required keyword)
- `infrastructure/persistence/sqlalchemy/protein_catalog/gene_repository.py` — `list_by_organism` and every other query builder gain `readable_by`

Add to `test_workspace_isolation.py`: a shared gene is readable, and `PATCH /genes/{id}` on it returns 404.

**Note:** `bulk_upsert_genes.py`, `bulk_upsert_proteins.py` and `bulk_enrich_genes.py` are **import paths** — they keep `SHARED_WORKSPACE_ID`.

### Task 4: Target biology

**This context contains the file with concurrent history. Re-read the constraint at the top of this plan before starting.**

- `application/target_biology/crud.py` — `Create/Update/DeleteTargetBiologyRecord`. The update and delete use cases move to `find_owned(auth.workspace_id, record_id)`; create builds the aggregate with `auth.workspace_id`.
- `application/target_biology/get_gene_target_biology.py`, `get_protein_target_biology.py` — `readable_by`.
- The eight `bulk_upsert_*.py` — **import paths, keep `SHARED_WORKSPACE_ID`**.
- `interface/routes/target_biology.py` — the eight create routes currently pass `workspace_id=SHARED_WORKSPACE_ID` into each aggregate's `create()`. Change **only that argument** to the caller's workspace. **Do not touch `_patch_updates`, the patch bodies, or the descriptor.**

Add to `test_workspace_isolation.py`: an essentiality record created by workspace A is invisible to workspace B, and a shared (published) record returns 404 on PATCH and DELETE.

### Task 5: Tagging

- `infrastructure/persistence/sqlalchemy/tagging/tag_browse_repository.py`, `tag_link_repository.py` — `readable_by` on browse queries, `owned_by` on link mutations.
- `tag_repository.py` list methods — `readable_by`.

Tags become workspace-owned, so the existing rename/merge dialogs keep working. Add a test that workspace A cannot see workspace B's tag.

### Task 6: Imports, scripts, and audit

- `domain/imports/import_run.py`, `upload.py` — factory defaults → required keyword.
- `infrastructure/persistence/sqlalchemy/imports/import_run_repository.py`, `import_upload_repository.py` — `readable_by` on list, `owned_by` on mutation.
- `infrastructure/persistence/sqlalchemy/audit_compliance/audit_repository.py` — `readable_by` on its list method. There is no audit HTTP route today, but the query must be correct before one is added.
- `application/service_auth.py` — read it and decide: if it represents a no-user system call, it keeps `SHARED_WORKSPACE_ID`.
- `scripts/backfill_essentiality.py`, `scripts/seed_mock_target_biology.py` — one-off operator scripts producing reference data: keep `SHARED_WORKSPACE_ID`.

Import runs become workspace-owned, so a tenant sees only their own import history.

---

### Task 7: Migration B — reclassify

**Files:**
- Create: `backend/alembic/versions/d2b5f9c8e314_reclassify_workspaces.py`
- Test: `backend/tests/api/test_workspace_isolation.py` (extend)

**Interfaces:**
- Consumes: `SHARED_WORKSPACE_ID`, and every read path filtering (Tasks 2–6).

**Only now does this mean anything.** Run before Task 6 and it is a no-op that looks like success.

- [ ] **Step 1: Confirm the classification against live data**

```bash
docker compose exec -T postgres psql -U protcellar -d protcellar -t -A -F' | ' -c "
SELECT 'essentiality', provenance->>'source_type', count(*) FROM essentiality_records GROUP BY 2
UNION ALL SELECT 'vulnerability', provenance->>'source_type', count(*) FROM vulnerability_records GROUP BY 2
UNION ALL SELECT 'resistance', provenance->>'source_type', count(*) FROM resistance_mutations GROUP BY 2;"
```
Expected at time of writing: essentiality 4010 `published`; vulnerability 5 `published` + **1 `private_comm`**; resistance 4 `published`. If the private count is no longer 1, the assertion in Step 4 must be updated to match reality, not the other way round.

- [ ] **Step 2: Write the migration**

`down_revision` is Migration A. The target workspace comes from a required env var so the migration fails loudly in a deployment where nobody has said which workspace inherits the data.

```python
"""move non-reference rows out of the shared workspace

Revision ID: d2b5f9c8e314
Revises: c1a4e8b7d203
Create Date: 2026-08-08 00:00:00.000000

Reference data stays shared. Private observations, workspace artifacts and
workspace-owned entities move to the workspace that owns them. This is the only
step in the tenancy work that changes what anyone can see, and at time of
writing it changes it for exactly one row.
"""
import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd2b5f9c8e314'
down_revision: Union[str, None] = 'c1a4e8b7d203'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHARED = 'a577f0f9-b1fb-53b6-be5d-49bcb500adeb'

# Target-biology tables whose rows move when the provenance is not public.
_OBSERVATION_TABLES = [
    "essentiality_records",
    "vulnerability_records",
    "hypomorphs",
    "crispri_strains",
    "resistance_mutations",
    "protein_productions",
    "protein_activity_assays",
    "unpublished_structures",
]

# Whole tables that are workspace artifacts, never reference data.
_WORKSPACE_TABLES = ["import_runs", "import_uploads", "tags", "targets", "organizations"]


def _target_workspace() -> str:
    value = os.environ.get("MIGRATION_TARGET_WORKSPACE_ID")
    if not value:
        raise RuntimeError(
            "MIGRATION_TARGET_WORKSPACE_ID must name the workspace that inherits "
            "the existing non-reference data. There is no safe default."
        )
    return value


def upgrade() -> None:
    target = _target_workspace()
    for table in _OBSERVATION_TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = :target "
                f"WHERE workspace_id = :shared "
                f"AND COALESCE(provenance->>'source_type', '') "
                f"NOT IN ('published', 'preprint')"
            ).bindparams(target=target, shared=_SHARED)
        )
    for table in _WORKSPACE_TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = :target WHERE workspace_id = :shared"
            ).bindparams(target=target, shared=_SHARED)
        )


def downgrade() -> None:
    target = _target_workspace()
    for table in _OBSERVATION_TABLES + _WORKSPACE_TABLES:
        op.execute(
            sa.text(
                f"UPDATE {table} SET workspace_id = :shared WHERE workspace_id = :target"
            ).bindparams(target=target, shared=_SHARED)
        )
```

`provenance` is `jsonb` as of `117f290`, so `->>` works and `COALESCE` covers a row with no `source_type` — which is treated as *not public*, the safe direction.

- [ ] **Step 3: Apply it**

```bash
MIGRATION_TARGET_WORKSPACE_ID=442df0cf-e618-4938-a089-80ae2f1e43e7 make migrate
```

Then confirm it fails without the variable:
```bash
cd backend && (set -a; . ./.env; set +a; unset MIGRATION_TARGET_WORKSPACE_ID; uv run alembic downgrade -1)
```
Expected: `RuntimeError` naming the variable.

- [ ] **Step 4: Verify exactly one row moved**

```bash
docker compose exec -T postgres psql -U protcellar -d protcellar -t -A -F' | ' -c "
SELECT workspace_id, count(*) FROM vulnerability_records GROUP BY 1;
SELECT count(*) FROM essentiality_records
 WHERE workspace_id <> 'a577f0f9-b1fb-53b6-be5d-49bcb500adeb';"
```
Expected: vulnerability split 5 shared / 1 workspace; essentiality `0` outside shared.

- [ ] **Step 5: Full verification and commit**

Run: `make test && make test-api && make test-fe`

```bash
git add backend/alembic/versions/d2b5f9c8e314_reclassify_workspaces.py backend/tests
git commit -m "feat(tenancy): move non-reference rows out of the shared workspace

Published and preprint observations stay shared; private_comm, internal and
patent ones move to the workspace that recorded them, along with import runs,
tags, targets and organizations. Exactly one row changes visibility today — a
private_comm vulnerability that every tenant could previously read.

The destination comes from a required env var with no default, so the migration
refuses to guess which workspace inherits the data."
```

---

### Task 8: `is_shared`, so the UI stops offering controls that 404

**Files:**
- Modify: `backend/src/protcellar/interface/routes/target_biology.py` (8 response models) — **concurrent history**
- Modify: `backend/src/protcellar/interface/routes/strains.py`
- Modify: `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx`
- Test: `backend/tests/api/test_workspace_isolation.py`, and a frontend test

After Task 7, the record tables render edit / provenance / delete on 4,019 shared rows whose mutations now 404.

- [ ] **Step 1: Add the field to the eight target-biology responses**

Each `*Response` gains `is_shared: bool`, mapped in `from_domain` as
`is_shared=(record.workspace_id == SHARED_WORKSPACE_ID)`. Add the field and the one mapping line to each class; change nothing else in the file.

Not `editable`: whether a caller may edit also depends on their role, which the client already knows. `is_shared` supplies the half it cannot compute.

- [ ] **Step 2: Add an API test**

```python
async def test_shared_records_are_marked_is_shared(client: AsyncClient) -> None:
    """The client needs this to hide controls it would otherwise offer in vain."""
    resp = await client.get("/api/v1/target-biology/essentiality?limit=1")
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"][0]["is_shared"] is True
```

(Uses the bulk endpoint from Task 9. If Task 9 has not landed, assert against a
`GET /genes/{id}/target-biology` bundle instead.)

- [ ] **Step 3: Hide the controls**

In `editable-record-table.tsx`, suppress the edit, provenance and delete actions for a row whose `is_shared` is true, and render a short static marker in the actions cell explaining that the row is reference data managed by import. **This file was changed by `10735a1` — read it and add the condition; do not rewrite the component.**

- [ ] **Step 4: Frontend test, verification, commit**

Add a test asserting a row with `is_shared: true` renders no edit/delete control and a row without it renders both.

Run: `make test-api && make test-fe && cd frontend && pnpm exec tsc --noEmit`

---

### Task 9: Bulk target-biology read

**Files:**
- Modify: `backend/src/protcellar/interface/routes/target_biology.py` — **concurrent history**
- Test: `backend/tests/api/test_target_biology.py`

**Interfaces:**
- Consumes: `readable_by`, and the `RecordKind` frozenset the write routes already validate against.
- Produces: `GET /api/v1/target-biology/{kind}`.

- [ ] **Step 1: Write the failing test**

```python
async def test_bulk_list_is_cursor_paginated_and_workspace_filtered(
    client: AsyncClient, database_url: str
) -> None:
    gene_id = uuid.uuid4()
    prov = Provenance(source_type=ProvenanceSourceType.PUBLISHED)
    for condition in ("7H9", "cholesterol", "glycerol"):
        await _save(
            database_url,
            SQLAlchemyEssentialityRepository,
            Essentiality(
                workspace_id=WS,
                gene_id=gene_id,
                classification=EssentialityClass.ESSENTIAL,
                provenance=prov,
                condition=condition,
            ),
        )

    resp = await client.get(f"/api/v1/target-biology/essentiality?gene_id={gene_id}")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) == 3


async def test_bulk_list_rejects_an_unknown_kind(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/target-biology/nonsense")
    assert resp.status_code == 422
```

- [ ] **Step 2: Run it to verify it fails** — 404, the route does not exist.

- [ ] **Step 3: Add the route**

Register it **after** `GET /target-biology/schema` (a literal path must not be shadowed by `{kind}`) and before the parameterized write routes. Signature:

```
GET /api/v1/target-biology/{kind}
    ?organism_id=&strain_id=&gene_id=&protein_id=&cursor=&limit=
```

`kind` validates against the existing frozenset before any query — an unknown kind is a 422 with no database round trip. `gene_id` and `protein_id` are repeatable. Filter with `readable_by`. Return `PaginatedResponse` with the same per-kind response models the bundle endpoints already use, so `is_shared` from Task 8 comes along.

`organism_id` and `strain_id` require joining the parent gene or protein; follow whatever join the existing `/genes` list uses rather than inventing one.

- [ ] **Step 4: Run tests, regenerate the client, commit**

```bash
make test-api && make generate-api
```

---

### Task 10: Parent validation on create

**Files:**
- Modify: `backend/src/protcellar/interface/routes/target_biology.py` — **concurrent history**
- Test: `backend/tests/api/test_target_biology.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_create_rejects_a_gene_that_does_not_exist(client: AsyncClient) -> None:
    """A record must not be attachable to a UUID that has never existed."""
    resp = await client.post(
        f"/api/v1/genes/{uuid.uuid4()}/target-biology/essentiality",
        json={
            "classification": "essential",
            "provenance": {"source_type": "published", "citations": []},
        },
    )
    assert resp.status_code == 404, resp.text
```

- [ ] **Step 2: Run it to verify it fails** — returns 201, because the route never looks the gene up.

- [ ] **Step 3: Add the lookup**

Both create routes resolve their parent through `find_readable(auth.workspace_id, parent_id)` and return 404 when it is absent or not visible. **404, never 403** — a 403 confirms the row exists to a caller who may not see it, which is the probe this closes.

Add the dependency to the two create handlers only; leave the eight PATCH routes and `_patch_updates` untouched.

- [ ] **Step 4: Run tests and commit**

Run: `make test && make test-api && make lint`

---

## Self-Review

**Spec coverage.** §1.1 → Task 1 Step 3. §1.2 → Task 1 Step 4. §1.3 → Task 1 Step 5 plus Tasks 2–6. §1.4 (child rows unscoped) → no task, correctly: the decision is to add nothing, and the invariant is exercised by Task 3's cross-tenant gene test, which loads a gene's children through a scoped parent. §1.5 → Task 8. §1.6 → Tasks 1 and 7. §2 → Task 9. §3 → Task 10. §4 testing → distributed across tasks, with the security cases collected in `test_workspace_isolation.py`. §6 → the second global constraint, restated in Tasks 4, 8, 9 and 10.

**Type consistency.** `readable_by` / `owned_by` are defined in Task 1 Step 4 and consumed by name in Tasks 1, 2, 3, 5, 6 and 9. `find_readable` / `find_owned` are defined in Task 1 Step 5 and consumed in Tasks 2, 3, 4, 6 and 10. `SHARED_WORKSPACE_ID` is defined in Task 1 Step 3 and its literal value appears identically in both migrations and the unit test.

**Two places the implementer must read the code rather than trust this plan**, flagged inline: the current head revision for Migration A's `down_revision`, and the live `source_type` distribution before Migration B. Both are cheap to check and wrong to guess.

**Known deviation from the usual plan style.** Tasks 3–6 give a file list and the specific test rather than reproducing Task 2's steps five times. That is deliberate: the shape is identical, and the alternative — five near-identical forty-line blocks — is the verbatim duplication the review rubric treats as a defect. Task 2 is the worked example; the per-task lists name every file and every decision that differs.
