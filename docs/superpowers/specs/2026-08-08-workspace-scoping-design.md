# Workspace scoping, bulk target-biology read, and parent validation — design

**Date:** 2026-08-08
**Status:** approved, ready for planning
**Follows:** `docs/superpowers/plans/2026-08-07-target-biology-api-hardening.md` (write-surface hardening,
branch `feat/target-biology-hardening`, awaiting final review).

## Problem

Every row in this database currently belongs to the reserved sentinel workspace
`00000000-0000-0000-0000-000000000000`: 34,280 genes, 161,070 proteins, 4,010 essentiality records,
3 organisms, 4 proteomes, 3 strains, 3 import runs. There is exactly one effective workspace.

**Tenancy is not missing — it is bypassed.** The machinery is built and correct:
`BaseRepository.find_by_id_in_workspace`, `_owns`, `delete(workspace_id, id)`, a save-time guard that
rejects a workspace change on an existing row, and `require_same_workspace` used at 42 call sites.
The Target context already does it properly. The other contexts opt out by passing
`GLOBAL_WORKSPACE_ID` at ~70 source call sites, and their list queries carry no workspace predicate
at all — `GeneRepository.list_by_organism` builds `select(GeneModel).where(organism_id == …)` and
nothing more.

The consequence is that a record whose provenance says `private_comm` is readable by everyone. One
such record exists today (a vulnerability observation). `Unpublished Structure` is a whole record
type, and `internal` and `private_comm` are first-class `source_type` values — the data model
anticipates private observations that the storage layer cannot keep private.

Two smaller defects travel with this:

- **No bulk read of target-biology.** `GET /genes/{id}/target-biology` is per-gene only; there is no
  list endpoint. A consumer wanting essentiality across a proteome would need one request per gene
  (34,280 today). Bulk *write* exists via the ingestion plugins; bulk *read* does not.
- **No parent validation on create.** `create_essentiality` takes `gene_id` from the URL path and
  never looks it up, so a record can be attached to a UUID that has never existed. (Orphaning by
  *deletion* is largely theoretical — the service has only two DELETE endpoints, `/tags/{id}` and
  `/target-biology/{kind}/{record_id}`; there is no gene or protein delete.)

## Decisions

| Question | Decision |
|---|---|
| Tenancy model | **Uniform check, shared reference workspace.** Every row has a real `workspace_id` and every read filters. Reference data is owned by a designated shared workspace; reads resolve `workspace_id IN (caller, shared)`. No duplication of reference data, gene UUIDs stay stable, and a workspace *can* own a private gene from day one. |
| Shared writes | **Imports only.** Ingestion paths write shared; every API write lands in the caller's workspace. No promotion endpoint. |
| Delivery | **One spec, three phases**, tenancy backbone first. |
| Existing private data | Goes to the `saclab-dev` workspace, not shared. |

## 0. The premise, now confirmed

This design rests on one property: **`AuthContext.workspace_id` carries a real, stable workspace id**,
not a placeholder. Sentinel issues it in the authz token, every service in the realm
(`daikon-siblings`) validates the same token, and the same workspace therefore presents the same id
everywhere it is used. Confirmed against real data in this realm: `saclab-dev` — the workspace this
deployment runs as, and the name the UI header displays — is
`442df0cf-e618-4938-a089-80ae2f1e43e7`.

That value has never reached this database. Every row here carries the sentinel instead, which is
why the property has not been exercised. **Re-confirm it from a live token as the first act of Phase
1** — it is a single field read, and the entire model rests on it. If the id turns out to be absent
or unstable, stop: the design needs a mapping layer and this document is wrong.

## 0b. Deployment reality: this is dev

The only deployment is `saclab-dev`, and its data is reproducible — the catalog comes from UniProt,
NCBI and Mycobrowser imports, and the target-biology records from the DeJesus dataset plus a handful
of manual rows. **A botched migration is recoverable by re-importing.**

That does not change the design — the two-migration split in §1.6 exists because the constant and its
stored value are only correct together, and because reclassifying before reads filter is a no-op that
*looks* like success. Both are correctness arguments, not data-safety ones.

It does change how much ceremony the implementation needs: write `downgrade()` because it is cheap
and it documents intent, but do not build elaborate rollback tooling, do not stage the migration
across releases, and do not let fear of the data slow the work down. Live QA may be destructive;
clean up after.

## 1. Tenancy backbone

### 1.1 A distinct shared workspace id

