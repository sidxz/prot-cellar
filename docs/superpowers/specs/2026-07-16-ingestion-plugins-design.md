# Ingestion Plugins — Design

**Date:** 2026-07-16
**Status:** Draft (design only; no code). Decisions captured for review.
**Scope:** A plugin architecture for populating prot-cellar's target-biology facts
(the 8 record types from `2026-07-15-target-biology-data-model-design.md`) from
heterogeneous, partly-unknown sources — curated files, external databases, and
AI/literature-mining tools — with each plugin **visible, runnable, and tracked
from the frontend**, and every value it writes **colored by how it was produced**
(human vs database vs AI). The pattern is designed to be replicated across the
sibling apps (chem-cellar, DAIKON gen3).

This is the planned evolution of the Import Hub
(`2026-06-22-import-hub-design.md`), which deliberately hardcoded 3 importers and
noted a *"registry-driven param descriptor endpoint is a future option if
importer count grows."* Plugins are that growth.

---

## 1. Context & goal

The 8 target-biology record types (Essentiality, Vulnerability, Hypomorph, CRISPRi
Strain, Resistance Mutation, Protein Production, Protein Activity Assay,
Unpublished Structure) get filled two ways: a human types a value, or a value is
loaded from an external source. The external sources are **not knowable up front** —
a database dump, a published supplementary table, an AI literature-mining tool —
and they **vary per strain and per organization**. We want adding a new source to
be "write one small plugin," not "touch the core," and we want the app to show,
honestly and visibly, that an AI-suggested value is not the same as a
human-curated one.

Goal: **adding an ingestion source = one self-contained plugin**; running it is a
frontend action with live status; and its output is stamped with provenance that
drives a color in every table where the data appears.

The design borrows the *clean parts* of docu-store's plugin system (a small
manifest/protocol/registry, config-driven discovery, a `GET /plugins` catalog the
UI introspects, per-plugin settings) but **inverts its isolation model**:
docu-store plugins are reactive enrichers that write their *own* side-collections
and never touch core; prot-cellar plugins **write core** (the target-biology
tables) on demand. Safety therefore comes not from separate storage but from the
**ingestion contract + provenance stamp + run-scoped lineage**.

## 2. Decisions locked

| Decision | Choice | Why |
|---|---|---|
| Execution locus | **In-tree, contract-shaped** | Plugins are in-worker adapters implementing a stable protocol + a canonical envelope, run by the existing Import Hub job runner. The envelope serializes 1:1 to an HTTP payload, so an external "push" endpoint can wrap the *same* handler later. Fastest to ship (reuses everything); not a dead-end for external/AI plugins. |
| Trust model | **Live, but colored** | Plugin output lands directly in the tables, colored by generation-method. The color *is* the "trust this less" signal; coloring only matters if the data is actually shown. No review-queue workflow to build. Escape hatches (§8) make it safe. |
| AI signal | **New orthogonal `generation_method` field**, not a new `source_type` member | `source_type` = *publication status* (published/preprint/…); how a value was produced is a different axis. An AI can extract a value from a *published* paper — both facts must survive. |
| Color granularity | **Per-record** (a row), not per-field | Provenance is stored once per record. Per-field provenance is a much heavier schema for a marginal gain. A human edit flips the whole record to `manual` → black. |
| Registry | **Generalize the existing import adapter registry** | `ImportType` enum + `IMPORT_ADAPTERS` map + the FE form-switch become an open, manifest-driven plugin registry. The 3 current importers stay working; they gain a manifest incrementally. |
| **UI revamp** | **Yes — scoped** (§9) | Plugins shift the model from "3 fixed importers, static forms" to "an open catalog with rich metadata + provenance color." That is a real IA change. Revamp the 3 surfaces the current UI can't express; reuse the monitor/history that already works. |
| **First plugin** | **DeJesus essentiality** | Its machinery mostly exists (DeJesus XLSX→TSV normalizer + essentiality CSV parser + `BulkUpsertEssentiality`). The reference plugin *wraps known-good code*, proving the abstraction against a path that already works. |
| Cross-app kit | **prot-cellar first; extract later** | Build cleanly here with the contract separated; copy to chem-cellar the 2nd time, extract a shared package the 3rd (rule of three). Building the shared abstraction from one example builds the wrong one. |
| Trigger | **Manual (frontend) only** | Matches the Import Hub. Scheduled/reactive triggers are deferred; nothing here precludes them. |

## 3. The model — three concepts

