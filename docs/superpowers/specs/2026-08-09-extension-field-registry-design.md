# Admin-defined extension fields — design

**Date:** 2026-08-09
**Status:** approved, ready for planning
**Builds on:** `2026-08-08-workspace-scoping-design.md` (workspace ownership, the two predicates,
`is_shared`) and the target-biology descriptor endpoint added in
`2026-08-07-target-biology-api-hardening.md`.

## Problem

Every target-biology record carries an `extensions` JSONB bag for the per-method, per-org tail the
core columns deliberately don't model. Today that bag is **unreachable**: it appears in no write
body, and the published descriptor lists it under `read_only`. Only an ingestion job can put
anything in it, and nothing renders what it contains.

That is about to matter. The legacy Gene service holds fifteen fields with no core column here —
nine on Vulnerability (`ViLowerBound`, `ViUpperBound`, `PctOfMax`, `Bin`, `Rank`, `Certain`,
`HighConfidenceVulnerabilityCall` and two essentiality calls) and six on Hypomorph
(`KnockdownLevel`, `EstimatedKnockdownRelativeToWT`, `EstimateBasedOn`, `Phenotype`,
`SuitableForScreening`, `SelectivelySensitizesToOnTargetInhibitors`), across 28,559 and 195 records
respectively. Migrating them into a write-locked, unlabelled, unrendered bag would produce data
nobody can read or correct.

This builds the registry the extensions bag always assumed: an admin declares what extra fields a
record kind has, and those declarations flow through the existing descriptor into every client.

## Decisions

| Question | Decision |
|---|---|
| Ownership | **Per-workspace.** Each workspace declares the fields it tracks. Shared records display their stored values read-only, whether or not the viewing workspace declared them. |
| Coverage | **The eight target-biology kinds only.** They are the tables that have an `extensions` column. Genes already have axis-typed `annotations`; a second mechanism there would be two ways to do one thing. |
| Reuse | **Per-kind.** A definition belongs to one record kind. No join table, no attach/detach. |

## 1. The registry

One table, in `workspace_config` — alongside organizations and tags, because this is
workspace-level configuration, not target-biology domain data.

```
extension_field_defs
  id, created_at, updated_at, workspace_id, version    -- the standard mixins
  kind             str    -- one of the eight RecordKind values
  name             str    -- the JSON key inside `extensions`
  label            str    -- human label
  field_type       str    -- see §2
  options          JSONB  -- enum only; null otherwise
  position         int    -- order in forms and tables
  show_in_table    bool   -- see §4
```

Unique on `(workspace_id, kind, name)`. Indexed on `(workspace_id, kind)` — the only read shape.

**Two rules that are not obvious and must be enforced:**

- **`name` is immutable after creation.** Values are stored under that key; renaming it orphans
  every one of them. `label` stays editable, which covers the real need (fixing wording).
- **Deleting a definition does not delete data.** The values stay in the JSONB and render as
  *unmapped* (§4). This is also what makes freshly-imported legacy data visible before anyone has
  declared anything — the migration does not depend on configuration existing first.

## 2. Field types come from the descriptor, not from elsewhere

`field_type` is one of: `string`, `text`, `number`, `integer`, `boolean`, `date`, `enum`.

That is the vocabulary the descriptor already emits for core fields, and an extension field must be
indistinguishable from a core one to a client rendering a form. `list`, `reference` and `object` are
deliberately excluded — those exist for core value objects (citations, compound refs) and have no
meaning for a free-form bag.

**A trap worth naming:** the sibling application's datasheet feature treats `enum` as "a string
field with `allowed_values`" rather than a type. Do not copy that here. This service's descriptor
already emits `"type": "enum"` with `"options"` for core fields such as `classification`; using a
different convention for extension fields would force every client into two code paths against one
document.

## 3. How definitions reach clients

`GET /api/v1/target-biology/schema` already resolves per caller workspace. Each kind gains one
sibling key:

```jsonc
"vulnerability": {
  "label": "Vulnerability",
  "attaches_to": "gene",
  "fields":           [ /* core, unchanged */ ],
  "extension_fields": [ /* admin-defined, ordered by position */ ],
  "read_only":        []
}
```

Each entry in `extension_fields` is an ordinary `FieldDescriptor` — same shape as core fields — plus
`show_in_table`.

**Why a separate array rather than merging into `fields` with a flag.** Core fields belong at the
top level of a write body; extension fields belong inside `extensions`. A merged list is one flag
away from a client building the wrong payload — and, decisively, **an existing client that has never
heard of extension fields keeps working**: it ignores an unknown key. Merged, that same client would
send admin-defined fields at the root and 422 on every write.

`extensions` leaves `read_only`. Nothing else about the descriptor changes, so the downstream
consumer that already renders forms from it picks these up with **no change on its side** — which is
the property the descriptor was built for.

**Do not cache the definitions.** The descriptor's existing per-workspace cache covers
`SuggestedValuesReader`, whose `SELECT DISTINCT` sweep is genuinely expensive. Field definitions are
one indexed lookup on `(workspace_id, kind)`, and an admin who adds a field must see it immediately —
a five-minute delay would read as a bug. Keep them outside that cache rather than adding
invalidation machinery.

## 4. Where values appear