Replace `GLOBAL_WORKSPACE_ID = uuid.UUID(int=0)` with

```python
SHARED_WORKSPACE_ID: uuid.UUID = uuid.UUID("a577f0f9-b1fb-53b6-be5d-49bcb500adeb")
# uuid5(NAMESPACE_DNS, "shared.protcellar") — deterministic, reproducible, and
# deliberately not the null UUID.
```

The null UUID is indistinguishable from *unset*. If a code path forgets to assign `workspace_id`, or
a column default fires, that row silently becomes world-readable — the exact failure this work
exists to prevent. With a distinct id, a forgotten assignment yields a row visible to **nobody**:
safe, and loud enough to find. The null UUID is also what the audit handler writes for an unknown
user, so the two meanings currently collide.

Keep the old name as a deprecated alias only if something outside this repo imports it; nothing does,
so delete it.

### 1.2 Two predicates, not one

This is the security core of the design.

```python
def readable_by(model, workspace_id):        # reads
    return model.workspace_id.in_((workspace_id, SHARED_WORKSPACE_ID))

def owned_by(model, workspace_id):           # mutations
    return model.workspace_id == workspace_id
```

Reads use the first; every mutation uses the second. Shared reference data is therefore **readable by
all tenants and mutable by none through the API**. Collapsing these into one predicate would let any
tenant edit UniProt-derived data for everyone — it is the single most important thing for a reviewer
to check.

### 1.3 Where enforcement lives

Three places, not seventy:

- **`BaseRepository`** — `find_by_id_in_workspace` splits into `find_readable(workspace_id, id)` and
  `find_owned(workspace_id, id)`. Get paths use the former; update and delete use the latter. `_owns`
  keeps `owned_by` semantics.

  **`save()` is deliberately left alone.** An earlier draft of this spec had it refuse writes to
  shared rows; that is unimplementable, because `save()` is called by the ingestion paths
  (`bulk_upsert_genes`, `bulk_upsert_proteins`, `bulk_enrich_genes`) which legitimately write shared
  aggregates, and the repository cannot tell an import from an API call. The real guarantee comes
  one level up: an API mutation loads its target through `find_owned(auth.workspace_id, id)`, so a
  shared row is simply never found and the request 404s. One enforcement point, not two. `save()`'s
  existing workspace-mismatch guard and its `workspace_id` predicate in the UPDATE remain as
  defence-in-depth.
- **The six repositories with list/search methods** — `gene_repository`, `import_run_repository`,
  `tag_repository`, `organism_repository`, `proteome_repository`, `audit_repository` — apply
  `readable_by` in their query builders.
- **Application use cases** — take `workspace_id` from `auth.workspace_id` instead of the sentinel.

The ~70 source sentinel sites split two ways, and that split is the bulk of the work:

| Path | Writes |
|---|---|
| User-facing use cases (create/update/delete via HTTP) | `auth.workspace_id` |
| Ingestion and import (`infrastructure/ingestion/`, the arq worker, `scripts/`) | `SHARED_WORKSPACE_ID` |

### 1.4 What stays unscoped, and why that is principled

The rule is **every tenant-visible *aggregate* is workspace-owned**. These are not aggregates and get
no `workspace_id`:

- **Child rows** — `protein_features` (1.1M), `protein_comments`, `protein_citations`,
  `protein_isoforms`, `protein_keywords`, `protein_cross_references`, `organism_names`,
  `proteome_proteins`, `target_components`, and the six tag-link tables. Each is reachable only
  through its parent, and the parent is scoped. Adding a column to 1.1M feature rows buys nothing.
  **Invariant, to be written down and tested:** *a child row is only ever loaded through a
  workspace-scoped parent query.*
- **`go_terms` / `go_edges`** — an external ontology. Nobody owns a private GO term.

### 1.5 Consequence: reference data becomes read-only through the API

This follows directly from §1.2 and §the "imports only" decision, and it is a real capability
removal, so it is stated here rather than discovered during implementation.

Mutations use `owned_by`. Reference data is owned by `SHARED`. Therefore **no API caller can mutate
a shared row** — not a workspace admin, not anyone. That covers:

- the 4,019 target-biology records with published/preprint provenance
- every gene, protein, organism, strain and proteome, all of which have PATCH routes today

Reference data becomes import-managed, full stop. Changing it means re-importing, which is also the
only way to keep it consistent with UniProt/NCBI/Mycobrowser in the first place.

