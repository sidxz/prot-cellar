# Ingestion Plugins — Plan A: Provenance `generation_method` + Coloring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an orthogonal `generation_method` axis to the shared `Provenance` value object (how a value was produced — `manual`/`imported`/`ai_extracted`/`ai_predicted`/`computed`), persist and expose it through the API, and recolor the Source cell of every target-biology record table by that method — AI = blue, imported/computed = neutral, manual = foreground — with a legend and a details tooltip.

**Architecture:** `generation_method` is a new field on the frozen `Provenance` dataclass with a `MANUAL` default, so every existing construction site and all 24 `to_domain()`/`from_domain()` call sites keep working unchanged. It rides inside the existing `provenance` JSON column (no table migration). The **read** model (`ProvenanceResponse`) exposes it to drive color; the **write** model (`ProvenanceBody`, the edit form's inbound payload) deliberately does *not* carry it, so any human edit routes through `to_domain()` and re-defaults to `manual` — that is the design's "a human edit flips the row to black" honesty rule, for free. The frontend maps the method string to a badge variant (adding one blue `info` variant to the design-system badge).

**Tech Stack:** Python ≥3.13 (`StrEnum`, `X | None`), frozen dataclasses, SQLAlchemy JSON columns, FastAPI + Pydantic response/body models, orval-generated TanStack Query client, React + Radix/cva design system, pytest + vitest.

**Standalone value:** this plan ships the entire coloring *mechanism* independently. Until records exist that carry a non-`manual` method (Plan B's imports, or the deferred essentiality backfill), tables render `manual`/neutral — honestly. It is the foundation Plans B and C build on.

## Global Constraints

- **Python ≥3.13** — `StrEnum`, `X | None`. Copied from `backend/pyproject.toml` `requires-python = ">=3.13"`.
- **Run backend commands from `backend/` via `uv`** — `uv run pytest ...`, `uv run lint-imports`, `uv run ruff check src tests`, `uv run mypy src`.
- **Domain purity (import-linter contract "Domain purity")** — `protcellar.domain.shared.provenance` may not import `application`, `infrastructure`, `interface`, `fastapi`, `sqlalchemy`, `asyncpg`, `redis`, `lagom`. It stays pure stdlib.
- **Non-breaking VO extension** — `generation_method` MUST default to `GenerationMethod.MANUAL`. `Provenance` is a `@dataclass(frozen=True, kw_only=True)` compared by value; do not reorder existing fields or add required ones. Legacy persisted `provenance` JSON has no `generation_method` key → `provenance_from_json` defaults it to `manual`.
- **Honesty rule** — `ProvenanceBody` (inbound edit payload in `interface/routes/target_biology.py`) does NOT gain `generation_method`; `to_domain()` therefore always yields `manual`. Only `ProvenanceResponse` (outbound) exposes it. Do not add it to the body.
- **Frontend tooling: direct binaries** — run `./node_modules/.bin/vitest`, `./node_modules/.bin/tsc`, `./node_modules/.bin/biome` from `frontend/` (pnpm exec is flaky in this repo).
- **Regenerate the API client with `make generate-api`** (repo root) after any backend schema change — it re-snapshots `frontend/openapi.json` from the live FastAPI app, then runs `pnpm generate:api`. Never hand-edit files under `frontend/src/shared/lib/api/` — they are orval-generated and biome-ignored.
- **Design-system files** (`frontend/src/shared/components/ui/`) are biome-ignored — additions there won't be linted; keep them consistent with the existing cva pattern by hand.

---

## File Structure

**Modify (backend):**
- `backend/src/protcellar/domain/shared/provenance.py` — add `GenerationMethod` enum + `generation_method` field.
- `backend/src/protcellar/infrastructure/persistence/sqlalchemy/target_biology/_provenance_json.py` — (de)serialize the new field.
- `backend/src/protcellar/interface/routes/target_biology.py` — add `generation_method` to `ProvenanceResponse` + `from_domain` (leave `ProvenanceBody` alone).

**Modify (backend tests):**
- `backend/tests/unit/domain/shared/test_provenance.py`
- `backend/tests/unit/infrastructure/target_biology/test_provenance_json.py`

**Create (backend tests):**
- `backend/tests/unit/interface/__init__.py`, `backend/tests/unit/interface/routes/__init__.py` (only if missing — empty package markers)
- `backend/tests/unit/interface/routes/test_provenance_mapping.py`

**Modify (frontend):**
- `frontend/src/shared/components/ui/badge.tsx` — add the blue `info` variant.
- `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx` — `generationMethodBadgeVariant` helper, `ProvLike` gains `generation_method`, Source cell becomes a badge + tooltip, export a `ProvenanceLegend`.
- `frontend/src/features/protein-catalog/components/sections/gene-target-biology-tab.tsx` — render `ProvenanceLegend`.
- `frontend/src/features/protein-catalog/components/sections/protein-target-biology-tab.tsx` — render `ProvenanceLegend`.

**Create (frontend tests):**
- `frontend/src/features/protein-catalog/components/sections/editable-record-table.test.tsx`

**Regenerated (do not hand-edit):**
- `frontend/openapi.json`, `frontend/src/shared/lib/api/model/provenanceResponse.ts`, `.../model/provenanceGenerationMethod.ts` (new), `.../model/index.ts`.

---

## Task 1: `GenerationMethod` enum + `generation_method` field on the `Provenance` VO

**Files:**
- Modify: `backend/src/protcellar/domain/shared/provenance.py`
- Test: `backend/tests/unit/domain/shared/test_provenance.py`

**Interfaces:**
- Produces:
  - `GenerationMethod(StrEnum)` = `MANUAL="manual"`, `IMPORTED="imported"`, `AI_EXTRACTED="ai_extracted"`, `AI_PREDICTED="ai_predicted"`, `COMPUTED="computed"`.
  - `Provenance.generation_method: GenerationMethod` — kw-only, defaults `GenerationMethod.MANUAL`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/domain/shared/test_provenance.py` and update its import block to include `GenerationMethod`:

```python
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)


def test_generation_method_defaults_to_manual() -> None:
    p = Provenance(source_type=ProvenanceSourceType.PUBLISHED)
    assert p.generation_method is GenerationMethod.MANUAL


def test_generation_method_is_settable() -> None:
    p = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        generation_method=GenerationMethod.AI_EXTRACTED,
    )
    assert p.generation_method is GenerationMethod.AI_EXTRACTED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/domain/shared/test_provenance.py -v`
Expected: FAIL — `ImportError: cannot import name 'GenerationMethod'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/src/protcellar/domain/shared/provenance.py`, add the enum after `ProvenanceSourceType` (before `Citation`):

```python
class GenerationMethod(StrEnum):
    """How a provenance-stamped value was produced — orthogonal to source_type.

    source_type answers *publication status* (published/preprint/…); this answers
    *how the value came to be*. An AI can extract a value from a published paper,
    so both axes must coexist.
    """

    MANUAL = "manual"  # a human typed / curated it (the default)
    IMPORTED = "imported"  # loaded verbatim from an external DB / dataset
    AI_EXTRACTED = "ai_extracted"  # an AI pulled a stated value from a source
    AI_PREDICTED = "ai_predicted"  # an AI inferred a value not directly stated
    COMPUTED = "computed"  # a deterministic pipeline derived it
