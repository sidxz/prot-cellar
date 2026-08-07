# Target-biology API hardening

**Date:** 2026-08-07
**Status:** approved, ready for implementation
**Touches:** `interface/routes/target_biology.py`, `application/target_biology/`,
`frontend/src/features/protein-catalog/components/sections/`

## Why

Four problems in the target-biology slice, two of them live data bugs.

### 1. The record form destroys provenance on every edit

`editable-record-table.tsx` round-trips provenance through a three-field draft:

```ts
export type ProvDraft = { source_type: string; pmid: string; note: string };

provToBody(d) => ({
  source_type: d.source_type,
  citations: d.pmid.trim() ? [{ pmid: d.pmid.trim() }] : [],
  note: d.note.trim() || null,
})
```

`Provenance` carries `citations[]{pmid, doi, url, label}`, `contributor_researcher` and
`observed_on`. None of those survive an edit:

- a record with **three citations keeps one**
- a citation identified by **DOI or URL with no PMID is deleted outright** — `d.pmid` is empty, so
  `citations` becomes `[]`
- `contributor_researcher` and `observed_on` are silently cleared

An ingested record edited once through the UI loses the evidence trail the ingestion plugin
recorded. Provenance is the point of these tables; this is the highest-priority fix here.

### 2. PATCH is full-replacement, so `generation_method` is clobbered

The aggregates already support partial updates — `Essentiality.update(**fields)` guards every
field with `if "condition" in fields`. But the route hands it every key unconditionally:

```python
updates = {
    "classification": body.classification,
    "provenance": body.provenance.to_domain(),
    "condition": body.condition,
    ...
}
```

So provenance is re-submitted on every edit, and `ProvenanceBody.to_domain()` defaults
`generation_method` to MANUAL. **Correcting a typo in `condition` re-attributes an
AI-extracted record to a human.**

Six other routers (`genes`, `proteins`, `targets`, `strains`, `organisms`, `organizations`)
already use the house `UNSET` sentinel from `application/shared/sentinel.py` for exactly this.
Target-biology is the only one that does not.

### 3. Optimistic locking is fully built and unreachable

`base_repository.save()` does the CAS:

```python
loaded_version: int = aggregate.version
... .where(self.model_class.version == loaded_version).values(version=loaded_version + 1)
```

`version` is on `base.py`'s model and on every target-biology aggregate. But no response exposes
it and no PATCH accepts it, so `UpdateTargetBiologyRecord` loads the record fresh and the check
always compares a value against itself. **Two people editing the same record silently lose one
edit.**

### 4. The field list of each record kind is written out twice

`interface/routes/target_biology.py` is 839 lines — eight response classes, eight write bodies,
sixteen create/patch handlers. `gene-record-tables.tsx` (480) and `protein-record-tables.tsx`
(353) restate the same eight field sets as column definitions. The *application* layer is already
generic over `RecordKind`; only the edges repeat. Adding a field means editing both, and the form
above proves what happens when one edge falls behind.

Related: `condition`, `method`, `expression_host`, `status`, `readout`, `throughput` and
`growth_defect_severity` are free-text `str | None` with no vocabulary anywhere. The data model
plan calls these configurable-vocabulary fields. Nothing today stops `7H9`, `7H9 medium` and
`Middlebrook 7H9` becoming three conditions.

## What we're building

### A. Self-describing write contract — `GET /api/v1/target-biology/schema`

One endpoint that tells any client what each record kind accepts. Derived from the eight
`*WriteBody` models that already exist, so it cannot drift from what the routes validate.

```jsonc
{
  "provenance": { "fields": [ FieldDescriptor, ... ] },
  "kinds": {
    "essentiality": {
      "label": "Essentiality",
      "attaches_to": "gene",          // "gene" | "protein" — which parent path to POST to
      "fields": [ FieldDescriptor, ... ],   // ORDERED; drives form layout
      "read_only": ["extensions"]     // present on the record, not writable
    }
  }
}
```

```jsonc
FieldDescriptor = {
  "name": "condition",
  "label": "Condition",
  "type": "string" | "text" | "number" | "integer" | "boolean"
        | "enum" | "date" | "list" | "reference",
  "required": false,
  "options": [...],             // enum only
  "suggested_values": [...],    // free-text vocabulary fields
  "min": 0.0, "max": 1.0,       // number only
  "item_fields": [ ... ],       // list only (citations)
  "target": "compound" | "strain"   // reference only
}
```

