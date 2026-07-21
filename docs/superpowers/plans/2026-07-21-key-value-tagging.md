# Key-Value Tagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port chem-cellar's key-value tagging system to prot-cellar (backend + frontend) at full parity, for 6 taggable entities, with workspace-scoped tags.

**Architecture:** A `Tag` aggregate (workspace-scoped `(key, value?)`) in the `workspace_config` context, attached to entities via one dedicated link table per taggable type (real FKs + cascade). Layered DDD backend (domain/application/infrastructure/interface). Next.js frontend feature `tagging` + shared `TagChip`, orval-generated client + hand-written hooks.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, `returns.Result`, Lagom DI, pytest, Postgres (pg_trgm, `NULLS NOT DISTINCT`). Frontend: Next.js 16 App Router, React 19, TanStack Query v5, orval, Radix/shadcn, vitest.

## Port model

This is a **port**, not a greenfield build. The reference implementation is chem-cellar at `~/workspace/chem-vault2`. For each task: **read the named chem-cellar source file(s), replicate them into the prot-cellar destination, and apply the listed adaptations.** Do not invent structure that diverges from chem-cellar unless an adaptation says so.

## Global Constraints

- **Design doc:** `docs/superpowers/specs/2026-07-21-key-value-tagging-design.md` — authoritative. Read it once before starting.
- **Reference root:** chem-cellar backend `~/workspace/chem-vault2/backend/src/cellar`, frontend `~/workspace/chem-vault2/frontend/src`.
- **Taggable set (6):** Protein, Gene, Target, Organism, Strain, Proteome. Plural URL segments: `proteins, genes, targets, organisms, strains, proteomes`. Link tables: `protein_tags, gene_tags, target_tags, organism_tags, strain_tags, proteome_tags`. Every entity table has UUID `id` PK and a `workspace_id` column.
- **THE adaptation (vs chem-cellar):** entity-visibility in `entity_exists_in_workspace` is **global-or-mine**: `entity.workspace_id IN (ws, GLOBAL_WORKSPACE_ID)` where `GLOBAL_WORKSPACE_ID = uuid.UUID(int=0)` (`from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID`). chem-cellar uses strict `== ws`; do NOT copy that.
- **Context home:** tagging is a sub-domain of `workspace_config`. Backend paths: `domain/workspace_config/tagging/`, `application/workspace_config/tagging/`, `infrastructure/persistence/sqlalchemy/tagging/`, `interface/routes/tags.py`.
- **Backend tooling:** run tests with `cd backend && uv run pytest ...` (match existing invocation — check `backend/README` / how other tests run first). Migrations: `cd backend && uv run alembic revision --autogenerate` / `alembic upgrade head`.
- **Frontend tooling:** run vitest/tsc/biome via `./node_modules/.bin/*` from `frontend/` (pnpm exec is flaky here). Orval: `pnpm generate:api`.
- **Per-task commits.** Every task ends with a commit. Branch is `feat/key-value-tagging` (already created).
- **Every new SQLAlchemy model module MUST be imported in** `infrastructure/persistence/sqlalchemy/metadata.py` or Alembic autogenerate won't see it.

---

## Phase A — Domain

### Task 1: Tag domain model

**Files:**
- Create: `backend/src/protcellar/domain/workspace_config/tagging/__init__.py`
- Create: `backend/src/protcellar/domain/workspace_config/tagging/tag.py`
- Create: `backend/src/protcellar/domain/workspace_config/tagging/events.py`
- Create: `backend/src/protcellar/domain/workspace_config/tagging/repository.py`
- Test: `backend/tests/unit/domain/workspace_config/test_tag_name.py`
- Test: `backend/tests/unit/domain/workspace_config/test_tag.py`

**Port from:** chem-cellar `domain/workspace_config/tagging/{tag.py,events.py,repository.py}`.