**This is the correct outcome, not a limitation to work around.** Sentinel exposes only
per-workspace roles (`workspace_role`), so "let admins edit shared data" would mean *any tenant's
admin can rewrite reference data for every other tenant*. There is no realm-admin concept to gate it
with. Import paths run as system and remain the only writer.

**But it must not ship as dead buttons.** The record tables render edit, provenance and delete
controls on every row unconditionally; after this change those would fail on 4,019 of them.

The fix is one field. Every workspace-scoped response gains:

```python
is_shared: bool   # True when this row belongs to SHARED — reference data, not editable here
```

Not `editable`: whether a caller may edit also depends on their role, which the client already
knows. `is_shared` supplies the half the client cannot compute. And because reads only ever return
the caller's own rows plus shared ones, those two cases are exhaustive — there is no third state to
represent.

The frontend hides mutate controls when `is_shared` is true and says why, rather than offering a
control that 404s.

**Where the field is actually needed**, checked against the frontend rather than assumed: the eight
target-biology responses (the record tables render edit / provenance / delete on every row) and
`StrainResponse` (`strain-form-dialog.tsx` exists, and strains are reference data). Genes and
proteins have PATCH routes but **no edit form in the UI**, so they get the field for consistency and
nothing else changes. Targets, organizations and tags become workspace-owned, so their existing
dialogs keep working untouched.

### 1.6 Data migration — two migrations, not one

Splitting this is what makes each half safe on its own. A single migration would have to change the
sentinel's *value* and reclassify rows at the same time, and the value change must land together with
the constant or every query goes looking for rows under an id nothing carries.

**Migration A — rename the sentinel (lands with §1.1).**
`UPDATE <every workspace-scoped table> SET workspace_id = 'a577f0f9-…' WHERE workspace_id =
'00000000-0000-0000-0000-000000000000'`. A pure value swap across ~200k rows: an UPDATE, not a
rewrite. No row changes owner in any meaningful sense and no read path filters yet, so **visibility
is provably unchanged**. This ships in the same commit as the constant, because the two are only
correct together.

**Migration B — reclassify (lands after §1.3, once every read path filters).**
Moves the rows that are not reference data out of `SHARED`:

| Rows | Destination | Why |
|---|---|---|
| `genes`, `proteins`, `organisms`, `strains`, `proteomes` and their children | stay `SHARED` | UniProt / NCBI / Mycobrowser reference data |
| Target-biology whose `provenance->>'source_type'` is `published` or `preprint` | stay `SHARED` | Public literature. 4,010 essentiality + 5 vulnerability + 4 resistance mutations |
| Target-biology whose `source_type` is `private_comm`, `internal` or `patent` | → workspace | Genuinely private observations. **One row today**, a `private_comm` vulnerability |
| `import_runs`, `import_uploads` | → workspace | Workspace artifacts — who ran what, not reference data |
| `tags`, `targets`, `organizations` | → workspace | Workspace-owned. All empty today |

Exactly one row changes visibility, which is what makes Migration B verifiable: every other
previously-readable row must still be readable, and that one must not be readable by anyone else.

The destination workspace is read from a required `MIGRATION_TARGET_WORKSPACE_ID` environment
variable **with no default** — so the migration fails loudly in a deployment where the operator has
not said which workspace inherits the existing data, rather than silently assigning it to the wrong
one. Here that is `442df0cf-e618-4938-a089-80ae2f1e43e7` (`saclab-dev`).

## 2. Bulk target-biology read

```
GET /api/v1/target-biology/{kind}
    ?organism_id=&strain_id=&gene_id=&protein_id=&cursor=&limit=
```

One generic route with `kind` in the path, mirroring the write routes. Cursor-paginated like the
other catalog lists, and filtered by `readable_by`.

- `organism_id` / `strain_id` scope the same way `/genes` and `/proteins` already do — the filters a
  catalog consumer already uses.
- `gene_id` / `protein_id` are repeatable, for fetching records for a known set.
- Response items are the same per-kind response models the bundle endpoints already return.

Consumer-agnostic: this service's own UI can use it for "every essential gene in this organism",
which the per-gene bundle cannot answer.

## 3. Parent validation on create

`POST /genes/{gene_id}/target-biology/{kind}` resolves the gene through `find_readable` and returns
**404** when it does not exist *or* is not visible to the caller. Same for
`POST /proteins/{protein_id}/target-biology/{kind}`.