1. **Plugin** — a `manifest()` (declarative: who I am, which record types I fill,
   what params I need, my default generation-method, secrets I require) + an
   `async run(ctx)` that fetches and formats records. Lives in-tree today; the
   same shape can run out-of-process later without changing the contract.
2. **The Envelope (the contract)** — the canonical package a plugin produces and
   hands to a **sink**: `{record_type, records[], generation_method, dry_run}`.
   In-tree, the sink calls the existing `BulkUpsert<X>Command`. Later, an external
   plugin's sink is an HTTP client POSTing the *identical* JSON envelope. This is
   the portable boundary — the "contract-shaped" promise.
3. **Run** — literally an `ImportRun` row. Reused wholesale: status
   (`QUEUED → RUNNING → SUCCEEDED | FAILED`), phase, `processed/total` progress,
   `summary`, `error`, `requested_by`, `upload_ref`, timestamps — plus the FE that
   already polls every 2s and renders a progress bar.

## 4. The contract — envelope + sink

The plugin author writes **fetch-and-map only**. They map source rows to the
existing per-record import DTO (e.g. `EssentialityImportRecord{locus_key,
classification, condition, method, confidence, pmid, dataset}`) — the DTO already
carries the citation/evidence fields the plugin knows — and call:

```
await ctx.sink.upsert("essentiality", records)     # records: list[EssentialityImportRecord]
```

The **framework**, not the plugin, attaches:

- `generation_method` (from the manifest default, or a per-call override),
- **run lineage** — `source_run_id` (the `ImportRun` id), plugin id + version,
- the target `workspace_id` (§5),

and reports `processed/total` progress onto the run. The sink is the single seam:

- **In-tree sink** → resolves `record_type` → the matching `BulkUpsert<X>Command`
  (idempotent upsert by natural key; gene-side resolves `locus_key` + tax-id,
  protein-side resolves `accession`) → returns per-row `ItemResult`s, which merge
  into the run's `summary` (created/updated/skipped/failed). `dry_run` flows
  straight through to the command's existing dry-run path.
- **HTTP sink** (future) → POSTs the same envelope to a bulk-ingest endpoint that
  invokes the same command handler server-side. Building it is deferred until the
  first external plugin exists; the envelope is *shaped* for it now.

Because the envelope is record-typed, one plugin can fill more than one record
type, and two different plugins (a DB scraper and an AI miner) can fill the *same*
record type through the same doorway — differing only in `generation_method`, and
therefore in color.

## 5. Provenance & color model

### The field
Add one field to the shared `Provenance` VO
(`domain/shared/provenance.py`):

```
generation_method: GenerationMethod   # manual | imported | ai_extracted | ai_predicted | computed
```

- `manual` — a human typed/curated it (the current default for hand-edited rows).
- `imported` — loaded verbatim from an external database/dataset (DeJesus,
  Mycobrowser).
- `ai_extracted` — an AI pulled a *stated* value out of a source (e.g. an
  essentiality call written in a paper).
- `ai_predicted` — an AI *inferred* a value not directly stated.
- `computed` — a deterministic pipeline derived it.

This is **orthogonal to `source_type`** (published/preprint/private_comm/internal/
patent). Example: DeJesus 2017 → `source_type=published`, `generation_method=imported`.
A future LLM miner reading that same paper → `source_type=published`,
`generation_method=ai_extracted`.

### The color
The UI maps `generation_method` → visual treatment. v1 needs only one loud
distinction — AI vs the rest:

| method | v1 treatment |
|---|---|
| `manual` | foreground / black (default) |
| `imported`, `computed` | neutral / muted |
| `ai_extracted`, `ai_predicted` | **blue** |

The field supports finer splits later (e.g. distinguishing `imported` from
`manual`, or predicted from extracted) without a schema change. **Honesty rule:** a
human edit to a plugin-loaded row sets `generation_method = manual` — a person now
stands behind it, so it turns black.

### Lineage (operational, separate from the scientific VO)
Every row a plugin writes is stamped with `source_run_id` (indexed) via the
existing import-lineage layer (`ProvenanceMixin` — distinct from the scientific
`Provenance` VO, per the target-biology design §4). This drives trace/undo (§8)
and is not shown as color.

### "Per strain" and "per organization" — already modeled
The user's two variation axes map onto existing fields, no new machinery:

- **Per strain** → the organism/tax-id run parameter (gene-side resolution is
  already organism-scoped; default tax-id 83332, M. tuberculosis H37Rv).
- **Per organization** → the target `workspace_id` on each record. Published
  sources default to `GLOBAL_WORKSPACE_ID`; a lab's private import targets that
  lab's workspace. Visibility already respects `workspace_id`.