```

Add one field to `Provenance`, immediately after `source_type`:

```python
@dataclass(frozen=True, kw_only=True)
class Provenance:
    """Where a target-biology fact came from — the shared provenance envelope."""

    source_type: ProvenanceSourceType
    generation_method: GenerationMethod = GenerationMethod.MANUAL
    citations: tuple[Citation, ...] = ()
    contributor_researcher: str | None = None
    contributor_organization_id: uuid.UUID | None = None
    observed_on: date | None = None
    note: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/domain/shared/test_provenance.py -v`
Expected: PASS (6 tests — 4 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/domain/shared/provenance.py backend/tests/unit/domain/shared/test_provenance.py
git commit -m "feat(target-biology): add orthogonal generation_method to Provenance VO"
```

---

## Task 2: Persist `generation_method` through the provenance JSON mapping

**Files:**
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/target_biology/_provenance_json.py`
- Test: `backend/tests/unit/infrastructure/target_biology/test_provenance_json.py`

**Interfaces:**
- Consumes: `GenerationMethod`, `Provenance` (Task 1).
- Produces: `provenance_to_json` writes a `"generation_method"` key; `provenance_from_json` reads it, defaulting a missing key to `"manual"` (legacy rows).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/infrastructure/target_biology/test_provenance_json.py` and add `GenerationMethod` to its provenance import:

