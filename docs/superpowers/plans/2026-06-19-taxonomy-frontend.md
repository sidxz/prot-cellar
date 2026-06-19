# Taxonomy Frontend (Plan 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Taxonomy feature slice — organisms (browse/detail + ancestor lineage), strains (workspace-scoped CRUD), proteomes (browse/detail) — and a shared `OrganismRef` so organism IDs across the whole app finally resolve to names.

**Architecture:** A `taxonomy` feature slice mirroring `protein-catalog`/`target` conventions. Organisms + proteomes are shared reference data → read-first (browse/search/detail; no create/edit UI). Strains are workspace data → full create/edit (mutations invalidate the **generated** query keys, per the Plan-2 lesson). A shared `OrganismRef` component (in `shared/`, using the generated organism get-hook) is retrofitted onto the protein/gene/target detail pages.

**Tech Stack:** Next 16 App Router, React 19, TanStack Query (orval hooks), shadcn/radix, ag-grid via `DataGrid`, react-hook-form + zod, the established `CrossReferenceLinks`/`DataGrid`/toast.

## Global Constraints

- **Foundation branch:** `feat/frontend` (HEAD `9f4499e` at plan time). Work in `frontend/`. OpenAPI = committed snapshot.
- **Reference patterns (mirror exactly):** `frontend/src/features/protein-catalog/**` (read-first list/detail, lazy `useState(readFilters)`, cursor-stack pagination, columns separate from pages, `toProtein`-style narrowing) and `frontend/src/features/target/**` (workspace CRUD: form dialog rhf+zod, mutation wrappers, `TARGET_TYPE_LABELS`-style maps). Strains follow the **Target** CRUD pattern; organisms/proteomes follow the **protein-catalog** read pattern.
- **Exact generated hooks:**
  - Organisms (`@/shared/lib/api/organisms/organisms`): `useListOrganismsApiV1OrganismsGet(params?)` → `PaginatedResponseOrganismResponse`; `useGetOrganismApiV1OrganismsOrganismIdGet(organismId)` → `OrganismResponse`; `useResolveOrganismApiV1OrganismsResolveTaxIdGet(taxId)` → `OrganismResponse`; plus the NON-hook `getOrganismApiV1OrganismsOrganismIdGet(organismId)` for the lineage walk. (Create/update/bulk exist but are admin reference-data ops — DO NOT surface them.)
  - Strains (`@/shared/lib/api/strains/strains`): `useListStrainsApiV1StrainsGet(params?)`, `useGetStrainApiV1StrainsStrainIdGet(strainId)`, `useCreateStrainApiV1StrainsPost()` (vars `{data: CreateStrainBody}`), `useUpdateStrainApiV1StrainsStrainIdPatch()` (vars `{strainId, data: UpdateStrainBody}`). No delete.
  - Proteomes (`@/shared/lib/api/proteomes/proteomes`): `useListProteomesApiV1ProteomesGet(params?)`, `useGetProteomeApiV1ProteomesProteomeIdGet(proteomeId)`. (Create exists; proteomes are read-first in this plan — DO NOT surface create.)
  - **READ each generated file to confirm exact hook + non-hook + key-helper names** before wiring.
- **MUTATION INVALIDATION (Plan-2 lesson — non-negotiable):** strain create/update wrappers MUST invalidate the orval-**generated** query keys, NOT hand-rolled ones. Import + use `getListStrainsApiV1StrainsGetQueryKey()` (list prefix) and `getGetStrainApiV1StrainsStrainIdGetQueryKey(strainId)` (detail) in `onSuccess`. NO per-mutation `onError` (global MutationCache toasts errors — a second would double-toast). Add a regression test asserting the generated keys are invalidated.
- **DTOs (re-narrow in `types/index.ts`):**
  - `OrganismResponse { id, ncbi_tax_id?, ncbi_url?, parent_id?, rank, scientific_name, division?, is_merged, merged_into_id?, is_deleted, source (ncbi|gtdb|local), source_release?, version, names: OrganismNameResponse[] }`; `OrganismNameResponse { name, name_class (NameClass), unique_name?, is_preferred }`.
  - `StrainResponse { id, workspace_id, species_organism_id, strain_organism_id?, name, isolate?, biosample_acc?, assembly_acc?, culture_collection?, host_organism_id?, metadata?, version }`. `CreateStrainBody` = `{species_organism_id, name, strain_organism_id?, isolate?, biosample_acc?, assembly_acc?, culture_collection?, host_organism_id?, metadata?}`. `UpdateStrainBody` = all-optional (no species_organism_id).
  - `ProteomeResponse { id, uniprot_proteome_id, proteome_url?, organism_id, strain_id?, proteome_type (ProteomeType), is_reference, assembly_acc?, source_version?, version }`.
