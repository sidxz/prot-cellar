# Key-Value Tagging — Design

**Date:** 2026-07-21
**Status:** Approved (scope decisions locked); pending spec review
**Normative reference:** chem-cellar (`~/workspace/chem-vault2`) `workspace_config/tagging` sub-domain. This is a port with one structural adaptation (below).

## Goal

Port chem-cellar's key-value tagging system to prot-cellar, backend and frontend, at full feature parity, adapted for prot-cellar's entities and its global-reference-data model.

A **tag** is a workspace-scoped `(key, value?)` pair (AWS-style): `key` required, `value` optional. Display casing is preserved; dedup is case-insensitive on normalized (casefolded) forms. Tags attach to entities through **one dedicated link table per taggable type** (real FKs + `ON DELETE CASCADE`, not polymorphic).

## Scope decisions (locked)

1. **Taggable entities:** all six first-class browsable aggregates — **Protein, Gene, Target, Organism, Strain, Proteome**. (The `target_biology` records render as sections inside protein/gene pages, not standalone, so they are not independently taggable.)
2. **Tag scope:** **workspace-scoped.** Each tag row carries its own `workspace_id`; it does *not* inherit the tagged entity's workspace. My workspace's tags on a shared protein are mine; another workspace sees its own.
3. **Feature set:** **full parity** — inline detail-page editor, management table (rename/merge/delete), cross-entity browse page, tag-faceted filtering on list pages.

## The one structural adaptation vs chem-cellar

chem-cellar's taggable entities are all workspace-scoped tenant data. In prot-cellar, the **reference-data aggregates (Protein, Gene, Organism, Strain, Proteome) are pinned to `GLOBAL_WORKSPACE_ID` (`uuid.UUID(int=0)`)** so they reuse workspace-scoped machinery, while **Target is ordinary per-workspace data**. All six nonetheless carry a `workspace_id` column (`WorkspaceIdMixin`) and a UUID `id` PK — so the design does not depend on which bucket a given type falls in; the visibility predicate below is uniform.

Consequence: the tag is always workspace-scoped, but the *entity it points at* may live in the global workspace. So the per-type "does this entity exist and is it visible to my workspace?" check is:

```
entity row exists with id == entity_id
AND entity.workspace_id IN (tag.workspace_id, GLOBAL_WORKSPACE_ID)
```

This is uniform across all six types — no per-type visibility divergence. This is the *only* semantic difference from chem-cellar, where the check was `entity.workspace_id == tag.workspace_id`.

Everything else is a mechanical port.

## Architecture (mirrors chem-cellar, prot-cellar conventions)

prot-cellar is **layer-first**: `domain/ application/ infrastructure/ interface/`, each with per-context subfolders. Tagging is a sub-domain of the existing `workspace_config` context.

### Backend

**Domain — `domain/workspace_config/tagging/`**
- `tag.py`:
  - `TagName` — frozen Pydantic VO. `key: str`, `value: str | None`. Validators: trim; key non-empty, ≤128 chars; value ≤256 chars; all-whitespace value → `None`; reject control chars. Props `normalized_key`/`normalized_value` = `.casefold()`.
  - `Tag(AggregateRoot)` — `id, workspace_id, _name: TagName, created_by, created_at, updated_at, version`. `Tag.create(...)` → `TagCreated`; `rename(new)` → `TagRenamed`. Passthrough props `key/value/normalized_key/normalized_value`.
  - `TaggableEntityType(StrEnum)` — `PROTEIN="Protein"`, `GENE="Gene"`, `TARGET="Target"`, `ORGANISM="Organism"`, `STRAIN="Strain"`, `PROTEOME="Proteome"`.
  - `AssignedTag` — frozen read model: `tag: Tag`, `assigned_by`, `assigned_at`.
- `events.py` — `TagCreated`, `TagRenamed`, `TagDeleted`, `TagMerged{target_tag_id}`, `TagAssigned{target_type,target_id}`, `TagUnassigned{target_type,target_id}` (all subclass `domain/shared/events.py::DomainEvent`, `aggregate_id` = tag id).
- `repository.py` — three `Protocol`s: `TagRepository` (`find_by_id_in_workspace`, `find_by_normalized`, `get_or_create`, `search`, `save`, `delete`), `TagLinkRepository` (bound to one link table: `entity_exists_in_workspace`, `add→bool`, `remove`, `set_for_entity`, `find_tags_for_entity`, `find_assigned_tags_for_entity`, `find_entity_ids_for_tags(match_all)`, `repoint`), `TagLinkRepositoryProvider` (`for_type(entity_type) → TagLinkRepository`).