```python
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)


def test_generation_method_round_trips() -> None:
    original = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        generation_method=GenerationMethod.AI_EXTRACTED,
    )
    restored = provenance_from_json(provenance_to_json(original))
    assert restored == original
    assert restored.generation_method is GenerationMethod.AI_EXTRACTED


def test_legacy_json_without_generation_method_defaults_to_manual() -> None:
    # A provenance blob written before the field existed.
    legacy = {"source_type": "published", "citations": []}
    restored = provenance_from_json(legacy)
    assert restored is not None
    assert restored.generation_method is GenerationMethod.MANUAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/infrastructure/target_biology/test_provenance_json.py -v`
Expected: FAIL — `test_generation_method_round_trips` fails (`restored != original`) because the field is dropped on serialization.

- [ ] **Step 3: Write minimal implementation**

In `_provenance_json.py`, add the import and both mapping edits. Update the import:

```python
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
```

In `provenance_to_json`, add the key right after `source_type`:

```python
def provenance_to_json(p: Provenance) -> dict[str, object]:
    return {
        "source_type": p.source_type.value,
        "generation_method": p.generation_method.value,
        "citations": [
            {"pmid": c.pmid, "doi": c.doi, "url": c.url, "label": c.label} for c in p.citations
        ],
        "contributor_researcher": p.contributor_researcher,
        "contributor_organization_id": (
            str(p.contributor_organization_id) if p.contributor_organization_id else None
        ),
        "observed_on": p.observed_on.isoformat() if p.observed_on else None,
        "note": p.note,
    }
```

In `provenance_from_json`, read it with a `manual` fallback (add the keyword to the `Provenance(...)` call, right after `source_type`):