- **Enums (generated consts):** `NameClass` (9), `OrganismSource` (ncbi|gtdb|local), `ProteomeType` (reference|representative|redundant|excluded).
- **List params:** organisms `{name?, rank?, cursor?, limit?}`; strains `{cursor?, limit?}` (no filters); proteomes `{organism_id?, cursor?, limit?}`.
- **Lineage:** `OrganismResponse.parent_id` only (no children-list endpoint, no parent_id list filter). The detail "lineage" = an **ancestor breadcrumb** built by walking `parent_id` upward (bounded). A direct-children list is DEFERRED (no API) — note it.
- **Organism display name:** `organism.scientific_name` (top-level). `names[]` shows the multi-name table; a helper picks a common name.
- **Lint/test:** biome clean (no new warnings; 8 pre-existing data-grid warns OK); `pnpm test` green; `pnpm build` OK. a11y. Commit per task on `feat/frontend`, trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

```
frontend/src/shared/components/common/organism-ref.tsx     # T2 shared <OrganismRef id/> (+ test)
frontend/src/features/taxonomy/
  types/index.ts            # T1 narrowed types + label maps + filter/form types
  lib/organism-format.ts    # T1 organismCommonName(names) (pure) + test
  hooks/use-organisms.ts    # T1 useOrganisms/useOrganism/useResolveOrganism/useOrganismLineage
  hooks/use-strains.ts      # T1 useStrains/useStrain/useCreateStrain/useUpdateStrain (gen-key invalidation)
  hooks/use-proteomes.ts    # T1 useProteomes/useProteome
  components/
    organism-list.tsx organism-columns.tsx        # T3
    organism-detail.tsx organism-lineage.tsx      # T3 (lineage breadcrumb + names table)
    strain-list.tsx strain-columns.tsx            # T4
    strain-form-dialog.tsx                        # T4
    strain-detail.tsx                             # T4
    proteome-list.tsx proteome-columns.tsx        # T5
    proteome-detail.tsx                           # T5
  index.ts                  # barrel
frontend/src/app/(dashboard)/
  organisms/page.tsx  organisms/[id]/page.tsx     # T3
  strains/page.tsx    strains/[id]/page.tsx       # T4
  proteomes/page.tsx  proteomes/[id]/page.tsx     # T5
```

---

### Task 1: Scaffolding — types, organism-format (TDD), hooks (organisms read + strains CRUD + proteomes + lineage)

**Files:** Create `types/index.ts`, `lib/organism-format.ts`(+test), `hooks/use-organisms.ts`, `hooks/use-strains.ts`, `hooks/use-proteomes.ts`, `index.ts`.

**Interfaces:**
- types: `Organism`, `OrganismName`, `Strain`, `Proteome` (narrowed); `NAME_CLASS_LABELS`, `ORGANISM_SOURCE_LABELS`, `PROTEOME_TYPE_LABELS`; `OrganismListFilters = {name?, rank?}`; `ProteomeListFilters = {organismId?}`; `StrainFormValues`.
- `organismCommonName(names: OrganismName[]): string | null` — first `common_name`, else `genbank_common_name`, else null.
- organism hooks: `useOrganisms(filters, cursor?)`, `useOrganism(id)`, `useResolveOrganism(taxId)`, `useOrganismLineage(organism: Organism | undefined)` — a `useQuery` keyed `["organism-lineage", organism?.id]`, `enabled: !!organism?.parent_id`, whose `queryFn` walks `parent_id` upward by calling the NON-hook `getOrganismApiV1OrganismsOrganismIdGet` (bounded to ≤ 30 hops, stop on missing/cycle), returning `Organism[]` ordered root→immediate-parent.
- strain hooks: `useStrains(cursor?)`, `useStrain(id)`, `useCreateStrain()` / `useUpdateStrain()` — wrap the generated mutation hooks; `onSuccess` invalidates `getListStrainsApiV1StrainsGetQueryKey()` (create + update) and `getGetStrainApiV1StrainsStrainIdGetQueryKey(variables.strainId)` (update); `showSuccess`; NO `onError`.
- proteome hooks: `useProteomes(filters, cursor?)`, `useProteome(id)`.

