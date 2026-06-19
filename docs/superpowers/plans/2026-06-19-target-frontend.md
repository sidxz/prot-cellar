# Target Frontend (Plan 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Target feature slice — the first **workspace-scoped, full-CRUD** context: browse/detail plus create/edit with a `TargetComponentsEditor` that enforces the single-vs-complex cardinality invariant client-side.

**Architecture:** A `target` feature slice mirroring `protein-catalog`'s structure, but adding **mutations** (create/update via the generated hooks wrapped with cache-invalidation + success toast) and **forms** (react-hook-form + zod). Components reference proteins by `protein_id`, resolved from an accession/ID via the existing resolve endpoint. A create/edit **Dialog** (not separate routes) launched from the list and detail pages.

**Tech Stack:** Next 16 App Router, React 19, TanStack Query (orval hooks + `createCrudHooks`-style wrappers), react-hook-form + `@hookform/resolvers` + zod, shadcn/radix (Dialog, Select, Form primitives), ag-grid via `DataGrid`, the Plan-0/1 `CrossReferenceLinks`, toast.

## Global Constraints

- **Foundation branch:** `feat/frontend` (HEAD `b3d8c46` at plan time). Work in `frontend/`. OpenAPI is the committed snapshot.
- **Reference patterns:**
  - `frontend/src/features/protein-catalog/**` — the established slice conventions (types alias+narrow, `hooks/query-keys.ts`, thin hooks, columns separate from pages, lazy `useState(readFilters)` filter prefs, cursor-stack pagination, `DataGrid` usage, detail-page layout with `MetadataRow`/skeleton/not-found). REUSE these patterns verbatim where applicable.
  - `~/workspace/chem-vault2/frontend/src/features/research-organization/components/create-project-dialog.tsx` — the react-hook-form + zod + Dialog form convention (schema at top, `zodResolver`, reset on open, `mutation.isPending`, error display).