| Surface | Behaviour |
|---|---|
| Record tables | Definitions with `show_in_table` render as columns after the core ones, in `position` order |
| Row detail | Every declared field, plus **unmapped** values — keys present in the JSONB with no matching definition |
| Editing | An "Extra fields…" row action opens a dialog built from `extension_fields`, mirroring the provenance dialog |
| Admin | `/admin/extension-fields` (§6) |

`show_in_table` earns its place: a workspace declaring the nine legacy vulnerability fields would
otherwise widen that table by nine columns. One boolean lets an admin choose what is a column and
what is detail-only, without a per-user column picker.

**Shared records show extension values read-only.** No new mechanism needed — mutations already
require ownership, and `is_shared` is already on every target-biology response.

## 5. Making `extensions` writable

The eight `*WriteBody` and `*PatchBody` classes gain `extensions: dict[str, Any] | None`.

Validation runs in the **application layer**, before the aggregate is touched. The aggregates already
accept an `extensions` dict and must not learn about a registry — a workspace-configuration lookup
does not belong in a domain object.

A small `ExtensionValidator` service, injected into `CreateTargetBiologyRecord` and
`UpdateTargetBiologyRecord`, takes `(workspace_id, kind, submitted)` and returns a `Result`:

- key with no definition → **422**, naming the key
- value of the wrong type for its definition → **422**
- `enum` value outside `options` → **422**

**Undeclared keys already stored are preserved, not stripped.** A PATCH that submits `extensions`
merges over the existing bag rather than replacing it, so editing a declared field cannot silently
delete imported values the workspace has not declared. This mirrors the partial-update semantics the
rest of the write surface already has.

`extensions` is absent from a PATCH body → the bag is left entirely alone, exactly like `provenance`.

## 6. Admin surface

`/admin/extension-fields`, sitting with `/admin/tags`, `/admin/organizations`, `/admin/plugins`.

Two screens, matching the shape the sibling application's datasheet admin already established:

1. **Kind list** — the eight record kinds with a count of declared fields each. Fixed set, so no
   create/delete of kinds themselves.
2. **Kind editor** — an inline editable list of field rows (name, label, type, options,
   `show_in_table`), with explicit Save and Cancel.

   - **Order is the list order.** `position` is assigned from each row's index on save; move-up and
     move-down controls per row. No drag-and-drop — it needs a dependency and a keyboard story for
     a screen that will hold single-digit numbers of rows.
   - **`options` is a comma-separated input**, shown only when `field_type` is `enum`, and parsed to
     the JSONB array on save. Trimmed, blanks dropped, order preserved.
   - **Delete is per row**, behind a confirm that states plainly that stored values are kept and
     will render as unmapped. That is the surprising half, so the confirm has to say it.

The row editor is directly analogous to that datasheet editor's `FieldRows`: a repeatable row of
`Input` + `Select`, one row per declaration. Follow its shape — same control choices, same inline
editing — so the two admin surfaces feel like one product. Do not import it; it lives in a different
repository and speaks a different type vocabulary (§2).

`name` renders read-only once a definition is saved, per §1.

Admin-gated with the existing `require_admin`, like every other `/admin` surface here.

## 7. Testing

- **The two §1 rules, directly** — a rename attempt on a saved definition is rejected; deleting a
  definition leaves stored values intact and they still render as unmapped.
- **Validation** — undeclared key 422s; wrong type 422s; out-of-range enum 422s; a PATCH touching
  one declared field preserves undeclared stored keys; an absent `extensions` leaves the bag alone.
- **Workspace isolation** — workspace A's definitions never appear in workspace B's descriptor, and
  a value A wrote under its own definition is not writable by B. Extend
  `tests/api/test_workspace_isolation.py`, which Tasks 4-9 of the tenancy work established.
- **Descriptor** — `extension_fields` present per kind and ordered by `position`; `extensions` no
  longer in `read_only`; the definitions are **not** served from the suggested-values cache
  (add a definition, fetch the descriptor, see it immediately).
- **Frontend** — a `show_in_table` definition renders a column and one without it does not; an
  unmapped value renders read-only; a shared record shows values with no edit affordance.

## 8. Build order

1. **The table, the aggregate and its repository** — plus the migration. Verifiable alone.
2. **CRUD use cases and routes**, admin-gated, with the immutability rule enforced.
3. **Descriptor integration** — `extension_fields` per kind, `extensions` out of `read_only`.
4. **Write validation** — `ExtensionValidator` wired into create and update.
5. **Admin UI** — kind list and kind editor.
6. **Display** — table columns, row detail, the edit dialog.

Steps 1-4 leave the service working and are independently reviewable; nothing user-visible appears
until step 5.

## Deliberately out of scope

- **`required` on a definition.** No legacy field is mandatory, and requiring one would make
  existing records unsaveable. Add it when something needs it.
- **`help_text`.** Wanted eventually; not needed to render or validate a field.
- **Migrating the legacy data.** Explicitly deferred — this exists so that migration has somewhere
  to land.
- **Extension fields on genes or proteins.** They have no `extensions` column and genes already have
  `annotations`.
- **Suggested values for free-text extension fields.** Enum definitions carry explicit `options`;
  distinct-value suggestions for the rest can come later if anyone asks.
- **Promoting an extension field to a core column.** That is a real migration and a deliberate
  decision each time, not a button.