**Application — `application/workspace_config/tagging/`** (one use-case per file, `returns.Result[..., DomainError]`, auth-gated, dispatch events on commit):
| File | Command/Query | Auth |
|---|---|---|
| `assign_tag.py` | `AssignTagCommand{workspace_id, entity_type, entity_id, key, value, assigned_by}` | editor |
| `unassign_tag.py` | `UnassignTagCommand{…, tag_id}` | editor |
| `set_entity_tags.py` | `SetEntityTagsCommand{…, tags: tuple[TagInput], assigned_by}` — reconcile full set (diff add/remove) | editor |
| `get_tags_for_entity.py` | `GetTagsForEntityQuery{workspace_id, entity_type, entity_id}` → `list[AssignedTag]` | viewer |
| `list_tags.py` | `ListTagsQuery{workspace_id, q, created_by, limit=50}` | viewer |
| `rename_tag.py` | `RenameTagCommand{workspace_id, tag_id, key, value}` — conflict → "merge instead" | admin |
| `merge_tags.py` | `MergeTagsCommand{workspace_id, source_tag_id, target_tag_id}` — repoint all 6 link tables, delete source | admin |
| `delete_tag.py` | `DeleteTagCommand{workspace_id, tag_id}` — links removed by DB CASCADE | admin |
| `list_tag_entities.py` | `ListTagEntitiesQuery{workspace_id, tag_ids, match_all, types, limit=200}` → `list[TaggedEntityRow]`; also defines `TagBrowseReader` protocol + `TaggedEntityRow{entity_type, entity_id, label, assigned_at}` | viewer |

Assign/unassign/set emit audit events only when a link actually changes (check the `inserted`/`removed` bool).