One lookup closes two holes: attaching a record to a gene that never existed, and probing another
workspace's private genes by attaching records to them and observing success.

Deliberately a 404 rather than a 403 for the not-visible case — a 403 confirms the row exists.

## 4. Testing

- **The predicates, directly** — a shared row is readable by any workspace and mutable by none; a
  workspace row is invisible to a different workspace. These are the security tests; they belong in
  their own file, not scattered.
- **Cross-tenant, per context** — workspace A cannot read, update or delete workspace B's genes,
  proteins, tags, targets or target-biology records. One test per context, all following the same
  shape.
- **Child-row invariant** — loading a protein's features for a protein that is not visible returns
  nothing, exercised through the API rather than the repository.
- **Migration** — after upgrade, every row readable before is still readable by `saclab-dev`, and the
  single `private_comm` row is not readable by any other workspace. Assert on counts per table so a
  missed table fails loudly. `downgrade()` restores the sentinel.
- **Bulk read** — workspace filter applied; cursor walks the full set; an unknown `kind` is a 422
  without an upstream query.
- **Parent validation** — 404 for a nonexistent gene, and 404 (not 403) for another workspace's
  private gene.
- **Live QA** — sign in as a real user, confirm `AuthContext.workspace_id` is
  `442df0cf-e618-4938-a089-80ae2f1e43e7`, and confirm the gene list and a gene detail page still
  render every record they rendered before.

## 5. Build order

1. **`SHARED_WORKSPACE_ID` + Migration A + the two predicates + the `BaseRepository` split.** The
   constant and Migration A must land together — the new value is wrong until the data carries it,
   and the data is orphaned if it carries a value no code knows. Nothing filters yet, so behaviour is
   unchanged and the step is verifiable on its own: every existing page still renders.
2. **Use cases and repositories move to `auth.workspace_id` / `SHARED_WORKSPACE_ID`**, context by
   context: taxonomy → protein_catalog → target_biology → tagging → imports. Cross-tenant tests land
   with each context. Reads now filter, but every row is still `SHARED`, so nothing disappears.
3. **Migration B — reclassify.** Only now, once every read path filters, does moving a row out of
   `SHARED` actually restrict it. Running it before step 2 would be a no-op that looks like success.
4. **Bulk target-biology read.**
5. **Parent validation on create.**
6. **Live QA**, then the whole-branch review.

Steps 1 and 2 are each independently shippable and leave the service working. Step 3 is the only one
that changes what anyone can see, and it changes it for one row.

## 6. Implementation discipline: this branch has concurrent history

`feat/target-biology-hardening` received an independent fix wave in **`10735a1`**, from a separate
session's whole-branch review, after the work this spec builds on. It changed files this spec's
tasks also touch:

- `interface/routes/target_biology.py` — `_patch_updates`'s null branch now keeps `compound` (so a
  null **clears** the reference) while `provenance` and `ligands` keep null-means-leave-alone
- `domain/target_biology/essentiality.py` — `update()` rejects an explicitly-null `classification`
- `domain/target_biology/hypomorph.py` — `_validate` rejects an explicitly-null `growth_defect`

Those are corrections to real defects — a 500 where a 422 belonged, and a silently-ignored clear.

**Therefore: task briefs for this spec specify changes as deltas against HEAD and never reproduce a
surrounding function.** An implementer told to "write `_patch_updates` as follows" would delete the
`compound` guard and nobody would notice, because no test of *this* spec covers it. Read the file,
change the lines you own, leave the rest.

The same caution applies to `provenance-dialog.tsx`, which that commit also changed (an untouched
save is now a no-op).

## Deliberately out of scope

- **Audit attribution.** `audit_operations` already has `workspace_id`, `user_id`, `actor_type` and
  `correlation_id`, and the handler populates `user_id` with the null UUID and `field_name` with the
  literal string `"event"`. It is a real defect, and it is the notification thread's problem — a
  change feed is worthless without it. Not this change.
- **Promoting a record from a workspace to shared.** Add when someone needs it.
- **Postgres row-level security.** It would make the filter impossible to forget, but it needs a
  per-connection `SET` that fights connection pooling, and the repository surface here is small
  enough to enforce reliably.
- **`workspace_id` on child tables or GO terms** — see §1.4.
- **Per-workspace copies of reference data.** Explicitly rejected: it would duplicate ~1.5 GB per
  workspace and give the same physical gene a different UUID in each, breaking every stable external
  reference to it.