**Interfaces produced (later tasks depend on these exact names):**
- `TagName(key: str, value: str | None = None)` — frozen; props `normalized_key`, `normalized_value`.
- `Tag(AggregateRoot)` — `Tag.create(workspace_id, key, value, created_by) -> Tag`; `.rename(TagName)`; props `key, value, normalized_key, normalized_value, workspace_id, created_by`.
- `TaggableEntityType(StrEnum)` with members `PROTEIN, GENE, TARGET, ORGANISM, STRAIN, PROTEOME` and values `"Protein","Gene","Target","Organism","Strain","Proteome"`.
- `AssignedTag(tag: Tag, assigned_by: UUID, assigned_at: datetime)` — frozen.
- Events: `TagCreated, TagRenamed, TagDeleted, TagMerged, TagAssigned, TagUnassigned` (subclass `domain/shared/events.py::DomainEvent`).
- Protocols in `repository.py`: `TagRepository`, `TagLinkRepository`, `TagLinkRepositoryProvider` (signatures per design doc).

**Adaptations:** enum = the 6 prot entities above (chem-cellar has 8 different ones). Base classes: use prot-cellar's `domain/shared/entity.py::AggregateRoot` and `domain/shared/events.py::DomainEvent` (confirm exact import paths — mirror how `domain/target/target.py` and `domain/target/events.py` import them).

- [ ] **Step 1: Write failing VO tests** (`test_tag_name.py`):

```python
import pytest
from protcellar.domain.workspace_config.tagging.tag import TagName


def test_key_required_and_trimmed():
    assert TagName(key="  Priority  ").key == "Priority"
    with pytest.raises(ValueError):
        TagName(key="   ")

def test_value_optional_blank_becomes_none():
    assert TagName(key="k", value="  ").value is None
    assert TagName(key="k").value is None

def test_normalized_is_casefolded():
    n = TagName(key="Priority", value="High")
    assert n.normalized_key == "priority"
    assert n.normalized_value == "high"

def test_length_limits():
    with pytest.raises(ValueError):
        TagName(key="k" * 129)
    with pytest.raises(ValueError):
        TagName(key="k", value="v" * 257)

def test_control_chars_rejected():
    with pytest.raises(ValueError):
        TagName(key="a\x00b")
```

- [ ] **Step 2: Write failing aggregate tests** (`test_tag.py`): cover `Tag.create` emits `TagCreated` (assert `collect_events()` contains it — mirror how `tests/unit/domain/target/test_target.py` asserts events), `.rename()` emits `TagRenamed`, and the 6-member enum values.

- [ ] **Step 3: Run to verify fail:** `cd backend && uv run pytest tests/unit/domain/workspace_config/ -v` → FAIL (import errors).

- [ ] **Step 4: Port the implementation** — create the four files by porting the chem-cellar sources, applying the adaptations. Read `~/workspace/chem-vault2/backend/src/cellar/domain/workspace_config/tagging/tag.py` first.

- [ ] **Step 5: Run to verify pass:** `cd backend && uv run pytest tests/unit/domain/workspace_config/ -v` → PASS.

- [ ] **Step 6: Commit:** `git add backend/src/protcellar/domain/workspace_config/tagging backend/tests/unit/domain/workspace_config && git commit -m "feat(tagging): Tag domain model (VO, aggregate, events, repo protocols)"`

---

## Phase B — Persistence