**Infrastructure — `infrastructure/persistence/sqlalchemy/tagging/`** (self-contained area, mirroring chem-cellar's `sqlalchemy/tagging/`)
- `models.py`:
  - `TagModel` table `tags`: `id, workspace_id, key String(128), value String(256) NULL, normalized_key, normalized_value NULL, created_by, created_at, updated_at, version`. Indexes: `uq_tags_ws_norm` UNIQUE `(workspace_id, normalized_key, normalized_value)` with **`postgresql_nulls_not_distinct=True`** (so value-less tags dedup); two trigram GIN indexes (`gin_trgm_ops`) on `normalized_key`/`normalized_value` for autocomplete; `ix_tags_ws_created_by`.
  - `TagLinkMixin`: `assigned_by UUID`, `assigned_at` (server default now).
  - **6 link tables**, composite PK `(entity_id, tag_id)`, both FKs `ON DELETE CASCADE`, `ix_<t>_tag_id`: `ProteinTagLinkModel`(`protein_tags`.protein_id→proteins.id), `GeneTagLinkModel`(`gene_tags`), `TargetTagLinkModel`(`target_tags`), `OrganismTagLinkModel`(`organism_tags`), `StrainTagLinkModel`(`strain_tags`), `ProteomeTagLinkModel`(`proteome_tags`).
- `tag_repository.py` — `SQLAlchemyTagRepository`. `get_or_create` via `pg_insert(...).on_conflict_do_nothing` on the norm index, re-select winner on race. `search` orders by usage count (see `tag_links_all` view), supports `"key=value"` split + LIKE-escaped substring on casefolded columns.
- `tag_link_repository.py` — `SQLAlchemyTagLinkRepository` base (class attrs `link_model, entity_model, entity_id_attr`) + 6 subclasses + `_REGISTRY` + `get_tag_link_repository()` + `SQLAlchemyTagLinkRepositoryProvider`. **`entity_exists_in_workspace` uses the global-or-mine predicate** (`workspace_id IN (ws, GLOBAL_WORKSPACE_ID)`). `OrganismTagLinkRepository` additionally requires `merged_into_id IS NULL` (organisms tombstone on merge). `repoint` copies-then-deletes source links, workspace-defended.
- `tag_browse_repository.py` — `SQLAlchemyTagBrowseRepository` implements `TagBrowseReader`: `UNION ALL` across the 6 link tables, each joined to its entity table for a display `label` (Protein→`primary_accession`; Gene→`primary_name`; Target→`name`; Organism/Strain→scientific name/name; Proteome→`uniprot_proteome_id`), grouped, `match_all` via HAVING count, ordered `assigned_at desc`.
- `tag_filter.py` — `tag_filter_subquery(link_model, entity_id_attr, tag_ids, match_all)` shared builder (any = distinct; all = group-by/having-count). Reused by the six entity list repos.
- `tag_links_all` — read-only `UNION ALL` view over the 6 link tables (usage-count ordering for `search`). Declared via `table()/column()` so Alembic ignores it; created/dropped in the migration by raw SQL.

**Interface — `interface/routes/tags.py`** (two routers, registered in `interface/app.py::create_app()`)
- Management `APIRouter(prefix="/api/v1/tags", tags=["tags"])`:
  - `GET /api/v1/tags?q=&mine=&limit=` → list
  - `PATCH /api/v1/tags/{tag_id}` (`{key, value}`) → rename
  - `POST /api/v1/tags/{tag_id}/merge` (`{target_tag_id}`) → merge
  - `DELETE /api/v1/tags/{tag_id}` → 204
  - `GET /api/v1/tags/entities?tags=&tag_logic=any|all&types=&limit=` → cross-entity browse
- Per-entity assignment `APIRouter(prefix="/api/v1", tags=["tags"])`, generic over `{entity_collection}` (plural→enum map `{proteins, genes, targets, organisms, strains, proteomes}`). **`entity_id` is the entity's UUID `id`** (proteins are addressed by accession in the UI, but the assignment endpoint keys by UUID — the FE passes `protein.id`):
  - `GET /api/v1/{entity_collection}/{entity_id}/tags` → `list[EntityTagResponse]`
  - `POST /api/v1/{entity_collection}/{entity_id}/tags` (`{key, value}`) → 201
  - `PUT /api/v1/{entity_collection}/{entity_id}/tags` (`{tags:[{key,value}]}`) → reconcile
  - `DELETE /api/v1/{entity_collection}/{entity_id}/tags/{tag_id}` → 204
- DTOs (Pydantic, inline): `TagResponse`, `EntityTagResponse`(+assigned_by/assigned_at), `TaggedEntityResponse`, `AssignTagBody`, `RenameTagBody`, `MergeTagBody`, `TagItemBody`, `SetEntityTagsBody`.

**Wiring**
- DI: `infrastructure/di/_workspace_config.py` binds the tagging handlers (build UoW + `SQLAlchemyTagRepository` + `SQLAlchemyTagLinkRepositoryProvider(uow)` + dispatcher); called from `di/container.py`.
- FastAPI deps: `interface/dependencies/_workspace_config.py` → `Annotated[UseCase, Depends(...)]` aliases, re-exported from `dependencies/__init__.py`.
- Register both routers in `interface/app.py`.
- Add the new models module to `infrastructure/persistence/sqlalchemy/metadata.py` (required for Alembic autogenerate + view lifecycle).
- If tags can be set during bulk import, dispatch events in the arq worker too — **not needed here** (tagging is user-driven only). `ponytail:` skip.

**Migration — `backend/alembic/versions/<rev>_tagging.py`**
- `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
- `tags` table + norm unique index (`nulls_not_distinct`) + 2 trigram GIN + `ix_tags_ws_created_by`.
- 6 link tables (composite PK, cascade FKs, tag_id index).
- `tag_links_all` view (raw SQL, both `upgrade`/`downgrade`).
- **No backfill** — prot-cellar has no legacy tag column (chem-cellar's `047`/`048` legacy-string migration has no analog here). Skip.

### Frontend

Next.js App Router; `src/features/tagging/`; orval `tags-split` client + hand-written hooks over `customInstance`; shared `TagChip`.

**`src/features/tagging/`**
- `types/index.ts` — `TaggableEntity` = union of the 6 plural URL segments; `Tag = TagResponse`; `EntityTag = EntityTagResponse`; `TagInput = AssignTagBody`.
- `hooks/`:
  - `use-tags.ts` — `useTags({q, mine, limit})`; `useRenameTag`/`useDeleteTag`/`useMergeTags`.
  - `use-entity-tags.ts` — `useEntityTags(entity, id)`, `useAssignTag(entity, id)`, `useUnassignTag(entity, id)`; invalidate `["entity-tags", entity, id]` + `["tags"]`.
  - `use-tag-entities.ts` — `useTagEntities(tagIds, tagLogic, types?)`; exports `TaggedEntity = TaggedEntityResponse`.
- `components/`:
  - `tag-browse.tsx` (`TagBrowse`) — cross-entity browse: `TagFilter` + per-type facet chips (counts + color) + data grid; type→detail-route map.
  - `tag-list.tsx` (`TagList`) — admin management table: search, rows of `TagChip`, admin Rename/Merge/Delete with confirm.
  - `tag-filter.tsx` (`TagFilter`) — `{tagIds, tagLogic}` popover, multi-select combobox, any/all toggle, clear.
  - `tag-autocomplete.tsx` (`TagAutocomplete`) — `field: "key"|"value"`, distinct-value suggestions from `useTags`, Enter to commit.
  - `tag-merge-dialog.tsx`, `tag-rename-dialog.tsx`.
  - `tags-relation.tsx` (`TagsRelation`) — the inline detail-page editor: renders `TagChip`s with `onRemove`→`useUnassignTag`; a "+ Tag" popover with two `TagAutocomplete` (key+value) → `useAssignTag`. Generic over `TaggableEntity`.
- `index.ts` — barrel exporting `TagBrowse`, `TagList`, `TagsRelation`.

**Shared — `src/shared/components/tag-chip.tsx`** — `TagChip` pill: `{tagKey, value, onRemove?, onClick?}`; renders `key`(colored) `=` `value`, optional × and click-to-filter.

**Orval** — regenerate after backend is live: refresh `openapi.json`, `pnpm generate:api` → `src/shared/lib/api/tags/tags.ts` + model files. Generated files committed.

**Detail pages — mount `TagsRelation`:**
- Protein: `features/protein-catalog/components/protein-detail.tsx` — add `<TagsRelation entity="proteins" id={protein.id} />` to the Overview side column, next to `KeywordsSection`.
- Gene: `gene-detail.tsx` — add a tags `<Card>`.
- Target: `features/target/components/target-detail.tsx`.
- Organism / Strain / Proteome: `organisms/[id]`, `strains/[id]`, `proteomes/[id]` detail components.

**List-page faceting** — add a `TagFilter` (→ `tags` + `tag_logic` query params) to the six list pages; backend list queries thread the params into `tag_filter_subquery`.

**App routes** — `app/(dashboard)/tags/page.tsx` → `<TagBrowse />`; `app/(dashboard)/admin/tags/page.tsx` → `<TagList />`.

## Testing

**Backend (pytest, mirror existing tree):** unit `tests/unit/domain/workspace_config/test_tag.py` + `test_tag_name.py`; application `tests/unit/application/workspace_config/tagging/test_set_entity_tags.py`; integration `tests/integration/test_tagging.py`, `test_tag_filtering.py`, `test_tag_admin.py` (real DB — covers the global-or-mine visibility on a GLOBAL-workspace protein *and* a workspace-scoped target); API `tests/api/test_tags.py`, `test_tag_browse.py`.

**Frontend (vitest, colocated):** `tag-chip.test.tsx`, `tag-filter.test.tsx`, `tags-relation.test.tsx`, `use-entity-tags.test.ts`.

## Deliberate simplifications (`ponytail:`)

- **No merge side-effect** carrying tags when two *entities* merge (chem-cellar's `MoleculeTagMergeSideEffect`). Organisms have `merged_into_id`; if entity-merge tag-carryover is later needed, add a per-type `on_merge` hook. `ponytail: skip entity-merge tag carryover; add a side-effect hook when entity merge ships.`
- **No legacy backfill** — no pre-existing tag column exists to migrate.
- **No arq-worker event dispatch** — tagging is user-driven, never set during bulk import.

## Build order (dependency-first)

1. Domain (`TagName`, `Tag`, enum, events, repo protocols) + unit tests.
2. Persistence (models, migration, repos, filter/browse, view) + integration tests.
3. Application handlers + tests.
4. Interface routes + DI/deps wiring + app registration + API tests.
5. Regenerate openapi/orval.
6. Frontend: `TagChip`, hooks, `TagsRelation`, mount on 6 detail pages + tests.
7. Frontend: `TagFilter` on 6 list pages + backend list-param threading.
8. Frontend: `TagBrowse` + `TagList` + admin/browse routes.