```python
    return Provenance(
        source_type=ProvenanceSourceType(str(data["source_type"])),
        generation_method=GenerationMethod(
            str(data.get("generation_method", GenerationMethod.MANUAL.value))
        ),
        citations=tuple(
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/infrastructure/target_biology/test_provenance_json.py -v`
Expected: PASS (4 tests — 2 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/infrastructure/persistence/sqlalchemy/target_biology/_provenance_json.py backend/tests/unit/infrastructure/target_biology/test_provenance_json.py
git commit -m "feat(target-biology): persist generation_method in provenance JSON"
```

---

## Task 3: Expose `generation_method` on the read API and regenerate the client

**Files:**
- Modify: `backend/src/protcellar/interface/routes/target_biology.py`
- Create: `backend/tests/unit/interface/routes/test_provenance_mapping.py` (+ `__init__.py` markers if missing)
- Regenerate: `frontend/openapi.json` + `frontend/src/shared/lib/api/model/**`

**Interfaces:**
- Consumes: `GenerationMethod`, `Provenance` (Task 1).
- Produces: `ProvenanceResponse.generation_method: GenerationMethod` (drives FE color); `ProvenanceResponse.from_domain` sets it. `ProvenanceBody` is **unchanged** — `to_domain()` keeps defaulting `generation_method` to `MANUAL` (the honesty rule). Orval emits a `ProvenanceGenerationMethod` TS enum + `generation_method` on the generated `ProvenanceResponse`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/interface/routes/test_provenance_mapping.py` (and empty `backend/tests/unit/interface/__init__.py`, `backend/tests/unit/interface/routes/__init__.py` if those dirs are new):

```python
"""Provenance ↔ API mapping: the read model exposes generation_method; the write
model does not, so an edit through the form re-attributes the row to a human."""

from protcellar.domain.shared.provenance import (
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
from protcellar.interface.routes.target_biology import ProvenanceBody, ProvenanceResponse


def test_response_exposes_generation_method() -> None:
    prov = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        generation_method=GenerationMethod.IMPORTED,
    )
    resp = ProvenanceResponse.from_domain(prov)
    assert resp.generation_method is GenerationMethod.IMPORTED


def test_body_to_domain_is_always_manual() -> None:
    # The honesty rule: the inbound edit payload carries no generation_method,
    # so a human edit routes through to_domain() and re-defaults to manual.
    body = ProvenanceBody(source_type=ProvenanceSourceType.PUBLISHED)
    assert body.to_domain().generation_method is GenerationMethod.MANUAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/interface/routes/test_provenance_mapping.py -v`
Expected: FAIL — `AttributeError: 'ProvenanceResponse' object has no attribute 'generation_method'` (and a Pydantic construction error).

- [ ] **Step 3: Write minimal implementation**

In `backend/src/protcellar/interface/routes/target_biology.py`:

Extend the provenance import to include `GenerationMethod`:

```python
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
```

Add the field to `ProvenanceResponse` (typed as the enum so orval generates a TS enum) and set it in `from_domain`:

```python
class ProvenanceResponse(BaseModel):
    source_type: str
    generation_method: GenerationMethod
    citations: list[ProvenanceCitationResponse]
    contributor_researcher: str | None = None
    contributor_organization_id: uuid.UUID | None = None
    observed_on: date | None = None
    note: str | None = None

    @classmethod
    def from_domain(cls, p: Provenance) -> ProvenanceResponse:
        return cls(
            source_type=p.source_type.value,
            generation_method=p.generation_method,
            citations=[
                ProvenanceCitationResponse(pmid=c.pmid, doi=c.doi, url=c.url, label=c.label)
                for c in p.citations
            ],
            contributor_researcher=p.contributor_researcher,
            contributor_organization_id=p.contributor_organization_id,
            observed_on=p.observed_on,
            note=p.note,
        )
```

Leave `ProvenanceBody` and `ProvenanceBody.to_domain` exactly as they are. Add a one-line comment above `ProvenanceBody` documenting the intent:

```python
# NOTE: no `generation_method` here — an edit submitted through the form must
# re-attribute the row to a human (to_domain() defaults it to MANUAL). See Plan A.
class ProvenanceBody(BaseModel):
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/interface/routes/test_provenance_mapping.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Regenerate the API client**

Run: `make generate-api`
Expected: `frontend/openapi.json` updates; `frontend/src/shared/lib/api/model/provenanceResponse.ts` gains `generation_method: ProvenanceGenerationMethod`; a new `frontend/src/shared/lib/api/model/provenanceGenerationMethod.ts` appears with `{ manual, imported, ai_extracted, ai_predicted, computed }`; `model/index.ts` re-exports it. Confirm:

```bash
cd frontend && grep -l generation_method src/shared/lib/api/model/provenanceResponse.ts && cat src/shared/lib/api/model/provenanceGenerationMethod.ts
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar/interface/routes/target_biology.py backend/tests/unit/interface frontend/openapi.json frontend/src/shared/lib/api/model
git commit -m "feat(target-biology): expose generation_method on read API + regen client"
```

---

## Task 4: Frontend badge — blue `info` variant + `generationMethodBadgeVariant` helper

**Files:**
- Modify: `frontend/src/shared/components/ui/badge.tsx`
- Modify: `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx`
- Test: `frontend/src/features/protein-catalog/components/sections/editable-record-table.test.tsx`

**Interfaces:**
- Produces:
  - Badge gains an `info` variant (blue, self-contained Tailwind classes — no theme token dependency).
  - `generationMethodBadgeVariant(method: string | null | undefined): BadgeVariant` — `ai_extracted`/`ai_predicted` → `"info"`; `imported`/`computed` → `"secondary"`; everything else (incl. `manual`, unknown, null) → `"outline"`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/protein-catalog/components/sections/editable-record-table.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";

import { generationMethodBadgeVariant } from "./editable-record-table";

describe("generationMethodBadgeVariant", () => {
  it("colors AI methods blue (info)", () => {
    expect(generationMethodBadgeVariant("ai_extracted")).toBe("info");
    expect(generationMethodBadgeVariant("ai_predicted")).toBe("info");
  });

  it("colors imported/computed neutral (secondary)", () => {
    expect(generationMethodBadgeVariant("imported")).toBe("secondary");
    expect(generationMethodBadgeVariant("computed")).toBe("secondary");
  });

  it("colors manual / unknown / null as outline", () => {
    expect(generationMethodBadgeVariant("manual")).toBe("outline");
    expect(generationMethodBadgeVariant("nonsense")).toBe("outline");
    expect(generationMethodBadgeVariant(undefined)).toBe("outline");
    expect(generationMethodBadgeVariant(null)).toBe("outline");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/protein-catalog/components/sections/editable-record-table.test.tsx`
Expected: FAIL — `generationMethodBadgeVariant` is not exported.

- [ ] **Step 3: Add the blue `info` badge variant**

In `frontend/src/shared/components/ui/badge.tsx`, add one entry to the `variant` map, after `warning`:

```tsx
        warning:
          "border-warning/20 bg-warning/15 text-warning [a&]:hover:bg-warning/25",
        info: "border-blue-500/20 bg-blue-500/15 text-blue-600 dark:text-blue-400 [a&]:hover:bg-blue-500/25",
        ghost: "[a&]:hover:bg-accent [a&]:hover:text-accent-foreground",
```

- [ ] **Step 4: Add the helper**

In `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx`, add near the top (after the existing `humanize`/`SOURCE_OPTIONS` exports). Derive `BadgeVariant` locally from the Badge prop type so the file doesn't depend on the import-hub feature:

```tsx
import type { ComponentProps } from "react";

import { Badge } from "@/shared/components/ui/badge";

type BadgeVariant = NonNullable<ComponentProps<typeof Badge>["variant"]>;

/** Map how-a-value-was-produced → badge color. AI = blue; imported/computed =
 * neutral; manual (and anything unknown) = foreground outline. */
export function generationMethodBadgeVariant(
  method: string | null | undefined,
): BadgeVariant {
  switch (method) {
    case "ai_extracted":
    case "ai_predicted":
      return "info";
    case "imported":
    case "computed":
      return "secondary";
    default:
      return "outline";
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/protein-catalog/components/sections/editable-record-table.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/shared/components/ui/badge.tsx frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx frontend/src/features/protein-catalog/components/sections/editable-record-table.test.tsx
git commit -m "feat(protein-catalog): blue info badge + generationMethodBadgeVariant helper"
```

---

## Task 5: Source cell → colored badge + tooltip, and a provenance legend

**Files:**
- Modify: `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx`
- Modify: `frontend/src/features/protein-catalog/components/sections/gene-target-biology-tab.tsx`
- Modify: `frontend/src/features/protein-catalog/components/sections/protein-target-biology-tab.tsx`
- Test: `frontend/src/features/protein-catalog/components/sections/editable-record-table.test.tsx` (extend)

**Interfaces:**
- Consumes: `generationMethodBadgeVariant` (Task 4); `provenance.generation_method` (now present on every record's `ProvenanceResponse`, Task 3).
- Produces: the Source column renders `<Badge variant={…(generation_method)}>{source_type}</Badge>` wrapped in a details `Tooltip`; an exported `ProvenanceLegend` component; `ProvLike` gains `generation_method: string`.

- [ ] **Step 1: Write the failing test**

Append to `editable-record-table.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";

import { ProvenanceLegend } from "./editable-record-table";

describe("ProvenanceLegend", () => {
  it("renders the three color meanings", () => {
    render(<ProvenanceLegend />);
    expect(screen.getByText("manual")).toBeInTheDocument();
    expect(screen.getByText("imported")).toBeInTheDocument();
    expect(screen.getByText("AI")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/protein-catalog/components/sections/editable-record-table.test.tsx`
Expected: FAIL — `ProvenanceLegend` is not exported.

- [ ] **Step 3: Update `ProvLike`, the Source cell, and add the legend**

In `editable-record-table.tsx`:

Add `generation_method` to the structural `ProvLike` type:

```tsx
interface ProvLike {
  source_type: string;
  generation_method: string;
  citations: { pmid?: string | null }[];
  note?: string | null;
}
```

Add the tooltip imports at the top:

```tsx
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
```

Replace the Source column's `render` (in `provColumns`) with a badge + tooltip via a small component. Define the component above `provColumns`:

```tsx
function ProvenanceSourceBadge({ p }: { p: ProvLike }) {
  const method = p.generation_method || "manual";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant={generationMethodBadgeVariant(method)}
          aria-label={`Source: ${humanize(p.source_type)}. Generated: ${humanize(method)}.`}
        >
          {humanize(p.source_type)}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="text-xs">
        <div>Source: {humanize(p.source_type)}</div>
        <div>Generated: {humanize(method)}</div>
        {p.citations[0]?.pmid ? <div>PMID: {p.citations[0].pmid}</div> : null}
        {p.note ? <div>{p.note}</div> : null}
      </TooltipContent>
    </Tooltip>
  );
}
```

And the Source column render becomes:

```tsx
    {
      label: "Source",
      field: "source_type",
      type: "enum",
      options: SOURCE_OPTIONS,
      render: (r) => <ProvenanceSourceBadge p={r.provenance} />,
    },
```

Add the exported legend at the end of the file:

```tsx
/** Explains the Source-cell colors. Render once above a set of record tables. */
export function ProvenanceLegend() {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span>Source color:</span>
      <Badge variant="outline">manual</Badge>
      <Badge variant="secondary">imported</Badge>
      <Badge variant="info">AI</Badge>
    </div>
  );
}
```

`ponytail:` the tooltip carries only what Plan A knows (source_type, method, citation, note). Plan C adds plugin + run + date to this tooltip when that lineage is surfaced.

- [ ] **Step 4: Make the legend test pass**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/protein-catalog/components/sections/editable-record-table.test.tsx`
Expected: PASS (the legend renders `manual`/`imported`/`AI`).

- [ ] **Step 5: Render the legend on both detail tabs**

In `frontend/src/features/protein-catalog/components/sections/gene-target-biology-tab.tsx`, import and render the legend once above the record tables:

```tsx
import { ProvenanceLegend } from "./editable-record-table";
```

Place `<ProvenanceLegend />` at the top of the tab's returned content (above the first record table). Do the identical edit in `protein-target-biology-tab.tsx`.

- [ ] **Step 6: Typecheck, lint, and run the affected FE tests**

Run:
```bash
cd frontend
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/biome check src/features/protein-catalog
./node_modules/.bin/vitest run src/features/protein-catalog
```
Expected: `tsc` clean, biome clean, all protein-catalog vitest suites PASS. If a Source-cell render test errors with a Radix tooltip context error, wrap that test's `render(...)` in `<TooltipProvider>` (imported from `@/shared/components/ui/tooltip`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/protein-catalog/components/sections
git commit -m "feat(protein-catalog): color Source cell by generation_method + legend/tooltip"
```

---

## Task 6: Full-gate verification

**Files:** none (verification only).

- [ ] **Step 1: Backend unit tests + import-linter**

Run: `cd backend && uv run pytest tests/unit -v && uv run lint-imports`
Expected: all PASS; import-linter reports all contracts kept (domain purity intact — `provenance.py` gained no imports beyond stdlib).

- [ ] **Step 2: Backend lint/type**

Run: `cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src`
Expected: clean.

- [ ] **Step 3: Backend API tests (needs Postgres + Valkey)**

Run: `make test-api`
Expected: PASS — target-biology record responses now include `generation_method` (a record read back through the API shows `"generation_method": "manual"` for legacy/hand-created rows). Note the two pre-existing proteome test-isolation failures documented in project memory are unrelated to this change.

- [ ] **Step 4: Frontend full suite + type + lint**

Run:
```bash
cd frontend
./node_modules/.bin/vitest run
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/biome check src/
```
Expected: all PASS/clean.

- [ ] **Step 5: Commit any formatting fixups (if the gates changed files)**

```bash
git add -A && git commit -m "chore(ingestion-plugins): plan A full-gate green" || echo "nothing to commit"
```

---

## Self-Review (checked against the spec §5, §9.3, §14.1)

- **§5 the field** — `generation_method` added to the shared `Provenance` VO with all five members ✓ (Task 1). Orthogonal to `source_type` ✓ (separate field, separate enum).
- **§5 the color** — `manual`→outline, `imported`/`computed`→secondary, `ai_*`→blue `info` ✓ (Tasks 4–5).
- **§5 honesty rule** — human edit → `manual` via `ProvenanceBody` omitting the field ✓ (Task 3), regression-tested ✓.
- **§9.3 provenance visible** — Source cell is a colored badge driven by `generation_method`, one edit recolors all 8 tables (single `provColumns` seam) ✓; legend ✓; tooltip ✓ (Task 5). "Hide AI predictions" per-table filter is marked optional in §9.3 — **deferred** (Plan C adds it alongside the catalog if wanted).
- **§14.1 ships value on its own** — the mechanism is complete and independently gated (Task 6). Visible non-`manual` color arrives with records that carry it (Plan B / the deferred backfill) — stated honestly in the goal.
- **Type consistency** — `GenerationMethod` name identical across VO, JSON mapping, and API; helper returns the exact badge variant strings present in `badge.tsx` (`info`/`secondary`/`outline`).