### Task 2: SQLAlchemy models (tags + 6 link tables)

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/tagging/__init__.py`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/tagging/models.py`
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/metadata.py` (import the new models module)

**Port from:** chem-cellar `infrastructure/persistence/sqlalchemy/tagging/models.py`.

**Interfaces produced:** `TagModel`, `TagLinkMixin`, and 6 link models: `ProteinTagLinkModel, GeneTagLinkModel, TargetTagLinkModel, OrganismTagLinkModel, StrainTagLinkModel, ProteomeTagLinkModel`.

**Adaptations:** 6 link tables (chem-cellar has 8). Each link model, mechanically:

| Model | table | entity FK col → target |
|---|---|---|
| `ProteinTagLinkModel` | `protein_tags` | `protein_id` → `proteins.id` |
| `GeneTagLinkModel` | `gene_tags` | `gene_id` → `genes.id` |
| `TargetTagLinkModel` | `target_tags` | `target_id` → `targets.id` |
| `OrganismTagLinkModel` | `organism_tags` | `organism_id` → `organisms.id` |
| `StrainTagLinkModel` | `strain_tags` | `strain_id` → `strains.id` |
| `ProteomeTagLinkModel` | `proteome_tags` | `proteome_id` → `proteomes.id` |

Each: composite PK `(<entity>_id, tag_id)`; both FKs `ondelete="CASCADE"`; `tag_id` FK → `tags.id`; index `ix_<table>_tag_id`; `TagLinkMixin` supplies `assigned_by`, `assigned_at`. `TagModel` unique index `uq_tags_ws_norm` on `(workspace_id, normalized_key, normalized_value)` with `postgresql_nulls_not_distinct=True`; two `postgresql_using="gin"` `gin_trgm_ops` indexes; `ix_tags_ws_created_by`.

- [ ] **Step 1:** Port `models.py` (read chem-cellar source; use prot-cellar `Base`/mixins from `sqlalchemy/base.py`).
- [ ] **Step 2:** Add `from protcellar.infrastructure.persistence.sqlalchemy.tagging import models as _tagging_models  # noqa` (mirror the existing style) to `metadata.py`.
- [ ] **Step 3: Verify import + metadata registration:** `cd backend && uv run python -c "from protcellar.infrastructure.persistence.sqlalchemy.metadata import *; from protcellar.infrastructure.persistence.sqlalchemy.base import Base; assert 'tags' in Base.metadata.tables and 'protein_tags' in Base.metadata.tables"` → no error.
- [ ] **Step 4: Commit:** `git commit -m "feat(tagging): SQLAlchemy models for tags + 6 link tables"`

### Task 3: Alembic migration

**Files:**
- Create: `backend/alembic/versions/<rev>_tagging.py` (generate the revision id; don't hand-pick)

**Port from:** chem-cellar `alembic/versions/047_tagging.py` + `050_tagging_expansion.py` (merge into ONE migration; **omit all legacy `molecules.tags` backfill** — no analog exists here).

- [ ] **Step 1: Autogenerate:** `cd backend && uv run alembic revision --autogenerate -m "tagging"`. Then hand-edit: ensure `op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")` runs first; verify the `nulls_not_distinct` unique index and the two GIN trigram indexes are present (autogenerate often misses these — add by hand from the chem-cellar migration). Add the `tag_links_all` view via `op.execute(<UNION ALL over the 6 link tables>)` in `upgrade` and `DROP VIEW` in `downgrade`.
- [ ] **Step 2: Apply:** `cd backend && uv run alembic upgrade head` → succeeds. Then `alembic downgrade -1` then `upgrade head` again to prove reversibility.
- [ ] **Step 3: Commit:** `git commit -m "feat(tagging): migration — tags, 6 link tables, pg_trgm, tag_links_all view"`

### Task 4: Tag repository

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/tagging/tag_repository.py`
- Test: `backend/tests/integration/test_tagging.py` (create; add tag-repo cases)

**Port from:** chem-cellar `infrastructure/persistence/sqlalchemy/tagging/tag_repository.py`.

**Interfaces produced:** `SQLAlchemyTagRepository(uow/session)` implementing `TagRepository` — `get_or_create`, `find_by_id_in_workspace`, `find_by_normalized`, `search`, `save`, `delete`.

**Adaptations:** `search` orders by usage count via the `tag_links_all` view — keep. Mirror prot-cellar's base repository (`sqlalchemy/base_repository.py`) and how `target_repository.py` obtains its session.

- [ ] **Step 1: Write failing integration test** — `get_or_create` is race-safe (calling twice with same normalized name returns same id; value-less dedup works). Use the integration DB fixture pattern from an existing `tests/integration/<context>/` test (find one and copy its fixture wiring).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Port `tag_repository.py`. **Step 4:** Run → PASS.
- [ ] **Step 5: Commit:** `git commit -m "feat(tagging): SQLAlchemyTagRepository (get_or_create, search)"`

### Task 5: Tag-link repositories + filter helper

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/tagging/tag_link_repository.py`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/tagging/tag_filter.py`
- Test: add to `backend/tests/integration/test_tagging.py`; new `backend/tests/integration/test_tag_filtering.py`

**Port from:** chem-cellar `tag_link_repository.py` + `tag_filter.py`.

**Interfaces produced:**
- `SQLAlchemyTagLinkRepository` base (class attrs `link_model, entity_model, entity_id_attr`) + 6 subclasses + `_REGISTRY` dict + `get_tag_link_repository(entity_type)` + `SQLAlchemyTagLinkRepositoryProvider(uow)` implementing `TagLinkRepositoryProvider.for_type`.
- `tag_filter_subquery(link_model, entity_id_attr, tag_ids, match_all) -> Select`.

**Adaptations (critical):** `entity_exists_in_workspace` = global-or-mine (see Global Constraints). `OrganismTagLinkRepository` additionally requires `merged_into_id IS NULL`. No molecule-style tombstone override on the others (verify none of proteins/genes/targets/strains/proteomes have a merge/tombstone column that should exclude rows; if one does, add the guard — check the model).

- [ ] **Step 1: Write the failing visibility test** — the core adaptation. Both a GLOBAL-workspace entity and a workspace-scoped entity must be taggable from a normal workspace:

```python
# in test_tagging.py — pseudocode shape; wire real fixtures/session per existing integration tests
async def test_global_entity_is_taggable_from_a_workspace(session):
    # a Protein pinned to GLOBAL_WORKSPACE_ID
    protein = await make_protein(session, workspace_id=GLOBAL_WORKSPACE_ID)
    repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.PROTEIN)
    ws = uuid4()  # a real user workspace, != GLOBAL
    assert await repo.entity_exists_in_workspace(protein.id, ws) is True