- [ ] **Step 1: Failing test** — `lib/organism-format.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { organismCommonName } from "./organism-format";
const n = (name: string, name_class: string) => ({ name, name_class, is_preferred: false }) as never;
describe("organismCommonName", () => {
  it("prefers common_name", () => {
    expect(organismCommonName([n("Human", "common_name"), n("man", "genbank_common_name")])).toBe("Human");
  });
  it("falls back to genbank_common_name then null", () => {
    expect(organismCommonName([n("man", "genbank_common_name")])).toBe("man");
    expect(organismCommonName([n("Homo sapiens", "scientific_name")])).toBeNull();
  });
});
```
- [ ] **Step 2: Run → FAIL** — `cd frontend && pnpm exec vitest run src/features/taxonomy/lib/organism-format.test.ts`.
- [ ] **Step 3: Implement** all files per Interfaces. For `useStrains` mutations, import the generated key helpers from `@/shared/lib/api/strains/strains` and invalidate them in `onSuccess` (mirror `frontend/src/features/target/hooks/use-targets.ts`). For `useOrganismLineage`, import the non-hook `getOrganismApiV1OrganismsOrganismIdGet`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Verify + commit** — `cd frontend && pnpm exec tsc --noEmit && pnpm lint`; `git add frontend/src/features/taxonomy && git commit -m "feat(frontend): taxonomy types, organism-format, hooks (organisms/strains/proteomes + lineage)"`.

---

### Task 2: shared `OrganismRef` (the payoff component)

**Files:** Create `frontend/src/shared/components/common/organism-ref.tsx`, `organism-ref.test.tsx`.

**Interfaces:** `<OrganismRef id={string | null | undefined} className?={string} />` — uses `useGetOrganismApiV1OrganismsOrganismIdGet(id)` (enabled when `id` set); renders `scientific_name` as a `next/link` to `/organisms/{id}`; `Skeleton` while loading; falls back to a short-id chip on error/no id. Lives in `shared/` (no feature coupling), uses the generated hook directly.

- [ ] **Step 1: Failing test** — `organism-ref.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("@/shared/lib/api/organisms/organisms", () => ({
  useGetOrganismApiV1OrganismsOrganismIdGet: () => ({ data: { id: "o1", scientific_name: "Homo sapiens" }, isLoading: false, isError: false }),
}));
import { OrganismRef } from "./organism-ref";
describe("OrganismRef", () => {
  it("renders the scientific name as a link", () => {
    render(<OrganismRef id="o1" />);
    expect(screen.getByRole("link", { name: /Homo sapiens/ })).toHaveAttribute("href", "/organisms/o1");
  });
});
```
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement** `organism-ref.tsx`. Note: query is `enabled: !!id`; while loading show a small `Skeleton`; on error or `!id` render a muted short-id (or "—"). Keep it tiny and dependency-light.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Verify + commit** — tsc + lint; `git add frontend/src/shared/components/common/organism-ref.tsx frontend/src/shared/components/common/organism-ref.test.tsx && git commit -m "feat(frontend): shared OrganismRef (resolve organism id -> name link)"`.

---

### Task 3: Organisms — list + detail (with ancestor lineage)

**Files:** Create `components/organism-list.tsx`, `organism-columns.tsx`, `organism-detail.tsx`, `organism-lineage.tsx`, `organism-list.test.tsx`, `organism-detail.test.tsx`; routes `app/(dashboard)/organisms/page.tsx`, `organisms/[id]/page.tsx`; update barrel.

**Interfaces:** `<OrganismListPage/>`, `<OrganismDetailPage organismId/>`. Read-first (no create/edit).

- [ ] **Step 1: Failing tests** — `organism-list.test.tsx` (mock `useOrganisms` + `next/navigation` + `DataGrid`; assert "Homo sapiens" renders) and `organism-detail.test.tsx` (mock `useOrganism` returning an organism with `names`; mock `useOrganismLineage` → `{data: [], isLoading:false}`; assert the scientific name heading + a name-table entry render). Use the protein-list/detail tests as the shape.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.**
  - `organism-columns.tsx`: scientific_name (link `/organisms/{id}`), rank (Badge), ncbi_tax_id (link via `ncbi_url`), common name (`organismCommonName(row.names)`), source (Badge `ORGANISM_SOURCE_LABELS`). stopPropagation on links.
  - `organism-list.tsx` (`"use client"`): filter toolbar (debounced `name` search + `rank` input), cursor-stack pagination, lazy `useState(readFilters)` prefs `pc-organisms-filters`, `DataGrid`, loading/empty/error, row→`/organisms/{id}`.
  - `organism-lineage.tsx`: given `organism`, render an ancestor breadcrumb from `useOrganismLineage` (links root→parent→… then the current organism as the tail, non-link), with a skeleton while loading. If no `parent_id`, render just the current organism / nothing.
  - `organism-detail.tsx` (`"use client"`): header (scientific_name h1, rank Badge, ncbi external link, source Badge, plus `is_merged`/`is_deleted` warning Badges when set + a `merged_into_id` link when merged); `<OrganismLineage organism={organism} />`; a **names table** (name / `NAME_CLASS_LABELS[name_class]` / preferred star); a "Parent" row linking to `/organisms/{parent_id}` when set; states isLoading→skeleton, isError/!data→"Organism not found". Note in a comment: direct-children list deferred (no API).
  - routes: async params; list/detail pages.