- **Exact generated hooks (`@/shared/lib/api/targets/targets`):** `useListTargetsApiV1TargetsGet(params?)` → `PaginatedResponseTargetResponse`; `useGetTargetApiV1TargetsTargetIdGet(targetId)` → `TargetResponse`; `useCreateTargetApiV1TargetsPost()` (mutation, body `CreateTargetBody`) → `TargetResponse`; `useUpdateTargetApiV1TargetsTargetIdPatch()` (mutation, `{ targetId, data: UpdateTargetBody }`) → `TargetResponse`. **No delete endpoint exists — no delete UI.**
- **Imperative protein resolve (for the component editor):** the non-hook generated function `resolveProteinApiV1ProteinsResolveIdentifierGet(identifier)` from `@/shared/lib/api/proteins/proteins` returns `Promise<ProteinResponse>` (throws `ApiError` on 404). Use it to turn a typed accession/ID into a `protein_id` — do NOT call a React hook per dynamic row.
- **DTOs (re-narrow in `types/index.ts`):** `TargetResponse { id, workspace_id, pref_name, target_type: TargetType, components: ComponentResponse[] ({id, protein_id, relationship}), organism_id?, chembl_id?, chembl_url?, pharmacological_class?, cross_references[], version }`. `CreateTargetBody { pref_name, target_type, components?: ComponentBody[] ({protein_id, relationship}), organism_id?, chembl_id?, pharmacological_class?, cross_references? }`. `UpdateTargetBody` = all-optional same fields. `ListTargetsApiV1TargetsGetParams { target_type?, chembl_id?, cursor?, limit? }`.
- **Enums (use the generated const objects):** `TargetType` = single_protein | protein_complex | protein_family | protein_protein_interaction | nucleic_acid | organism | cell_line | tissue | unknown. `ComponentRelationship` = single_protein | protein_subunit | family_member | interacting_protein.
- **Cardinality invariant (the whole point — enforce client-side, backend re-validates → 422):** `single_protein` ⇒ exactly 1 component; `protein_complex` / `protein_family` / `protein_protein_interaction` ⇒ ≥ 2 components; all other types ⇒ any number (incl. 0).
- **Mutations wrapper convention:** wrap the generated create/update hooks so `onSuccess` invalidates `TARGETS_KEY` (+ the detail key on update) and calls `showSuccess(...)`. Do NOT add a per-mutation `onError` (the global `MutationCache` handler in `query-provider.tsx` shows the error toast — adding another would double-toast, the exact Plan-0 bug).
- **Workspace scoping:** `workspace_id` is set server-side from auth; the frontend never sends it (it's not in Create/Update bodies). Don't surface it in forms.
- **Read/write split:** Targets ARE workspace-scoped tenant data → full create/edit is correct here (unlike the read-first proteins/genes). No delete (no endpoint).
- **Organism:** still id-only (Taxonomy is Plan 3) — organism field in the form is a free-text id input with a "picker in Plan 3" comment; detail shows an organism link chip to `/organisms/{id}`.
- **Lint/test:** biome clean (no NEW warnings beyond the 8 pre-existing data-grid ones; `pnpm lint` exits 0); `pnpm test` green; `pnpm build` succeeds. a11y: form fields labeled, buttons typed, dialog has an accessible title. Commit per task on `feat/frontend`, trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

```
frontend/src/features/target/
  types/index.ts              # T1 Target/Component narrowing + label maps + TargetFormValues
  lib/cardinality.ts          # T1 cardinalityRule()/componentCountValid() (pure) + test
  hooks/query-keys.ts         # T1 TARGETS_KEY + targetDetailKey
  hooks/use-targets.ts        # T1 useTargets/useTarget/useCreateTarget/useUpdateTarget
  components/
    target-components-editor.tsx   # T2 dynamic rows: resolve protein + relationship + cardinality hint
    target-form-dialog.tsx         # T3 react-hook-form + zod; create & edit modes
    target-columns.tsx             # T4 ag-grid ColDefs
    target-list.tsx                # T4 TargetListPage (DataGrid + filters + pagination + New)
    target-detail.tsx              # T5 TargetDetailPage (components table + metadata + Edit)
  index.ts                    # barrel (grown per task)
frontend/src/app/(dashboard)/targets/
  page.tsx                    # T4 -> <TargetListPage/>
  [id]/page.tsx               # T5 -> <TargetDetailPage targetId=.../>
```

---

### Task 1: Scaffolding — types, cardinality (TDD), query-keys, hooks (incl. mutations)

**Files:**
- Create: `frontend/src/features/target/types/index.ts`, `lib/cardinality.ts`, `lib/cardinality.test.ts`, `hooks/query-keys.ts`, `hooks/use-targets.ts`, `index.ts`

**Interfaces:**
- Produces (types): `Target` (= `TargetResponse`), `TargetComponentView` (= `ComponentResponse`), `TargetComponentInput = { protein_id: string; relationship: ComponentRelationship; accession?: string; label?: string }` (UI-side editor row; `accession`/`label` are display-only), `TARGET_TYPE_LABELS: Record<TargetType,string>`, `RELATIONSHIP_LABELS: Record<ComponentRelationship,string>`, `TargetListFilters = { targetType?: TargetType; chemblId?: string }`.
- Produces (cardinality): `cardinalityRule(t: TargetType): { min: number; max: number }` (single_protein→{1,1}; protein_complex/protein_family/protein_protein_interaction→{2, Number.MAX_SAFE_INTEGER}; else→{0, MAX}); `componentCountValid(t: TargetType, n: number): boolean`; `cardinalityHint(t: TargetType): string` (e.g. "Exactly 1 protein", "At least 2 proteins", "Optional").
- Produces (query-keys): `TARGETS_KEY = ["targets"] as const`, `targetDetailKey(id)`.
- Produces (hooks): `useTargets(filters, cursor?)`, `useTarget(id)`, `useCreateTarget()` (wraps `useCreateTargetApiV1TargetsPost`, `onSuccess`→invalidate `TARGETS_KEY` + `showSuccess("Target created")`), `useUpdateTarget()` (wraps the patch hook, `onSuccess`→invalidate `TARGETS_KEY` + `targetDetailKey` + `showSuccess("Target updated")`). No per-mutation `onError`.

- [ ] **Step 1: Write the failing cardinality test** — `lib/cardinality.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { cardinalityRule, componentCountValid } from "./cardinality";

describe("cardinality", () => {
  it("single_protein requires exactly 1", () => {
    expect(componentCountValid("single_protein", 1)).toBe(true);
    expect(componentCountValid("single_protein", 0)).toBe(false);
    expect(componentCountValid("single_protein", 2)).toBe(false);
  });
  it("complex/family/ppi require >= 2", () => {
    for (const t of ["protein_complex", "protein_family", "protein_protein_interaction"] as const) {
      expect(componentCountValid(t, 1)).toBe(false);
      expect(componentCountValid(t, 2)).toBe(true);
      expect(componentCountValid(t, 5)).toBe(true);
    }
  });
  it("other types allow any count incl. 0", () => {
    expect(componentCountValid("organism", 0)).toBe(true);
    expect(componentCountValid("unknown", 3)).toBe(true);
  });
  it("cardinalityRule returns bounds", () => {
    expect(cardinalityRule("single_protein")).toEqual({ min: 1, max: 1 });
    expect(cardinalityRule("protein_complex").min).toBe(2);
  });
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && pnpm exec vitest run src/features/target/lib/cardinality.test.ts` → FAIL.

- [ ] **Step 3: Implement** `cardinality.ts` (per Interfaces), `types/index.ts` (label maps from the generated enum consts), `query-keys.ts`, `hooks/use-targets.ts` (list/detail wrap the generated query hooks mapping filters→params; create/update wrap the generated mutation hooks adding `onSuccess` invalidation+toast via `useQueryClient`). Barrel exports. Import enums from `@/shared/lib/api/model`.

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/target
git commit -m "feat(frontend): target types, cardinality rules, query-keys, hooks (incl. mutations)"
```

---

### Task 2: TargetComponentsEditor (TDD pure core already in T1; component test here)

**Files:**
- Create: `frontend/src/features/target/components/target-components-editor.tsx`, `target-components-editor.test.tsx`
- Modify: `index.ts`

**Interfaces:**
- Consumes: `resolveProteinApiV1ProteinsResolveIdentifierGet` (imperative), `cardinalityHint`/`componentCountValid` (T1), `RELATIONSHIP_LABELS`, ui primitives (Input, Select, Button, Badge), `showError`.
- Produces: `<TargetComponentsEditor value={TargetComponentInput[]} onChange={(rows)=>void} targetType={TargetType} />` — controlled list of component rows.

- [ ] **Step 1: Write the failing component test** — `target-components-editor.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("@/shared/lib/api/proteins/proteins", () => ({
  resolveProteinApiV1ProteinsResolveIdentifierGet: vi.fn(),
}));
import { TargetComponentsEditor } from "./target-components-editor";
describe("TargetComponentsEditor", () => {
  it("shows the cardinality hint for the target type", () => {
    render(<TargetComponentsEditor value={[]} onChange={vi.fn()} targetType="protein_complex" />);
    expect(screen.getByText(/at least 2/i)).toBeInTheDocument();
  });
  it("renders an existing component row with its relationship", () => {
    render(
      <TargetComponentsEditor
        value={[{ protein_id: "p1", relationship: "protein_subunit", accession: "P12345", label: "Albumin" }]}
        onChange={vi.fn()}
        targetType="protein_complex"
      />,
    );
    expect(screen.getByDisplayValue("P12345")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && pnpm exec vitest run src/features/target/components/target-components-editor.test.tsx` → FAIL.

- [ ] **Step 3: Implement `target-components-editor.tsx`** (`"use client"`):
  - Renders `value` as rows: an accession/ID `Input` (controlled by `row.accession`), a resolve action (on blur or an explicit "Resolve" button) that calls `resolveProteinApiV1ProteinsResolveIdentifierGet(accession)`, and on success sets `row.protein_id` + `row.label` (the resolved `primary_accession`/recommended name) and shows a small confirmation; on failure calls `showError` and marks the row unresolved. A relationship `Select` (options from `RELATIONSHIP_LABELS`). A remove (×) `Button`. An "Add component" `Button` appends an empty row.
  - Shows `cardinalityHint(targetType)` and a live count + an inline warning when `!componentCountValid(targetType, resolvedCount)`.
  - All mutations go through `onChange(newRows)` (controlled). Each row needs a stable client key — generate one per row when added (e.g. a counter ref), NOT the array index.
  - a11y: labeled inputs, `type="button"` on all buttons.

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/target/components/target-components-editor.tsx frontend/src/features/target/components/target-components-editor.test.tsx frontend/src/features/target/index.ts
git commit -m "feat(frontend): TargetComponentsEditor (resolve proteins, relationship, cardinality hint)"
```

---

### Task 3: Target create/edit form dialog

**Files:**
- Create: `frontend/src/features/target/components/target-form-dialog.tsx`, `target-form-dialog.test.tsx`
- Modify: `index.ts`

**Interfaces:**
- Consumes: `useCreateTarget`/`useUpdateTarget` (T1), `TargetComponentsEditor` (T2), `cardinalityRule`/`componentCountValid` (T1), react-hook-form + zod, ui Dialog/Select/Input/Button/Label.
- Produces: `<TargetFormDialog open onOpenChange target?={Target} />` — create when `target` is undefined, edit otherwise.

- [ ] **Step 1: Write the failing test** — `target-form-dialog.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
vi.mock("../hooks/use-targets", () => ({
  useCreateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
import { TargetFormDialog } from "./target-form-dialog";
describe("TargetFormDialog", () => {
  it("renders the create form with a preferred-name field", () => {
    const qc = new QueryClient();
    render(<QueryClientProvider client={qc}><TargetFormDialog open onOpenChange={vi.fn()} /></QueryClientProvider>);
    expect(screen.getByLabelText(/preferred name/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && pnpm exec vitest run src/features/target/components/target-form-dialog.test.tsx` → FAIL.

- [ ] **Step 3: Implement `target-form-dialog.tsx`** (`"use client"`):
  - zod schema at top: `pref_name` (non-empty), `target_type` (enum), `components` (array of `{ protein_id: string-nonempty, relationship: enum }`), `organism_id` (optional), `chembl_id` (optional), `pharmacological_class` (optional). Add a `.superRefine` enforcing `componentCountValid(target_type, components.length)` with a message from `cardinalityHint` — attach the error to `components`.
  - `useForm` with `zodResolver`; default values from `target` when editing (map `Target.components` → `TargetComponentInput[]`, prefilling `accession`/`label` as the protein_id if unknown), or empty create defaults (`target_type: "single_protein"`, one empty component row).
  - Render: Dialog with title "New Target"/"Edit Target"; `pref_name` Input (labeled "Preferred name"); `target_type` Select (TARGET_TYPE_LABELS) — changing it should re-run cardinality validation; `TargetComponentsEditor` bound to the `components` field via Controller (value/onChange) with `targetType` = current form `target_type`; organism_id Input (free-text, "picker in Plan 3" helper text); chembl_id Input; pharmacological_class Input. Submit button disabled while `mutation.isPending`.
  - onSubmit: build `CreateTargetBody`/`UpdateTargetBody` (strip the UI-only `accession`/`label` from components → `{protein_id, relationship}`), call `useCreateTarget().mutateAsync(body)` or `useUpdateTarget().mutateAsync({targetId, data})`, then `onOpenChange(false)`. (Errors surface via the global mutation toast; do not duplicate.)
  - Reset form on `open` transition.

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/target/components/target-form-dialog.tsx frontend/src/features/target/components/target-form-dialog.test.tsx frontend/src/features/target/index.ts
git commit -m "feat(frontend): target create/edit form dialog (rhf+zod, cardinality refine)"
```

---

### Task 4: Target list page

**Files:**
- Create: `frontend/src/features/target/components/target-columns.tsx`, `target-list.tsx`, `target-list.test.tsx`
- Create: `frontend/src/app/(dashboard)/targets/page.tsx`
- Modify: `index.ts`

**Interfaces:**
- Consumes: `useTargets` (T1), `TargetFormDialog` (T3), `DataGrid`, `TARGET_TYPE_LABELS`, ui primitives.
- Produces: `<TargetListPage/>`.

- [ ] **Step 1: Write the failing test** — `target-list.test.tsx` (mirror protein-list.test pattern: mock `useTargets` + `next/navigation` + `DataGrid`; assert a target row "EGFR" renders):
```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../hooks/use-targets", () => ({
  useTargets: () => ({ data: { items: [{ id: "t1", pref_name: "EGFR", target_type: "single_protein", components: [{ id: "c1", protein_id: "p1", relationship: "single_protein" }], cross_references: [], version: 1, workspace_id: "w1" }], next_cursor: null }, isLoading: false, isError: false }),
}));
import { TargetListPage } from "./target-list";
describe("TargetListPage", () => {
  it("renders a target row", () => {
    const qc = new QueryClient();
    render(<QueryClientProvider client={qc}><TargetListPage /></QueryClientProvider>);
    expect(screen.getByText("EGFR")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && pnpm exec vitest run src/features/target/components/target-list.test.tsx` → FAIL.

- [ ] **Step 3: Implement.** `target-columns.tsx`: ColDefs — pref_name (link to `/targets/{id}`), target_type (Badge via `TARGET_TYPE_LABELS`), component count (`components.length`), organism chip (`/organisms/{organism_id}` when set; Plan-3 comment), chembl_id. `target-list.tsx` (`"use client"`): filter toolbar (target_type Select, chembl_id Input) + cursor-stack pagination + a "New Target" Button opening `<TargetFormDialog>` in create mode + `DataGrid` + loading/empty/error + localStorage prefs `pc-targets-filters` (lazy single read). `onRowClick`→`/targets/{id}`. Route page → `<TargetListPage/>`.

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/target/components/target-columns.tsx frontend/src/features/target/components/target-list.tsx frontend/src/features/target/components/target-list.test.tsx frontend/src/features/target/index.ts "frontend/src/app/(dashboard)/targets/page.tsx"
git commit -m "feat(frontend): target list page (DataGrid, filters, pagination, New Target)"
```

---

### Task 5: Target detail page

**Files:**
- Create: `frontend/src/features/target/components/target-detail.tsx`, `target-detail.test.tsx`
- Create: `frontend/src/app/(dashboard)/targets/[id]/page.tsx`
- Modify: `index.ts`

**Interfaces:**
- Consumes: `useTarget` (T1), `TargetFormDialog` (T3, edit mode), `CrossReferenceLinks`, `TARGET_TYPE_LABELS`/`RELATIONSHIP_LABELS`, ui primitives.
- Produces: `<TargetDetailPage targetId: string />`.

- [ ] **Step 1: Write the failing test** — `target-detail.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("../hooks/use-targets", () => ({
  useTarget: () => ({ data: { id: "t1", workspace_id: "w1", pref_name: "EGFR", target_type: "single_protein", components: [{ id: "c1", protein_id: "p1", relationship: "single_protein" }], chembl_id: "CHEMBL203", chembl_url: "https://x/CHEMBL203", cross_references: [], version: 1 }, isLoading: false, isError: false }),
  useUpdateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCreateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
import { TargetDetailPage } from "./target-detail";
describe("TargetDetailPage", () => {
  it("shows the target name and a component", () => {
    render(<TargetDetailPage targetId="t1" />);
    expect(screen.getByRole("heading", { name: "EGFR" })).toBeInTheDocument();
    expect(screen.getByText(/p1/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && pnpm exec vitest run src/features/target/components/target-detail.test.tsx` → FAIL.

- [ ] **Step 3: Implement `target-detail.tsx`** (`"use client"`): header (pref_name h1; target_type Badge; chembl external link via `chembl_url` when set; an "Edit" Button opening `<TargetFormDialog target={target} />`); a **components table** (each row: protein link → `/proteins/{protein_id}` [note: links by protein id; the proteins detail resolves by accession, so for now link to `/proteins/{protein_id}` and add a comment that protein-id→accession linking is refined when organism/protein cross-linking lands], relationship via `RELATIONSHIP_LABELS`); metadata (organism chip, pharmacological_class); `CrossReferenceLinks items={cross_references}`; states isLoading→skeleton, isError/!data→"Target not found". Route `app/(dashboard)/targets/[id]/page.tsx` async params → `<TargetDetailPage targetId={id} />`.

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/target/components/target-detail.tsx frontend/src/features/target/components/target-detail.test.tsx frontend/src/features/target/index.ts "frontend/src/app/(dashboard)/targets/[id]/page.tsx"
git commit -m "feat(frontend): target detail page (components table, metadata, edit)"
```

---

### Task 6: Green gate + smoke

- [ ] **Step 1: Route smoke** — `cd frontend && (pnpm dev > /tmp/pc-fe.log 2>&1 &) ; sleep 16` then `curl -fsS -o /dev/null -w "targets=%{http_code}\n" http://localhost:3000/targets` (expect 200). `pkill -f "next dev"`.
- [ ] **Step 2: Full green gate** — `cd frontend && pnpm lint && pnpm exec tsc --noEmit && pnpm test && pnpm build` → biome exit 0 (pre-existing data-grid warns only); tsc clean; all tests pass (Plan 0+1 = 32, plus new ~7); `next build` succeeds with `/targets` + `/targets/[id]`.
- [ ] **Step 3: Commit (if any wiring changed)** — `git add -A frontend && git commit -m "chore(frontend): target green gate"` (skip if nothing changed).

---

## Self-Review

**Spec coverage (spec §5.3 + §12 Plan 2):** Target browse/detail → T4/T5; create/edit → T3; `TargetComponentsEditor` + the single-vs-complex cardinality invariant → T1 (pure rule + TDD) + T2 (editor) + T3 (zod refine, the authoritative gate); workspace-scoped (no workspace_id in forms) → respected; chembl interop seam shown (chembl_id/url) → T4/T5; no delete (no endpoint) → respected.

**Placeholder scan:** no TBD/TODO; exact hooks/DTOs/enums inlined; pure cardinality + its tests full; component/form/list/detail tests provided.

**Type consistency:** `useCreateTarget`/`useUpdateTarget` wrap the exact generated mutation hooks with `onSuccess` invalidation+toast and NO per-mutation onError (avoids the Plan-0 double-toast). `TargetComponentInput` carries UI-only `accession`/`label` stripped before building `ComponentBody`. Cardinality enforced in three consistent layers: pure `componentCountValid` (T1) → editor hint/warning (T2) → zod `superRefine` (T3, the submit gate). Filters→`ListTargetsApiV1TargetsGetParams` use only real fields (`target_type`, `chembl_id`).

**Known deferrals (intentional, noted in code):** organism id-only until Plan 3; cross-reference editing not in the form (create/edit covers core fields; xrefs shown read-only on detail); component protein links use protein_id (accession cross-linking refined later); no delete (no backend endpoint).