async def test_target_only_visible_to_its_own_workspace(session):
    ws_a, ws_b = uuid4(), uuid4()
    target = await make_target(session, workspace_id=ws_a)
    repo = SQLAlchemyTagLinkRepositoryProvider(uow).for_type(TaggableEntityType.TARGET)
    assert await repo.entity_exists_in_workspace(target.id, ws_a) is True
    assert await repo.entity_exists_in_workspace(target.id, ws_b) is False
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** Port both files with the global-or-mine adaptation. **Step 4:** Run → PASS.
- [ ] **Step 5: Write + pass a `tag_filter_subquery` test** in `test_tag_filtering.py` — any-logic returns entities with ≥1 of the tags; all-logic returns only entities with all.
- [ ] **Step 6: Commit:** `git commit -m "feat(tagging): tag-link repos (global-or-mine visibility) + tag_filter_subquery"`

### Task 6: Cross-entity browse reader

**Files:**
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/tagging/tag_browse_repository.py`
- Test: add to `test_tag_filtering.py` or new `test_tag_browse.py`

**Port from:** chem-cellar `tag_browse_repository.py`.

**Interfaces produced:** `SQLAlchemyTagBrowseRepository` implementing `TagBrowseReader` (defined in Task 8's `list_tag_entities.py`; if building this first, stub the protocol import).

**Adaptations:** `UNION ALL` over the **6** link tables; per-type display `label`: Protein→`primary_accession`, Gene→`primary_name`, Target→`name`, Organism→scientific/display name, Strain→`name`, Proteome→`uniprot_proteome_id`. (Confirm exact column names on each model.)

- [ ] **Step 1:** Write failing test — tag two different entity types, browse by the tag, assert both rows returned with correct `entity_type` + `label`; `match_all=True` across two tags narrows correctly.
- [ ] **Step 2–4:** FAIL → port → PASS. **Step 5: Commit:** `git commit -m "feat(tagging): cross-entity tag browse reader"`

---

## Phase C — Application

### Task 7: Assignment use-cases (assign / unassign / set / get)

**Files:**
- Create: `backend/src/protcellar/application/workspace_config/tagging/__init__.py`
- Create: `assign_tag.py`, `unassign_tag.py`, `set_entity_tags.py`, `get_tags_for_entity.py` (same dir)
- Test: `backend/tests/unit/application/workspace_config/tagging/test_set_entity_tags.py`

**Port from:** chem-cellar `application/workspace_config/tagging/{assign_tag,unassign_tag,set_entity_tags,get_tags_for_entity}.py`.

**Interfaces produced:** `AssignTagCommand`+`AssignTag`, `UnassignTagCommand`+`UnassignTag`, `SetEntityTagsCommand`(+`TagInput`)+`SetEntityTags`, `GetTagsForEntityQuery`+`GetTagsForEntity`. Each handler `async __call__(input, auth) -> Result[..., DomainError]`.

**Adaptations:** auth guards + UoW/dispatcher wiring per prot-cellar's `application/target/create_target.py` pattern (`require_editor`, `async with self._uow`, `dispatch_all`). Assign/unassign/set emit audit events only when a link actually changes.

- [ ] **Step 1:** Write failing `test_set_entity_tags.py` — reconcile: given entity has tags {A,B}, `set({B,C})` adds C, removes A, keeps B; uses a fake link repo/provider (copy fake style from `tests/fakes/`).
- [ ] **Step 2–4:** FAIL → port → PASS.
- [ ] **Step 5: Commit:** `git commit -m "feat(tagging): assign/unassign/set/get entity-tag use-cases"`

### Task 8: Management use-cases (list / rename / merge / delete / list-entities)

**Files:**
- Create: `list_tags.py`, `rename_tag.py`, `merge_tags.py`, `delete_tag.py`, `list_tag_entities.py` (same dir)
- Test: `backend/tests/unit/application/workspace_config/tagging/test_merge_tags.py`

**Port from:** chem-cellar equivalents.

**Interfaces produced:** `ListTagsQuery`+handler, `RenameTagCommand`+handler, `MergeTagsCommand`+handler, `DeleteTagCommand`+handler, `ListTagEntitiesQuery`+handler; plus `TagBrowseReader` protocol + `TaggedEntityRow` DTO (in `list_tag_entities.py`).

**Adaptations:** merge repoints all **6** link tables then deletes source. Rename conflict → domain error advising merge. Auth: list/list-entities = viewer; rename/merge/delete = admin.

- [ ] **Step 1:** Write failing `test_merge_tags.py` — merging source→target repoints links and deletes source (fake repos). **Step 2–4:** FAIL → port → PASS.
- [ ] **Step 5: Commit:** `git commit -m "feat(tagging): list/rename/merge/delete/list-entities use-cases"`

---

## Phase D — Interface + wiring

### Task 9: Routes + DTOs

**Files:**
- Create: `backend/src/protcellar/interface/routes/tags.py`

**Port from:** chem-cellar `interface/routes/tags.py`.

**Interfaces produced:** `router` (`/api/v1/tags`) + `assignment_router` (`/api/v1`, generic `{entity_collection}`); DTOs `TagResponse, EntityTagResponse, TaggedEntityResponse, AssignTagBody, RenameTagBody, MergeTagBody, TagItemBody, SetEntityTagsBody`; `_ENTITY_COLLECTIONS` plural→`TaggableEntityType` map for the 6 types.

**Adaptations:** `_ENTITY_COLLECTIONS = {"proteins": PROTEIN, "genes": GENE, "targets": TARGET, "organisms": ORGANISM, "strains": STRAIN, "proteomes": PROTEOME}`. Use prot-cellar `result_to_response` (`interface/error_handlers.py`) and `AuthDep`. Use-case deps come from Task 10's aliases — write the handlers referencing `Create... Dep`-style aliases you'll define next.

- [ ] **Step 1:** Port `tags.py` with the 6-entity map. (No test yet — API tests need DI, done in Task 10.)
- [ ] **Step 2: Commit:** `git commit -m "feat(tagging): FastAPI routers + DTOs"`

### Task 10: DI + FastAPI deps + registration + API tests

**Files:**
- Modify/Create: `backend/src/protcellar/infrastructure/di/_workspace_config.py` (bind tagging handlers; create if absent — mirror `di/_target.py`)
- Modify: `backend/src/protcellar/infrastructure/di/container.py` (call `register_...` if new)
- Modify/Create: `backend/src/protcellar/interface/dependencies/_workspace_config.py` (use-case `Annotated[..., Depends]` aliases) + re-export from `dependencies/__init__.py`
- Modify: `backend/src/protcellar/interface/app.py` (`include_router` both routers)
- Test: `backend/tests/api/test_tags.py`

**Port from:** chem-cellar `di/_workspace_config.py` (tagging bindings) + `interface/app.py` router includes.

**Adaptations:** construct handlers with `SQLAlchemyTagRepository` + `SQLAlchemyTagLinkRepositoryProvider(uow)` + `SQLAlchemyTagBrowseRepository`. Follow prot-cellar's exact DI/deps idiom from the `target` context.

- [ ] **Step 1: Write failing API tests** (`test_tags.py`, `httpx.AsyncClient`, mirror `tests/api/test_targets.py`): POST a tag to a protein → 201; GET the protein's tags → contains it; PUT reconcile; DELETE → 204; GET `/api/v1/tags?q=` lists it.
- [ ] **Step 2:** Run → FAIL (routes not wired). **Step 3:** Wire DI + deps + register routers. **Step 4:** Run → PASS.
- [ ] **Step 5: Full backend suite:** `cd backend && uv run pytest` → green (note: per memory, ~2 pre-existing proteome test-isolation failures may exist; confirm they're unrelated).
- [ ] **Step 6: Commit:** `git commit -m "feat(tagging): DI, deps, router registration + API tests"`

---

## Phase E — API client

### Task 11: Regenerate OpenAPI + orval client

**Files:** refresh `frontend/openapi.json`; generated `frontend/src/shared/lib/api/tags/tags.ts` + model files.

- [ ] **Step 1:** Export fresh `openapi.json` from the running backend (use the same command the repo already uses — check `package.json`/`Makefile` for the openapi dump script).
- [ ] **Step 2:** `cd frontend && pnpm generate:api`. Confirm `src/shared/lib/api/tags/tags.ts` and model DTOs (`tagResponse.ts`, `entityTagResponse.ts`, `assignTagBody.ts`, `setEntityTagsBody.ts`, `taggedEntityResponse.ts`, …) exist.
- [ ] **Step 3: Typecheck:** `cd frontend && ./node_modules/.bin/tsc --noEmit` → clean.
- [ ] **Step 4: Commit:** `git commit -m "chore(tagging): regenerate openapi + orval client"`

---

## Phase F — Frontend core (attach tags on detail pages)

### Task 12: TagChip (shared)

**Files:**
- Create: `frontend/src/shared/components/tag-chip.tsx`
- Test: `frontend/src/shared/components/tag-chip.test.tsx`

**Port from:** chem-cellar `shared/components/tag-chip.tsx`.

**Interfaces produced:** `TagChip({ tagKey, value, onRemove?, onClick? })`.

**Adaptations:** category color — port `resolveCategoryColor` if present (or inline a simple hash→hue). Use prot-cellar's `Badge` from `shared/components/ui`.

- [ ] **Step 1:** Write failing `tag-chip.test.tsx` — renders `key=value`; clicking × calls `onRemove`; no × when `onRemove` absent. **Step 2–4:** FAIL → port → PASS (`cd frontend && ./node_modules/.bin/vitest run src/shared/components/tag-chip.test.tsx`).
- [ ] **Step 5: Commit:** `git commit -m "feat(tagging): TagChip shared component"`

### Task 13: Tagging hooks + types

**Files:**
- Create: `frontend/src/features/tagging/types/index.ts`
- Create: `frontend/src/features/tagging/hooks/use-tags.ts`, `use-entity-tags.ts`, `use-tag-entities.ts`
- Create: `frontend/src/features/tagging/index.ts` (barrel)
- Test: `frontend/src/features/tagging/hooks/use-entity-tags.test.ts`

**Port from:** chem-cellar `features/tagging/{types,hooks}`.

**Interfaces produced:** `TaggableEntity` (union of 6 plural segments), `Tag, EntityTag, TagInput, TaggedEntity`; `useTags, useRenameTag, useDeleteTag, useMergeTags, useEntityTags, useAssignTag, useUnassignTag, useTagEntities`.

**Adaptations:** `TaggableEntity = "proteins"|"genes"|"targets"|"organisms"|"strains"|"proteomes"`. Wrap `customInstance`; invalidate `["entity-tags", entity, id]` + `["tags"]` on mutations; `showSuccess` toast on success (match `features/target/hooks/use-targets.ts`).

- [ ] **Step 1:** Write failing `use-entity-tags.test.ts` — `useAssignTag` posts and invalidates (mock `customInstance`; mirror `use-targets.test.ts`). **Step 2–4:** FAIL → port → PASS.
- [ ] **Step 5: Commit:** `git commit -m "feat(tagging): FE hooks + types"`

### Task 14: TagsRelation editor + mount on 6 detail pages

**Files:**
- Create: `frontend/src/features/tagging/components/tags-relation.tsx`, `tag-autocomplete.tsx`
- Test: `frontend/src/features/tagging/components/tags-relation.test.tsx`
- Modify (mount `<TagsRelation entity=... id={...} />`):
  - `frontend/src/features/protein-catalog/components/protein-detail.tsx` (Overview side column, near `KeywordsSection`) — `entity="proteins" id={protein.id}`
  - `frontend/src/features/protein-catalog/components/gene-detail.tsx` — `entity="genes" id={gene.id}`
  - `frontend/src/features/target/components/target-detail.tsx` — `entity="targets" id={target.id}`
  - organism detail component (under `features/taxonomy/…` behind `organisms/[id]`) — `entity="organisms"`
  - strain detail component (`strains/[id]`) — `entity="strains"`
  - proteome detail component (`proteomes/[id]`) — `entity="proteomes"`

**Port from:** chem-cellar `features/screening-assay/components/run-relations.tsx::TagsRelation` (the reference inline editor) + `tag-autocomplete.tsx`.

**Interfaces produced:** `TagsRelation({ entity: TaggableEntity, id: string })`, `TagAutocomplete({ field: "key"|"value", ... })`.

- [ ] **Step 1:** Write failing `tags-relation.test.tsx` — renders existing tags as `TagChip`s; "+ Tag" → enter key+value → calls `useAssignTag`; × on a chip → `useUnassignTag` (mock hooks). **Step 2–4:** FAIL → port → PASS.
- [ ] **Step 5:** Mount on the 6 detail pages (find each detail component; add the section next to existing metadata/keyword cards). Typecheck clean.
- [ ] **Step 6: Verify in-app:** use the `verify` skill / `run` skill to load a protein detail page and confirm tags render + a tag can be added/removed (real backend running).
- [ ] **Step 7: Commit:** `git commit -m "feat(tagging): TagsRelation editor mounted on 6 detail pages"`

---

## Phase G — Frontend list faceting

### Task 15: TagFilter on 6 list pages + backend list-param threading

**Files:**
- Create: `frontend/src/features/tagging/components/tag-filter.tsx`
- Test: `frontend/src/features/tagging/components/tag-filter.test.tsx`
- Modify: the 6 list components + their backend `list_*` queries/repos + list route DTOs to accept `tags: list[UUID]` + `tag_logic: "any"|"all"`.

**Port from:** chem-cellar `features/tagging/components/tag-filter.tsx`; backend list-param pattern from chem-cellar `routes/projects.py` (tags/tag_logic params) → `tag_filter_subquery`.

**Interfaces produced:** `TagFilter({ value: {tagIds, tagLogic}, onChange })`.

**Adaptations:** thread `tags`/`tag_logic` into each of the 6 backend list queries via `tag_filter_subquery(<LinkModel>, "<entity>_id", tag_ids, match_all)`. Do the backend param + repo change and its API test in the SAME task as the FE filter so each list stays shippable. Regenerate orval after backend param changes (list DTOs gain the params).

- [ ] **Step 1:** Backend first — add `tags`/`tag_logic` to one list query (proteins) + API test asserting filtering; FAIL → implement → PASS. Repeat for the other 5 (genes, targets, organisms, strains, proteomes).
- [ ] **Step 2:** `pnpm generate:api` (list params now in DTOs).
- [ ] **Step 3:** Write failing `tag-filter.test.tsx`; port `TagFilter`; PASS.
- [ ] **Step 4:** Wire `TagFilter` into the 6 list components (pass selected `{tagIds, tagLogic}` into the list query hook). Typecheck clean.
- [ ] **Step 5: Commit:** `git commit -m "feat(tagging): tag-faceted filtering on 6 list pages"`

---

## Phase H — Frontend admin + browse

### Task 16: Tag management table (admin)

**Files:**
- Create: `frontend/src/features/tagging/components/tag-list.tsx`, `tag-rename-dialog.tsx`, `tag-merge-dialog.tsx`
- Create: `frontend/src/app/(dashboard)/admin/tags/page.tsx` → `<TagList />`
- Test: `frontend/src/features/tagging/components/tag-list.test.tsx`

**Port from:** chem-cellar `features/tagging/components/{tag-list.tsx,tag-table.tsx,tag-rename-dialog.tsx,tag-merge-dialog.tsx}` + `app/(dashboard)/admin/tags/page.tsx`.

- [ ] **Step 1:** Write failing `tag-list.test.tsx` — lists tags, admin Rename/Merge/Delete actions invoke the hooks (mock). **Step 2–4:** FAIL → port → PASS.
- [ ] **Step 5:** Add the admin route; confirm it appears in nav/admin section (match how other `admin/*` pages register). **Step 6: Commit:** `git commit -m "feat(tagging): admin tag management (list/rename/merge/delete)"`

### Task 17: Cross-entity browse page

**Files:**
- Create: `frontend/src/features/tagging/components/tag-browse.tsx`
- Create: `frontend/src/app/(dashboard)/tags/page.tsx` → `<TagBrowse />`
- Test: `frontend/src/features/tagging/components/tag-browse.test.tsx`

**Port from:** chem-cellar `features/tagging/components/tag-browse.tsx` + `app/(dashboard)/tags/page.tsx`.

**Adaptations:** `ROUTE_PREFIX`/`hrefFor` map the 6 entity types to their detail routes (`proteins/[accession]` uses accession — for proteins, link via accession if the browse row carries it, else fall back to `/proteins?tag=`; confirm what `TaggedEntityRow.label`/id provides). Type facet chips for the 6 types.

- [ ] **Step 1:** Write failing `tag-browse.test.tsx` — filter by a tag renders result rows across types with type facet chips. **Step 2–4:** FAIL → port → PASS.
- [ ] **Step 5:** Add the `/tags` route + nav entry. **Step 6: Verify in-app** (browse page loads, filtering works against real backend). **Step 7: Commit:** `git commit -m "feat(tagging): cross-entity tag browse page"`

---

## Final

- [ ] **Full backend suite green:** `cd backend && uv run pytest`.
- [ ] **Full frontend suite green + typecheck + lint:** `cd frontend && ./node_modules/.bin/vitest run && ./node_modules/.bin/tsc --noEmit && ./node_modules/.bin/biome check src`.
- [ ] **Update memory** (`gene-import-and-data-state` sibling / new `tagging` memory) noting the feature shipped on `feat/key-value-tagging`, un-merged.
- [ ] **Requesting-code-review** skill before merge/PR.

## Self-review notes (coverage vs spec)

- Domain (Task 1), persistence models+migration (2–3), repos incl. THE global-or-mine adaptation (4–6), application assign+management (7–8), interface+wiring (9–10), orval (11), FE chip/hooks/editor (12–14), faceting (15), admin+browse (16–17) — every spec section maps to a task.
- `ponytail:` deferrals from the spec (no entity-merge tag carryover, no legacy backfill, no arq-worker dispatch) are intentionally NOT tasks.
- The one behavior that MUST NOT be a blind copy — the visibility check — has its own failing test first (Task 5, Step 1).