- [ ] **Step 4: Run → PASS** (both tests + full suite).
- [ ] **Step 5: Verify + commit** — tsc + lint; commit `feat(frontend): organism list + detail (lineage breadcrumb, names table)`.

---

### Task 4: Strains — list + detail + create/edit form (workspace CRUD)

**Files:** Create `components/strain-list.tsx`, `strain-columns.tsx`, `strain-form-dialog.tsx`, `strain-detail.tsx`, `strain-list.test.tsx`, `strain-form-dialog.test.tsx`, `strain-detail.test.tsx`; routes `strains/page.tsx`, `strains/[id]/page.tsx`; barrel.

**Interfaces:** `<StrainListPage/>`, `<StrainFormDialog open onOpenChange strain?/>`, `<StrainDetailPage strainId/>`. Mirror the **target** CRUD trio.

- [ ] **Step 1: Failing tests** — `strain-list.test.tsx` (mock `useStrains` + nav + DataGrid; assert a strain `name` renders), `strain-form-dialog.test.tsx` (mock `../hooks/use-strains` create/update; render create mode; assert a "Name" + "Species organism" labeled field), `strain-detail.test.tsx` (mock `useStrain`; assert the strain name heading). Mirror the target test shapes.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.**
  - `strain-columns.tsx`: name (link `/strains/{id}`), species organism (`<OrganismRef id={row.species_organism_id}/>`), strain organism (`<OrganismRef>` when set), biosample_acc, assembly_acc, culture_collection. stopPropagation.
  - `strain-list.tsx`: no API filters (just cursor/limit) → toolbar has only a "New Strain" Button (opens `<StrainFormDialog>` create) + cursor-stack pagination + `DataGrid` + states. (No localStorage filters needed; still lazy-read if you add a client-side name filter — optional, keep simple: no client filter.)
  - `strain-form-dialog.tsx` (rhf+zod, mirror target-form-dialog): schema `species_organism_id` (min 1), `name` (min 1), optional `strain_organism_id`/`isolate`/`biosample_acc`/`assembly_acc`/`culture_collection`/`host_organism_id`, `metadata` (optional JSON string → parse to object on submit; show a validation error if invalid JSON). Create defaults empty; edit prefill from `strain` (note: `species_organism_id` is NOT in `UpdateStrainBody` — render it read-only/disabled in edit mode). organism-id fields are text inputs with helper text "paste an organism id (organism search picker — future)". onSubmit strips empties, parses metadata, calls `useCreateStrain().mutateAsync({data})` / `useUpdateStrain().mutateAsync({strainId, data})`, closes on success; NO manual error toast.
  - `strain-detail.tsx`: header (name h1; Edit button → `StrainFormDialog` edit mode); metadata (species organism `<OrganismRef>`, strain organism `<OrganismRef>`, isolate, biosample/assembly/culture, host organism `<OrganismRef>`, metadata pretty-printed); states.
  - routes: async params.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Verify + commit** — tsc + lint; commit `feat(frontend): strain list + detail + create/edit form (workspace CRUD)`.

---

### Task 5: Proteomes — list + detail (read-first)

**Files:** Create `components/proteome-list.tsx`, `proteome-columns.tsx`, `proteome-detail.tsx`, `proteome-list.test.tsx`; routes `proteomes/page.tsx`, `proteomes/[id]/page.tsx`; barrel.

**Interfaces:** `<ProteomeListPage/>`, `<ProteomeDetailPage proteomeId/>`. Read-first (create endpoint exists but is deferred — note it).