## 6. Plugin anatomy

```
plugins/dejesus_essentiality/
  __init__.py     # exports `plugin` (module-level attr, docu-store style)
  manifest.py     # the declarative contract (below)
  plugin.py       # class: manifest() + async run(ctx)
  config.py       # optional pydantic settings for secrets (PLUGIN_<NAME>_… env)
```

**Manifest** (declarative, drives the FE catalog + validation):

```
PluginManifest:
    id: str                       # stable slug, e.g. "dejesus_essentiality"
    version: str                  # semver
    name: str
    description: str
    target_records: list[str]     # which of the 8 types it fills, e.g. ["essentiality"]
    default_generation_method: GenerationMethod   # e.g. imported
    params: list[ParamField]      # the constrained param descriptor (below)
    requires_secrets: list[str]   # env keys ops must set (for a "needs config" warning)
```

**`ParamField`** — a *constrained* descriptor, **not** arbitrary JSON Schema. A
small closed set of field types covers the real cases and the FE renders each
without a schema-form library (the import-hub design's rejected complexity):

```
ParamField: { key, label, type, required, default?, options?, help? }
  type ∈ { string | number | enum | organism | file_upload | bool }
```

`organism` renders the existing organism combobox; `file_upload` reuses the
existing `POST /uploads` → `upload_ref` flow. This descriptor is what the FE
fetches from `GET /api/v1/plugins` to build the run form dynamically.

**Protocol** (structural, docu-store style — plugins match a shape, no base class):

```
class IngestionPlugin(Protocol):
    @staticmethod
    def manifest() -> PluginManifest: ...
    async def run(self, ctx: PluginRunContext) -> None: ...
```

`PluginRunContext` gives the plugin: validated `params`, resolved `organism_id`,
`load_upload(upload_ref)`, the `sink`, a `progress(processed, total, phase)`
reporter, and a service auth identity — mirroring the current `ImportRuntime`.

**Discovery/registration** — config-driven, in-tree: an `ENABLED_PLUGINS` list +
`importlib` pulling each package's module-level `plugin` attribute into a registry
(docu-store's loader, minus Kafka/Temporal). `GET /api/v1/plugins` returns the
manifests. The 3 existing importers register as built-in plugins (each gains a
manifest); their adapters are unchanged.

## 7. Execution model & the ladder

A plugin run *is* an `ImportRun`, executed by the existing arq worker
(`run_import(ctx, import_run_id)`): load run → `start()` → resolve plugin from the
registry → build `PluginRunContext` → `await plugin.run(ctx)` → `succeed(summary)`
or `fail(error)`. No new execution engine.

The user's "separate workers, Temporal later" is a **ladder you climb only when it
hurts** — the contract makes every rung swappable without touching plugins or FE:

1. **Now (arq):** the worker is already a separate process. A second arq worker on
   its own queue name isolates slow AI plugins from fast imports — a config change.
2. **Later (dedicated worker):** a worker box with the heavy plugin's own deps
   installed (this is the one real cost of in-tree plugins — shared Python deps).
3. **Eventually (Temporal), only if needed:** durable, resumable, retrying
   long-running workflows — and it dissolves the current **arq default 300s
   `job_timeout`** gap (no `job_timeout` is set today; a long AI-mining run would
   be aborted mid-flight). Until then, set an explicit `job_timeout` on
   `WorkerSettings` as a one-line stopgap.

## 8. Safety under "live but colored"

No review queue; three cheap escape hatches instead:

- **Trace / undo by run** — every row carries `source_run_id`, so "show everything
  run X loaded" is a query. v1 = trace + visibility + manual edit/delete. **Undo
  button (delete rows a run *created*) is v1.1**; reverting *updates* is deferred.
- **Dry-run preview** — the bulk-upsert `dry_run` already runs the full
  resolve+match loop without committing, returning would-be created/updated/
  skipped/failed counts. The run flow exposes this as a **Preview** step before
  commit (§9).
- **Human edit flips to black** — editing a plugin-loaded row sets
  `generation_method = manual`, both correcting the value and re-attributing it.

Per-record failures stay `failed` `ItemResult`s in the run summary (existing
behavior) — one bad row never aborts a run. An unhandled plugin exception marks
the run `FAILED` with the captured error; the row remains for inspection.

## 9. UI — the revamp (scoped)

**Decision: revamp the three surfaces the current UI structurally cannot express;
reuse the monitor/history that already works.** Visual execution will use the
`frontend-design` skill at implementation time; this section fixes *scope and IA*,
not pixels.

**Tier 1 — build (new surfaces the current UI can't express):**

1. **Plugin catalog** — the discovery front door, fed by `GET /api/v1/plugins`.
   Plugins as cards, filterable by *what they fill* (the 8 record types) and by
   *source kind*. Each card carries identity: name, description, a **source-kind
   chip in the provenance color language** (an "AI" chip is blue, matching the data
   it produces), last-run status, and a "needs config" badge if a required secret
   is unset. Replaces the 3-card static picker; scales to an open set.
2. **Run flow with dry-run preview** — selecting a plugin opens a focused panel:
   the param form **rendered from the manifest's `ParamField` descriptor**, then a
   **Preview (dry-run)** showing "would create N / update M / skip K / fail J"
   *before* committing. A genuine safety+legibility upgrade over the current
   submit-and-hope form, and it pays off the live-but-colored model.
3. **Provenance made visible in the data** — the payoff, on the gene/protein
   detail pages (`editable-record-table.tsx` → `provColumns`): the **Source cell
   becomes a colored badge** driven by `generation_method` (one edit recolors all
   8 record tables; the codebase already has a value→badge-variant helper to
   copy), plus a small **legend** and a **provenance tooltip** (plugin, run, date,
   citation). Optional per-table **"hide AI predictions"** filter.

**Tier 2 — reuse + light polish (already works):**

- Run monitor / detail drawer / live progress bar / runs table — keep. Enhance the
  summary to surface the created/updated/skipped/failed breakdown already present
  in `ItemResult`, and add source-kind color chips for consistency.

**Tier 3 — NOT building (YAGNI):** no marketplace ratings/install, no drag-drop
pipeline builder, no scheduling UI, no per-plugin analytics dashboards.

## 10. First plugin — DeJesus essentiality (the reference vertical)

**Why it's the right first plugin:** most of its pieces already exist, so it proves
the *plugin abstraction* against a known-good path rather than proving two new
things at once. It also demonstrates the **file-upload plugin shape** (a human
drops a published supplementary file), the counterpart to the future
**fetch-from-API shape** (Mycobrowser/UniProt).

**What already exists (the plugin wraps, not rebuilds):**

- A DeJesus XLSX/CSV → TSV normalizer (`dejesus_xlsx.essentiality_upload_to_tsv`,
  reachable today via `POST /api/v1/imports/uploads`).
- The essentiality CSV parser (`parse_essentiality_csv`) + `BulkUpsertEssentiality`
  command (idempotent on `(gene_id, condition, method)`), gene-side, organism-scoped.
- The CLI `scripts/import_essentiality.py`.

**The plugin:**

- **Manifest:** `id="dejesus_essentiality"`, `target_records=["essentiality"]`,
  `default_generation_method=imported`, params = `organism` (tax-id, default 83332)
  + `file_upload` (the DeJesus table) + optional `condition` string.
- **`run(ctx)`:** `load_upload` → normalize → `parse_essentiality_csv` → map to
  `EssentialityImportRecord`s with `provenance.source_type=published` citing DeJesus
  2017 (PMID) → `ctx.sink.upsert("essentiality", records)`. The framework stamps
  `generation_method=imported` + `source_run_id`, and reports progress.

**Relationship to the existing GENE_ENRICHMENT importer:** GENE_ENRICHMENT today
bundles location + context + essentiality into one run writing gene annotations
(and per the target-biology design is being repointed to write `Essentiality`
records). This plugin is the **first step of unbundling** that monolith into
focused, individually-runnable, provenance-stamped sources. GENE_ENRICHMENT keeps
working; the plugin is the targeted path.

**First AI plugin (later, illustrative — not this slice):** an LLM essentiality
miner would target the *same* `"essentiality"` doorway with
`default_generation_method=ai_extracted`, and its rows would render **blue** — the
same target, a different method, a different color. That is the whole design in one
picture.

## 11. Cross-app portability

The reusable core is: the **manifest + protocol + registry**, the **envelope +
sink** boundary, the **`generation_method` provenance field + color mapping**, and
the **catalog/run/monitor UI pattern**. Build it cleanly in prot-cellar with the
contract separated from prot-cellar specifics (the 8 record types, tax-id
resolution). Copy the pattern to chem-cellar the **second** time it's needed;
extract a shared package the **third**. Do not build the cross-app kit from one
example.

## 12. Integration seams (concrete)

- Provenance VO + enum: `backend/src/protcellar/domain/shared/provenance.py`
  (add `generation_method`); JSON mapping
  `.../persistence/sqlalchemy/target_biology/_provenance_json.py` (both directions);
  API bodies `interface/routes/target_biology.py` (`ProvenanceResponse`,
  `ProvenanceBody.to_domain`); regenerate the Orval client
  (`frontend/src/shared/lib/api/model/`).
- Bulk-upsert doorway: `application/target_biology/bulk_upsert_*.py`,
  `_import_support.py` (locus index + `ItemResult`),
  `infrastructure/ingestion/csv_table.py` + per-record `*_csv.py` parsers.
- Registry seam: `infrastructure/ingestion/import_adapters.py` (`IMPORT_ADAPTERS`,
  `ImportAdapter`) + `domain/imports/enums.py` (`ImportType`) →
  generalize to a manifest-driven plugin registry; `application/imports/registry.py`
  is the intended home per the import-hub design.
- Run/job: `domain/imports/import_run.py`, `.../persistence/sqlalchemy/imports/models.py`
  (`ImportRunModel`, `ImportUploadModel`), `interface/routes/imports.py`,
  `application/imports/{start_import,params,progress_reporter}.py`,
  `infrastructure/ingestion/{worker.py,arq_enqueuer.py}` (set an explicit
  `job_timeout`).
- FE: `frontend/src/features/import-hub/**` (hooks/`use-imports.ts`,
  `start-import-dialog.tsx`, `import-detail.tsx`, `types/index.ts`) → catalog +
  descriptor-driven run form + dry-run preview; target-biology display
  `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx`
  (`provColumns`) + `gene-detail.tsx` / `protein-detail.tsx`.

## 13. Out of scope / deferred (YAGNI)

- External HTTP push endpoint (the envelope is *shaped* for it; build when the
  first external plugin exists).
- Kafka / Temporal (climb to Temporal only when a plugin needs durable long runs).
- Review/approval queue (add a per-plugin `requires_approval` flag later only if a
  source proves too noisy).
- Per-field provenance; per-plugin dependency isolation; scheduled/reactive
  triggers; the shared cross-app package.
- Automated undo-a-run button (v1.1); reverting *updates* (later).
- The extensions registry / JSON-Schema validation (already deferred upstream).

## 14. Phased build order

1. **Provenance field** — add `generation_method` to the VO + JSON mapping + API
   bodies; regenerate the FE client. Recolor the Source cell (all 8 tables) +
   legend + tooltip. *Ships value on its own: existing data gets honest coloring.*
2. **Plugin contract in-tree** — `PluginManifest` / `IngestionPlugin` protocol /
   registry / `PluginRunContext` / the in-tree sink over `BulkUpsert<X>`; generalize
   the run adapter resolution off the fixed `ImportType`. Set `job_timeout`.
3. **DeJesus essentiality plugin** — the reference vertical, wrapping the existing
   normalizer + parser + command; stamps `generation_method=imported` + lineage.
4. **UI Tier 1** — catalog (`GET /plugins`), descriptor-driven run form, dry-run
   preview. Reuse the monitor/history (Tier 2 polish).
5. *(optional/next)* second plugin of the fetch-from-API shape; then the AI miner
   (proves the blue path); then per-app copy → extraction.

## 15. Testing (minimal, per the house pattern)

- Domain: `generation_method` on the VO round-trips through
  `_provenance_json.py`; edit flips method to `manual`.
- Registry: a manifest with each `ParamField` type validates good params and
  rejects bad; unknown plugin id → error.
- Sink: `sink.upsert` routes a record type to the right `BulkUpsert<X>` and stamps
  method + `source_run_id`; `dry_run` commits nothing.
- Plugin: the DeJesus plugin over a fixture file drives `QUEUED→RUNNING→SUCCEEDED`,
  produces N essentiality records with the DeJesus citation and
  `generation_method=imported`; a bad file → `FAILED` with a captured error.
- FE: catalog renders manifests; the descriptor renders each field type; the
  Source badge color maps from `generation_method`. (`tsc`/`vitest`/`biome` via
  `./node_modules/.bin`.)
- Full gates: `make test` (incl. import-linter — the plugin/registry code must not
  break bounded-context independence), `make test-api`, `make lint`.

## 16. Final step (the acceptance demo)

Open the app → **Plugins** → pick **DeJesus essentiality** → choose the organism
(M. tuberculosis H37Rv) and drop the published DeJesus supplementary table →
**Preview** shows would-create/update counts → **Run** → watch live progress →
open a gene detail page and see its Essentiality record, its Source cell rendering
the provenance, editable by a human (which flips it to `manual`). The same run is a
tracked `ImportRun` with a summary and audit trail, and every row it wrote is
traceable by `source_run_id`.