- **Derivation.** `EssentialityWriteBody.model_json_schema()` already yields name, type,
  required-ness and enum options. A small annotation table keyed by `(kind, field)` supplies
  `label`, `min`/`max`, and which columns feed `suggested_values`. Roughly 60–100 lines total;
  no new abstraction, just publishing what the models already know.
- **`suggested_values`** is `SELECT DISTINCT <col> … WHERE <col> IS NOT NULL ORDER BY 1 LIMIT 200`
  over the kind's own table. Self-maintaining, no curation UI.
  `ponytail: distinct-over-stored-values, so a typo becomes a suggestion. Swap for a curated
  vocabulary registry when someone owns curation — the descriptor shape does not change.`
- **`reference` fields** name what is needed, not how to pick it. A client supplies its own
  picker per `target`; the value posted is the `{compound_id, name}` / strain id the record
  already stores.
- **No version negotiation.** Adding a field makes it appear in every descriptor-driven form;
  removing one makes it disappear. That is the point.
- Ordering of `fields` is the form's field order, so field layout is controlled here.

### B. Partial PATCH via the house `UNSET` sentinel

Target-biology's update routes adopt the pattern the other six routers use: build `updates` from
`body.model_fields_set`, omitting keys the caller did not send. The aggregates already do the
right thing with a partial dict.

Consequence: **`generation_method` is only re-stamped when the caller actually submitted
provenance.** Editing `condition` alone leaves the evidence trail intact.

### C. Optimistic locking reaches the wire

- Add `version: int` to the eight record responses.
- Add optional `version: int | None` to the eight write bodies.
- `UpdateTargetBiologyRecord` compares a supplied `version` against the loaded record and returns
  a conflict when they differ; the existing repository CAS stays as the backstop.
- **Optional, not required** — omitting it keeps today's last-write-wins behaviour, so existing
  scripts and the CSV importers are unaffected. The UI always sends it.

Maps to HTTP 409 through `result_to_response`.

### D. Three unauthorable fields become writable

`compound` (resistance mutation), `ligands` (unpublished structure) and `knockdown_strain_id`
(hypomorph) are stored on the aggregates and returned in responses, but appear in no write body —
only an importer can set them. A resistance mutation whose compound cannot be named through the
UI is missing the fact that makes it a resistance mutation.

Add them to the write bodies, typed as `reference` in the descriptor.

### E. The form renders provenance from the descriptor

`editable-record-table.tsx` keeps its inline row editing for record fields — that is presentation
and works. The **provenance block moves into a descriptor-driven dialog** opened from the row:
source type, the full repeatable citation list (PMID / DOI / URL / label), contributor, observed
date, note.

`ProvDraft`, `provToDraft` and `provToBody` are deleted. Round-tripping goes through the full
`Provenance` shape, so nothing is dropped. The three provenance *columns* stay as they are —
showing a subset in a table is fine; a form omitting a field is not.

Deliberately **not** in scope: making the record-field form descriptor-driven, or collapsing the
sixteen create/patch handlers into a generic pair. Both are attractive (~500 lines of deletion)
but they refactor working code behind working UI. Revisit once A–E are in and QA'd.

## Build order

1. **B** (partial PATCH) — smallest, self-contained, fixes the clobbering immediately.
2. **C** (version through the wire) — response field, body field, use-case comparison, 409.
3. **D** (three write fields).
4. **A** (descriptor endpoint) — after B–D so it describes the finished write surface.
5. **E** (provenance dialog) — consumes A, fixes the data-loss bug.

## Testing

- **Unit** — descriptor derivation for all eight kinds: enum options match the domain enums;
  required-ness matches the Pydantic models; `attaches_to` matches the route the kind is created
  under. `suggested_values` returns distinct non-null values and tolerates an empty table.
- **Route** — PATCH with a single field leaves the other fields *and* `generation_method`
  unchanged; PATCH with a stale `version` returns 409; PATCH without `version` still succeeds;
  a resistance mutation round-trips its `compound` through create and update.
- **Regression for the data bug** — create a record with two citations, one DOI-only, plus a
  contributor and an observed date; edit an unrelated field through the UI's code path; assert
  every citation, the contributor and the date survive. This test fails on today's `provToBody`.
- **Frontend** — the provenance dialog renders every descriptor field; saving an untouched
  dialog is a no-op that does not re-stamp `generation_method`.
