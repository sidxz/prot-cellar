# Protein Catalog Frontend (Plan 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Protein Catalog feature slice — browse/search/detail for **proteins** (with sequence + cross-references + FASTA) and **genes** — on top of the Plan 0 foundation, as the first vertical proving the data path end-to-end.

**Architecture:** A `protein-catalog` feature slice (`src/features/protein-catalog/{components,hooks,types,lib,index.ts}`) consuming the orval-generated hooks via thin domain wrappers, rendered by thin App-Router pages under `(dashboard)/proteins` and `(dashboard)/genes`. Reference data is **read-first**: browse (DataGrid + filters + cursor pagination), detail (metadata + `SequenceViewer` + `CrossReferenceLinks`), and accession/ID lookup via the resolve endpoint. No create/edit UI in this plan (admin edits deferred per spec §7).

**Tech Stack:** Next 16 App Router, React 19, TanStack Query (orval hooks), shadcn/radix, ag-grid via `DataGrid`, the Plan-0 `SequenceViewer`/`CrossReferenceLinks`/`createCrudHooks`/`customInstance`/`toast`.

## Global Constraints

- **Foundation branch:** `feat/frontend` (HEAD `281c06e` at plan time). Work in `frontend/`. Backend OpenAPI is the committed `frontend/openapi.json`; regen via `pnpm generate:api` only if the backend changes (it won't in this plan).
- **Reference frontend (patterns to mirror):** `~/workspace/chem-vault2/frontend/src/features/` — use the `compounds` (entity browse/detail) and `research-organization` (list page + filters + DataGrid + detail) slices as the structural template: `components/`, `hooks/query-keys.ts` + `use-*.ts`, `types/index.ts` (alias + re-narrow orval DTOs), `index.ts` barrel.
- **Reuse, do not reinvent:** `DataGrid` (`@/shared/components/data-grid/data-grid`), `SequenceViewer` + `sequence.ts` (`@/shared/components/sequence/*`), `CrossReferenceLinks` (`@/shared/components/xrefs/cross-reference-links`), `createCrudHooks`/`unwrapList` (`@/shared/lib/api/crud-hooks`), `customInstance`/`API_V1` (`@/shared/lib/api/custom-instance`), `showError`/`showSuccess` (`@/shared/lib/toast`), ui primitives (`@/shared/components/ui/*`).
- **Read-first:** proteins & genes are shared reference data. This plan ships **browse + search + detail only**. Do NOT surface create/edit/delete UI (the generated `useCreateProtein…`/`useUpdateProtein…`/`useCreateGene…` hooks exist but stay unused this plan).
- **Exact generated hooks (do not rename; import from the tag files):**
  - Proteins (`@/shared/lib/api/proteins/proteins`): `useListProteinsApiV1ProteinsGet(params?)` → `PaginatedResponseProteinResponse`; `useGetProteinApiV1ProteinsAccessionGet(accession, params?)` → **`unknown`** (content-negotiated); `useResolveProteinApiV1ProteinsResolveIdentifierGet(identifier)` → `ProteinResponse`.
  - Genes (`@/shared/lib/api/genes/genes`): `useListGenesApiV1GenesGet(params?)` → `PaginatedResponseGeneResponse`; `useGetGeneApiV1GenesGeneIdGet(geneId)` → `GeneResponse`.
- **Param types:** `ListProteinsApiV1ProteinsGetParams = { organism_id?, gene_id?, reviewed?, min_length?, max_length?, cursor?, limit? }` (all `… | null`). `ListGenesApiV1GenesGetParams = { name?, organism_id?, cursor?, limit? }`. There is **no** protein name/accession list filter — accession/ID search uses the **resolve** endpoint (returns one protein → navigate to its detail).
- **DTO facts (re-narrow in `types/index.ts`):** `ProteinResponse` has `id, primary_accession, uniprot_url?, secondary_accessions[], entry_name?, is_reviewed, protein_names ({recommended?,alternative[],submitted[]} — generated loosely as `{[k]:unknown}`; re-narrow), organism_id, strain_id?, gene_id?, seq_length, seq_mass?, seq_crc64?, protein_existence?, keywords[], entry_version?, sequence_version?, cross_references[], version`. **It has NO `sequence` field.** `GeneResponse` has `id, primary_name, organism_id, synonyms[], ncbi_gene_id?, ncbi_gene_url?, ensembl_gene_id?, ensembl_url?, hgnc_id?, cross_references[], version`. `CrossReferenceResponse = { database, accession, curie, url? }`.
- **Sequence access (the load-bearing constraint):** the amino-acid sequence is **only** available via `GET /api/v1/proteins/{accession}?format=fasta` (`text/x-fasta`); no JSON response contains it. `customInstance` currently parses JSON only — Task 1 adds a text mode. The detail page fetches FASTA, parses it, and feeds the sequence to `SequenceViewer` (length/mass come from `ProteinResponse`).
- **Organism display:** `ProteinResponse`/`GeneResponse` carry only `organism_id` (UUID), no name (the Taxonomy feature is Plan 3). Render organism as a link chip to `/organisms/{organism_id}` showing a short id; a code-comment must note "resolves to organism name in Plan 3."
- **Lint/test:** biome clean (hand-written files are linted; mind a11y — `type` on buttons, discernible link text). `pnpm test` green; `pnpm build` succeeds. Commit per task on `feat/frontend`, trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

```
frontend/src/
  shared/lib/api/custom-instance.ts        # T1 MODIFY: add responseType:"text"
  shared/components/sequence/sequence.ts   # T1 MODIFY: add parseFasta()
  features/protein-catalog/
    types/index.ts                         # T2 narrowed Protein/Gene/CrossReference + filter types
    hooks/query-keys.ts                    # T2 PROTEINS_KEY/GENES_KEY + factories
    hooks/use-proteins.ts                  # T2 useProteins/useProtein/useProteinFasta/useResolveProtein
    hooks/use-genes.ts                     # T2 useGenes/useGene
    lib/protein-format.ts                  # T2 pure display helpers (primaryName, existenceLabel) + test
    components/
      protein-list.tsx                     # T3 ProteinListPage (DataGrid + toolbar + pagination + resolve-jump)
      protein-columns.tsx                  # T3 ag-grid ColDefs + cell renderers (reviewed badge, links)
      protein-detail.tsx                   # T4 ProteinDetailPage (metadata + SequenceViewer + xrefs)
      gene-list.tsx                        # T5 GeneListPage (DataGrid + name/organism filter + pagination)
      gene-detail.tsx                      # T6 GeneDetailPage (metadata + xref links)
    index.ts                               # T2 barrel (grown per task)
  app/(dashboard)/
    proteins/page.tsx                      # T3 -> <ProteinListPage/>
    proteins/[accession]/page.tsx          # T4 -> <ProteinDetailPage accession=.../>
    genes/page.tsx                         # T5 -> <GeneListPage/>
    genes/[id]/page.tsx                    # T6 -> <GeneDetailPage geneId=.../>
```

---

### Task 1: Foundation gaps — `customInstance` text mode + `parseFasta` (TDD)

**Files:**
- Modify: `frontend/src/shared/lib/api/custom-instance.ts`, `frontend/src/shared/lib/api/custom-instance.test.ts`
- Modify: `frontend/src/shared/components/sequence/sequence.ts`, `frontend/src/shared/components/sequence/sequence.test.ts`

**Interfaces:**
- Produces: `customInstance<T>(config & { responseType?: "json" | "text" })` — when `"text"`, return `await response.text()` as `T` (still inject base URL + auth headers + params; still throw `ApiError` on non-2xx). Default stays `"json"`.
- Produces: `parseFasta(text: string): { header: string; sequence: string }` — drops the leading `>header` line, concatenates remaining lines stripped of whitespace; for input without a `>` header, treats all lines as sequence (header `""`).

- [ ] **Step 1: Write failing tests**

Append to `custom-instance.test.ts`:
```ts
it("returns raw text when responseType is 'text'", async () => {
  fetchMock.mockResolvedValue(
    new Response(">sp|P1|X\nMAAA\nKLL", { status: 200, headers: { "content-type": "text/x-fasta" } }),
  );
  const out = await customInstance<string>({ url: "/api/v1/proteins/P1", method: "GET", params: { format: "fasta" }, responseType: "text" });
  expect(out).toBe(">sp|P1|X\nMAAA\nKLL");
});
```
Append to `sequence.test.ts`:
```ts
import { parseFasta } from "./sequence";
describe("parseFasta", () => {
  it("strips the header and joins residue lines", () => {
    expect(parseFasta(">sp|P1|X\nMAAA\nKLL")).toEqual({ header: "sp|P1|X", sequence: "MAAAKLL" });
  });
  it("handles headerless input as pure sequence", () => {
    expect(parseFasta("MAAA\nKLL")).toEqual({ header: "", sequence: "MAAAKLL" });
  });
  it("trims whitespace/blank lines", () => {
    expect(parseFasta(">h\nMA A\n\n KL \n")).toEqual({ header: "h", sequence: "MAAKL" });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**
Run: `cd frontend && pnpm exec vitest run src/shared/lib/api/custom-instance.test.ts src/shared/components/sequence/sequence.test.ts`
Expected: the new cases FAIL (`responseType`/`parseFasta` not implemented).

- [ ] **Step 3: Implement**
In `custom-instance.ts`: add `responseType?: "json" | "text"` to the config type; in the success path, when `responseType === "text"` return `(await response.text()) as T` (before the JSON parse). Keep 204→undefined and the JSON path unchanged.
In `sequence.ts`:
```ts
export function parseFasta(text: string): { header: string; sequence: string } {
  const lines = text.split("\n");
  let header = "";
  const residues: string[] = [];
  for (const line of lines) {
    if (line.startsWith(">")) { header = line.slice(1).trim(); continue; }
    residues.push(line.replace(/\s+/g, ""));
  }
  return { header, sequence: residues.join("") };
}
```

- [ ] **Step 4: Run tests to verify they pass**
Run: `cd frontend && pnpm exec vitest run src/shared/lib/api/custom-instance.test.ts src/shared/components/sequence/sequence.test.ts`
Expected: PASS (all cases).

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/shared/lib/api/custom-instance.ts frontend/src/shared/lib/api/custom-instance.test.ts frontend/src/shared/components/sequence/sequence.ts frontend/src/shared/components/sequence/sequence.test.ts
git commit -m "feat(frontend): customInstance text responseType + parseFasta (FASTA support)"
```

---

### Task 2: Feature scaffolding — types, query-keys, hooks, format helpers (TDD for helpers)

**Files:**
- Create: `frontend/src/features/protein-catalog/types/index.ts`, `hooks/query-keys.ts`, `hooks/use-proteins.ts`, `hooks/use-genes.ts`, `lib/protein-format.ts`, `lib/protein-format.test.ts`, `index.ts`

**Interfaces:**
- Produces (types): `Protein` (= `ProteinResponse` with `protein_names` re-narrowed to `{ recommended?: string | null; alternative?: string[]; submitted?: string[] }`), `Gene` (= `GeneResponse`), `CrossRef` (= `CrossReferenceResponse`), `ProteinListFilters = { reviewed?: boolean; minLength?: number; maxLength?: number; organismId?: string }`, `GeneListFilters = { name?: string; organismId?: string }`.
- Produces (query-keys): `PROTEINS_KEY = ["proteins"] as const`, `proteinDetailKey(accession)`, `proteinFastaKey(accession)`, `GENES_KEY = ["genes"]`, `geneDetailKey(id)`.
- Produces (hooks):
  - `useProteins(filters, cursor?)` — wraps `useListProteinsApiV1ProteinsGet`, mapping `ProteinListFilters`→params; returns the query (items via `data.items`, `data.next_cursor`).
  - `useProtein(accession)` — wraps `useGetProteinApiV1ProteinsAccessionGet(accession)`, narrowing the `unknown` result `as ProteinResponse | undefined`.
  - `useProteinFasta(accession)` — `useQuery` keyed `proteinFastaKey`, calling `customInstance<string>({ url: \`${API_V1}/proteins/${accession}\`, method: "GET", params: { format: "fasta" }, responseType: "text" })`, `enabled: !!accession`; returns `{ header, sequence }` via `select: parseFasta`.
  - `useResolveProtein(identifier)` — wraps `useResolveProteinApiV1ProteinsResolveIdentifierGet`, `enabled: !!identifier`.
  - `useGenes(filters, cursor?)`, `useGene(id)` — wrap the gene hooks.
- Produces (lib): `proteinPrimaryName(p: Protein): string` (recommended → first submitted → entry_name → primary_accession); `proteinExistenceLabel(pe?: string | null): string` (maps PE codes to readable text, else "—").

- [ ] **Step 1: Write failing test for the pure helpers** — `lib/protein-format.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { proteinExistenceLabel, proteinPrimaryName } from "./protein-format";

const base = { primary_accession: "P1", entry_name: null, protein_names: {} } as never;
describe("proteinPrimaryName", () => {
  it("prefers recommended", () => {
    expect(proteinPrimaryName({ ...base, protein_names: { recommended: "Albumin" } })).toBe("Albumin");
  });
  it("falls back to entry_name then accession", () => {
    expect(proteinPrimaryName({ ...base, entry_name: "ALBU_HUMAN" })).toBe("ALBU_HUMAN");
    expect(proteinPrimaryName(base)).toBe("P1");
  });
});
describe("proteinExistenceLabel", () => {
  it("maps known codes and falls back to dash", () => {
    expect(proteinExistenceLabel(null)).toBe("—");
    expect(typeof proteinExistenceLabel("EVIDENCE_AT_PROTEIN_LEVEL")).toBe("string");
  });
});
```

- [ ] **Step 2: Run to verify fail**
Run: `cd frontend && pnpm exec vitest run src/features/protein-catalog/lib/protein-format.test.ts`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement types, query-keys, hooks, and `protein-format.ts`.** Implement `proteinPrimaryName`/`proteinExistenceLabel` to satisfy the tests; build the hooks per the Interfaces block above, importing the exact generated hooks named in Global Constraints and `customInstance`/`API_V1`/`parseFasta`. Export public surface from `index.ts`. (Wrappers should expose `{ data, isLoading, isError, … }` from the underlying query plus convenience accessors where helpful; keep them thin.)

- [ ] **Step 4: Run to verify pass**
Run: `cd frontend && pnpm exec vitest run src/features/protein-catalog/lib/protein-format.test.ts`
Expected: PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/protein-catalog
git commit -m "feat(frontend): protein-catalog types, query-keys, hooks, format helpers"
```

---

### Task 3: Protein list page

**Files:**
- Create: `frontend/src/features/protein-catalog/components/protein-list.tsx`, `protein-columns.tsx`
- Create: `frontend/src/app/(dashboard)/proteins/page.tsx`
- Modify: `frontend/src/features/protein-catalog/index.ts` (export `ProteinListPage`)
- Create test: `frontend/src/features/protein-catalog/components/protein-list.test.tsx`

**Interfaces:**
- Consumes: `useProteins` (T2), `DataGrid`, ui primitives, `proteinPrimaryName`.
- Produces: `<ProteinListPage/>` — DataGrid of proteins + a filter toolbar + cursor pagination + an accession/ID "jump" box.

- [ ] **Step 1: Write the failing component test** — `protein-list.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../hooks/use-proteins", () => ({
  useProteins: () => ({ data: { items: [{ id: "1", primary_accession: "P12345", entry_name: "ALBU_HUMAN", is_reviewed: true, seq_length: 609, organism_id: "o1", protein_names: { recommended: "Albumin" }, secondary_accessions: [], keywords: [], cross_references: [], version: 1 }], next_cursor: null }, isLoading: false, isError: false }),
}));
import { ProteinListPage } from "./protein-list";
function renderPage() {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}><ProteinListPage /></QueryClientProvider>);
}
describe("ProteinListPage", () => {
  it("renders a protein row", () => {
    renderPage();
    expect(screen.getByText("P12345")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify fail**
Run: `cd frontend && pnpm exec vitest run src/features/protein-catalog/components/protein-list.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement.**
`protein-columns.tsx`: ag-grid `ColDef[]` for accession (link to `/proteins/{primary_accession}`), entry_name, recommended name (`proteinPrimaryName`), reviewed (Swiss-Prot vs TrEMBL badge via `Badge`), seq_length, organism (link chip to `/organisms/{organism_id}` showing short id; comment: resolves to name in Plan 3).
`protein-list.tsx`: `"use client"`. State: filters (`reviewed?`, `minLength?`, `maxLength?`) + cursor stack for pagination + a jump-box string. Toolbar: a reviewed tri-state/`Switch`, two number inputs (min/max length), and an "Open accession / ID" input that on submit routes to `/proteins/{value}` (the detail page resolves it). Render `DataGrid` with the columns, `loading`, `emptyState`, `onRowClick` → router push to detail. Pagination: a "Load more"/next-cursor control driven by `data.next_cursor` (append or page-forward — keep it simple: a Next button that sets cursor, plus Prev via a cursor stack). Persist filter prefs to localStorage (key `pc-proteins-filters`).
`app/(dashboard)/proteins/page.tsx`: `export default function Page(){ return <ProteinListPage/> }`.

- [ ] **Step 4: Run to verify pass**
Run: `cd frontend && pnpm exec vitest run src/features/protein-catalog/components/protein-list.test.tsx`
Expected: PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/protein-catalog/components/protein-list.tsx frontend/src/features/protein-catalog/components/protein-columns.tsx frontend/src/features/protein-catalog/components/protein-list.test.tsx frontend/src/features/protein-catalog/index.ts "frontend/src/app/(dashboard)/proteins/page.tsx"
git commit -m "feat(frontend): protein list page (DataGrid, filters, cursor pagination, ID jump)"
```

---

### Task 4: Protein detail page (sequence via FASTA + cross-references)

**Files:**
- Create: `frontend/src/features/protein-catalog/components/protein-detail.tsx`
- Create: `frontend/src/app/(dashboard)/proteins/[accession]/page.tsx`
- Modify: `frontend/src/features/protein-catalog/index.ts` (export `ProteinDetailPage`)
- Create test: `frontend/src/features/protein-catalog/components/protein-detail.test.tsx`

**Interfaces:**
- Consumes: `useProtein`, `useProteinFasta` (T2), `SequenceViewer`, `CrossReferenceLinks`, ui primitives.
- Produces: `<ProteinDetailPage accession: string />`.

- [ ] **Step 1: Write the failing component test** — `protein-detail.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("../hooks/use-proteins", () => ({
  useProtein: () => ({ data: { id: "1", primary_accession: "P12345", entry_name: "ALBU_HUMAN", is_reviewed: true, seq_length: 7, seq_mass: 800, organism_id: "o1", gene_id: null, protein_names: { recommended: "Albumin" }, secondary_accessions: [], keywords: ["Signal"], cross_references: [{ database: "pdb", accession: "1AO6", curie: "pdb:1AO6", url: "https://x/1AO6" }], version: 1 }, isLoading: false, isError: false }),
  useProteinFasta: () => ({ data: { header: "sp|P12345|ALBU_HUMAN", sequence: "MAAAKLL" }, isLoading: false, isError: false }),
}));
import { ProteinDetailPage } from "./protein-detail";
describe("ProteinDetailPage", () => {
  it("shows the accession and a cross-reference link", () => {
    render(<ProteinDetailPage accession="P12345" />);
    expect(screen.getByText("P12345")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /1AO6/ })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify fail**
Run: `cd frontend && pnpm exec vitest run src/features/protein-catalog/components/protein-detail.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `protein-detail.tsx`** (`"use client"`): header row (primary_accession as title, `entry_name`, reviewed `Badge` = "Swiss-Prot"/"TrEMBL", external link to `uniprot_url` if present); a metadata `Card` grid (protein names: recommended + alternative + submitted; organism link chip → `/organisms/{organism_id}`; gene link → `/genes/{gene_id}` when set; `proteinExistenceLabel`; entry/sequence versions; keywords as badges; secondary accessions). `SequenceViewer` fed `sequence={fasta.sequence}`, `length={protein.seq_length}`, `mass={protein.seq_mass ?? undefined}`, `accession={protein.primary_accession}` — show a `Skeleton` while `useProteinFasta` is loading and a muted "sequence unavailable" note on FASTA error. `CrossReferenceLinks items={protein.cross_references}`. Handle protein `isLoading` (skeleton) and `isError`/not-found (friendly message). `app/(dashboard)/proteins/[accession]/page.tsx`: read `params`, render `<ProteinDetailPage accession={decodeURIComponent(accession)} />` (Next 16 async params — `await params`).

- [ ] **Step 4: Run to verify pass**
Run: `cd frontend && pnpm exec vitest run src/features/protein-catalog/components/protein-detail.test.tsx`
Expected: PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/protein-catalog/components/protein-detail.tsx frontend/src/features/protein-catalog/components/protein-detail.test.tsx frontend/src/features/protein-catalog/index.ts "frontend/src/app/(dashboard)/proteins/[accession]/page.tsx"
git commit -m "feat(frontend): protein detail page (SequenceViewer via FASTA + cross-references)"
```

---

### Task 5: Gene list page

**Files:**
- Create: `frontend/src/features/protein-catalog/components/gene-list.tsx`, `gene-columns.tsx`
- Create: `frontend/src/app/(dashboard)/genes/page.tsx`
- Modify: `index.ts` (export `GeneListPage`)
- Create test: `frontend/src/features/protein-catalog/components/gene-list.test.tsx`

**Interfaces:**
- Consumes: `useGenes` (T2), `DataGrid`, ui primitives.
- Produces: `<GeneListPage/>` — DataGrid of genes + name/organism filter toolbar + cursor pagination.

- [ ] **Step 1: Write the failing test** — `gene-list.test.tsx` (mirror the protein-list test shape):
```tsx
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../hooks/use-genes", () => ({
  useGenes: () => ({ data: { items: [{ id: "g1", primary_name: "TP53", organism_id: "o1", synonyms: ["P53"], cross_references: [], version: 1 }], next_cursor: null }, isLoading: false, isError: false }),
}));
import { GeneListPage } from "./gene-list";
describe("GeneListPage", () => {
  it("renders a gene row", () => {
    const qc = new QueryClient();
    render(<QueryClientProvider client={qc}><GeneListPage /></QueryClientProvider>);
    expect(screen.getByText("TP53")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && pnpm exec vitest run src/features/protein-catalog/components/gene-list.test.tsx` → FAIL.

- [ ] **Step 3: Implement.** `gene-columns.tsx`: ColDefs for primary_name (link to `/genes/{id}`), synonyms (joined), organism link chip, ncbi/ensembl/hgnc id badges. `gene-list.tsx` (`"use client"`): a debounced `name` search input + organism filter (free text id for now; note Plan 3) + `DataGrid` + cursor pagination (same pattern as proteins) + localStorage prefs (`pc-genes-filters`). `app/(dashboard)/genes/page.tsx` → `<GeneListPage/>`.

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/protein-catalog/components/gene-list.tsx frontend/src/features/protein-catalog/components/gene-columns.tsx frontend/src/features/protein-catalog/components/gene-list.test.tsx frontend/src/features/protein-catalog/index.ts "frontend/src/app/(dashboard)/genes/page.tsx"
git commit -m "feat(frontend): gene list page (DataGrid, name/organism filter, pagination)"
```

---

### Task 6: Gene detail page

**Files:**
- Create: `frontend/src/features/protein-catalog/components/gene-detail.tsx`
- Create: `frontend/src/app/(dashboard)/genes/[id]/page.tsx`
- Modify: `index.ts` (export `GeneDetailPage`)
- Create test: `frontend/src/features/protein-catalog/components/gene-detail.test.tsx`

**Interfaces:**
- Consumes: `useGene` (T2), `CrossReferenceLinks`, ui primitives.
- Produces: `<GeneDetailPage geneId: string />`.

- [ ] **Step 1: Write the failing test** — `gene-detail.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("../hooks/use-genes", () => ({
  useGene: () => ({ data: { id: "g1", primary_name: "TP53", organism_id: "o1", synonyms: ["P53", "LFS1"], ncbi_gene_id: "7157", ncbi_gene_url: "https://x/7157", ensembl_gene_id: null, hgnc_id: "HGNC:11998", cross_references: [], version: 1 }, isLoading: false, isError: false }),
}));
import { GeneDetailPage } from "./gene-detail";
describe("GeneDetailPage", () => {
  it("shows the gene name and a synonym", () => {
    render(<GeneDetailPage geneId="g1" />);
    expect(screen.getByText("TP53")).toBeInTheDocument();
    expect(screen.getByText(/LFS1/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify fail** — `cd frontend && pnpm exec vitest run src/features/protein-catalog/components/gene-detail.test.tsx` → FAIL.

- [ ] **Step 3: Implement `gene-detail.tsx`** (`"use client"`): header (primary_name); metadata Card (synonyms as badges; organism link chip; ncbi/ensembl/hgnc as external links using `ncbi_gene_url`/`ensembl_url` when present, else id text); `CrossReferenceLinks`. Loading skeleton + not-found message. `app/(dashboard)/genes/[id]/page.tsx`: `await params`, render `<GeneDetailPage geneId={id} />`.

- [ ] **Step 4: Run to verify pass** — same command → PASS.

- [ ] **Step 5: Verify + commit**
Run: `cd frontend && pnpm exec tsc --noEmit && pnpm lint`
```bash
git add frontend/src/features/protein-catalog/components/gene-detail.tsx frontend/src/features/protein-catalog/components/gene-detail.test.tsx frontend/src/features/protein-catalog/index.ts "frontend/src/app/(dashboard)/genes/[id]/page.tsx"
git commit -m "feat(frontend): gene detail page (metadata + cross-references)"
```

---

### Task 7: Full green gate + dashboard wiring

**Files:**
- Modify: `frontend/src/app/(dashboard)/page.tsx` (dashboard cards already link to /proteins; ensure /genes is reachable via nav — nav already has it from Plan 0)

- [ ] **Step 1: Smoke the routes** — `cd frontend && (pnpm dev > /tmp/pc-fe.log 2>&1 &) ; sleep 16` then `curl -fsS -o /dev/null -w "proteins=%{http_code}\n" http://localhost:3000/proteins` (expect 200; it will render the client shell even without backend data) and `… /genes`. `pkill -f "next dev"`. (Data requires backend on 8001 + auth; the page shell/empty-state rendering is what we're checking.)

- [ ] **Step 2: Full green gate**
Run: `cd frontend && pnpm lint && pnpm exec tsc --noEmit && pnpm test && pnpm build`
Expected: biome clean (pre-existing data-grid warns OK); tsc clean; all tests pass (Plan-0 20 + new ~6); `next build` succeeds with the new routes (`/proteins`, `/proteins/[accession]`, `/genes`, `/genes/[id]`).

- [ ] **Step 3: Commit (if any wiring changed)**
```bash
git add -A frontend && git commit -m "chore(frontend): protein-catalog green gate (lint/tsc/test/build)"
```

---

## Self-Review

**Spec coverage (frontend spec §6 + §7 + §12 Plan 1):** proteins browse/search/detail → T3/T4; `SequenceViewer` + FASTA → T1 (text mode + parseFasta) + T4; `CrossReferenceLinks` → T4/T6; genes browse/detail → T5/T6; cursor pagination → T3/T5; reference-data read-first (no create/edit UI) → respected. Build order (Protein before Target) honored — this is Plan 1.

**Placeholder scan:** no TBD/TODO; exact hook/DTO/param names from the generated client are inlined; pure helpers + their tests are full; component tests provided per page.

**Type consistency:** `useProtein` narrows the generated `unknown`→`ProteinResponse`; `useProteinFasta` uses the new `responseType:"text"` (T1) + `parseFasta` (T1); filter→param mapping matches `ListProteins…Params`/`ListGenes…Params`; `Protein.protein_names` re-narrowed from the loose generated `{[k]:unknown}`. Gene hooks `useGenes`/`useGene` wrap `useListGenesApiV1GenesGet`/`useGetGeneApiV1GenesGeneIdGet`.

**Known deferrals (intentional, noted in code):** organism shown as id-link until Taxonomy (Plan 3) resolves names; no create/edit UI (admin, later); protein list has no free-text name filter (backend doesn't expose one — accession/ID jump uses resolve).