- [ ] **Step 1: Failing test** — `proteome-list.test.tsx` (mock `useProteomes` + nav + DataGrid; assert a `uniprot_proteome_id` like "UP000005640" renders).
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.**
  - `proteome-columns.tsx`: uniprot_proteome_id (link `/proteomes/{id}`; external via `proteome_url`), organism (`<OrganismRef id={row.organism_id}/>`), proteome_type (Badge `PROTEOME_TYPE_LABELS`), is_reference (Badge/check), assembly_acc. stopPropagation.
  - `proteome-list.tsx`: filter toolbar (organism_id text input → `ProteomeListFilters.organismId`), cursor-stack pagination, lazy prefs `pc-proteomes-filters`, `DataGrid`, states, row→`/proteomes/{id}`.
  - `proteome-detail.tsx`: header (uniprot_proteome_id h1; external proteome link; proteome_type Badge; is_reference Badge); metadata (organism `<OrganismRef>`, strain link `/strains/{strain_id}` when set, assembly_acc, source_version); states.
  - routes: async params.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Verify + commit** — tsc + lint; commit `feat(frontend): proteome list + detail (read-first)`.

---

### Task 6: Retrofit OrganismRef onto existing detail pages (the payoff)

**Files:** Modify `frontend/src/features/protein-catalog/components/protein-detail.tsx`, `gene-detail.tsx`, and `frontend/src/features/target/components/target-detail.tsx`.

**Interfaces:** replace the raw organism-id link chip (the `/organisms/{organism_id}` chip showing a short id, marked "resolves to name in Plan 3") with `<OrganismRef id={organism_id} />` from `@/shared/components/common/organism-ref`.

- [ ] **Step 1: Apply the swap** in all three detail pages — import `OrganismRef`, replace the organism chip's inner content; keep the surrounding label/row. Remove the now-stale "Plan 3" comment.
- [ ] **Step 2: Update any test** that asserted the old id-chip text (the detail tests mock `useGetOrganism...`? They don't — `OrganismRef` will call the real hook in tests; mock `@/shared/lib/api/organisms/organisms`'s `useGetOrganismApiV1OrganismsOrganismIdGet` in the three detail tests to return `{data: undefined, isLoading:false, isError:false}` so the fallback renders and the tests stay green). Keep assertions valid.
- [ ] **Step 3: Verify + commit** — `cd frontend && pnpm exec vitest run && pnpm exec tsc --noEmit && pnpm lint`; commit `feat(frontend): resolve organism ids to names on protein/gene/target detail (OrganismRef)`.

---

### Task 7: Green gate + route smoke

- [ ] **Step 1: Route smoke** — `cd frontend && (pnpm dev > /tmp/pc-fe.log 2>&1 &) ; sleep 16` then curl `/organisms /strains /proteomes` (expect 200 each); `pkill -f "next dev"`.
- [ ] **Step 2: Full green gate** — `cd frontend && pnpm lint && pnpm exec tsc --noEmit && pnpm test && pnpm build` → biome exit 0 (pre-existing data-grid warns only); tsc clean; all tests pass; `next build` OK with the 6 new routes (`/organisms`, `/organisms/[id]`, `/strains`, `/strains/[id]`, `/proteomes`, `/proteomes/[id]`).
- [ ] **Step 3: Commit** (if wiring changed) — `git add -A frontend && git commit -m "chore(frontend): taxonomy green gate"`.

---

## Self-Review

**Spec coverage (spec §5.1 + §12 Plan 3):** organisms browse/detail + lineage → T3 (ancestor breadcrumb; children-list deferred per missing API); strains workspace CRUD → T4 (Target pattern + generated-key invalidation); proteomes browse/detail → T5; organism-name resolution across the app → T2 (`OrganismRef`) + T6 (retrofit). Read/write split honored (organisms/proteomes read-first; strains CRUD).

**Placeholder scan:** no TBD/TODO; exact hooks/DTOs/enums named; pure `organismCommonName` + test full; per-page tests provided.

**Type consistency:** strain mutations invalidate the **generated** `getList/GetStrains…QueryKey` (Plan-2 fix), with a regression test; `useOrganismLineage` walks via the non-hook get fn (no hooks-in-loop); `OrganismRef` lives in shared (no feature→feature coupling) and is consumed by T6. Filters map to real params only (organisms name/rank; proteomes organism_id; strains none).

**Known deferrals (noted in code):** organism direct-children list (no API); organism create/edit + proteome create (admin/reference — endpoints exist, UI deferred); organism search-picker for strain organism fields (text id inputs for now); list-column organism names still id-based where a per-row fetch would be wasteful (detail pages get `OrganismRef`).
