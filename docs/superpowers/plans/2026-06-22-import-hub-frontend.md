# Import Hub Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an admin "Import Hub" at `/admin/imports` — list import runs, start an import (3 types), upload an essentiality file, and watch one run with live status polling.

**Architecture:** A new `src/features/import-hub/` feature module mirroring `src/features/workspace-config/` (admin list + detail + dialog). Thin Next.js App-Router pages re-export the feature's components. Data flows through orval-generated react-query hooks wrapped in `hooks/use-imports.ts`. The Start dialog renders one self-contained sub-form per import type; the gene-enrichment sub-form embeds a searchable organism picker (built from `Input` + a filtered list — no combobox primitive exists) and an inline file upload.

**Tech Stack:** Next.js 15 (App Router, client components), React 19, TanStack Query v5 (orval-generated hooks), react-hook-form + zod, radix-based UI primitives in `src/shared/components/ui/`, ag-grid via `DataGrid`, vitest + @testing-library/react, biome.

## Global Constraints

- **Tooling:** run `./node_modules/.bin/tsc --noEmit`, `./node_modules/.bin/biome check`, `./node_modules/.bin/vitest run` from `frontend/`. `pnpm exec` is flaky here — use the direct binaries. `make generate-api` is run from the repo root.
- **Generated names are authoritative:** Task 1 emits the API client. The hook/model names used throughout this plan are derived from the backend route function names (FastAPI operationId → orval) and should match exactly; if Task 1's verification shows any name differs, use the actual generated export.
- **API is snake_case:** `import_type`, `target_key`, `next_cursor`, `upload_ref`, `ncbi_tax_id`, `scientific_name`, `requested_by`, `created_at`, `finished_at`. There is no camelCase variant.
- **Enums (exact):** `ImportType` = `proteome | gene_enrichment | go_ontology`. `ImportStatus` = `queued | running | succeeded | failed | cancelled`. No `failed_validation`.
- **`StartImportBody.params`** is a free-form object (backend `dict[str, Any]`). If the generated `params` type is stricter than `{ [k: string]: unknown }`, cast the composed object: `params as StartImportBody["params"]`.
- **No per-mutation `onError`** — the global `MutationCache.onError → showError` (in `src/shared/providers/query-provider.tsx`) shows the error toast and unwraps `ApiError.detail`. Mutation wrappers add only `onSuccess`.
- **Role gating:** none on the client. Pages under `app/(dashboard)/` are auto-gated to authenticated users by `(dashboard)/layout.tsx` (`useAuthz()`). Admin-only Start/Upload calls return 403 → surfaced by the global toast. Do not fetch the user's role and do not hide buttons.
- **No cancel / no retry** UI anywhere.
- **Test convention:** there is no `renderWithProviders`. Use `render` from `@testing-library/react` and `vi.mock` the feature hook (or the generated module `@/shared/lib/api/imports/imports`); stub `DataGrid` and child dialogs. Mock `next/navigation`'s `useRouter` when a component uses it.
- **Booleans:** no Checkbox UI primitive exists — use a native `<input type="checkbox" {...register(...)} />` (react-hook-form stores it as a boolean).
- **Commit after every task** with a `feat(imports):` / `test(imports):` conventional message. Work stays on branch `feat/import-hub`.

---

## File Structure

```
frontend/src/features/import-hub/
├── components/
│   ├── import-list.tsx                       (Task 9)
│   ├── import-columns.tsx                    (Task 4)
│   ├── import-detail.tsx                     (Task 10)
│   ├── organism-combobox.tsx                 (Task 5)
│   ├── start-import-dialog.tsx               (Task 8)
│   └── param-forms/
│       ├── go-ontology-form.tsx              (Task 6)
│       ├── proteome-form.tsx                 (Task 6)
│       └── gene-enrichment-form.tsx          (Task 7)
├── hooks/
│   └── use-imports.ts                        (Task 3)
├── types/
│   └── index.ts                              (Task 2)
└── index.ts                                  (Task 11)

frontend/src/app/(dashboard)/admin/imports/
├── page.tsx                                  (Task 11)
└── [id]/page.tsx                             (Task 11)

frontend/src/shared/lib/navigation.ts          (Task 11 — modify)
frontend/src/shared/lib/api/imports/imports.ts  (Task 1 — generated)
frontend/openapi.json                           (Task 1 — regenerated)
```

**Dependency order:** types → hooks → columns → organism-combobox → simple forms → gene-enrichment form → dialog → list → detail → wiring. Each task consumes only earlier tasks.

---

## Task 1: Regenerate the API client

**Files:**
- Modify: `frontend/openapi.json`
- Create (generated): `frontend/src/shared/lib/api/imports/imports.ts`, plus import-related types under `frontend/src/shared/lib/api/model/`

**Interfaces:**
- Produces (for all later tasks): hooks `useStartImportApiV1ImportsPost`, `useListImportRunsApiV1ImportsGet`, `useGetImportRunApiV1ImportsImportRunIdGet`, `useUploadEssentialityFileApiV1ImportsUploadsPost`; key getters `getListImportRunsApiV1ImportsGetQueryKey`, `getGetImportRunApiV1ImportsImportRunIdGetQueryKey`; models `ImportRunResponse`, `StartImportBody`, `UploadResponse`, `ImportType`, `ImportStatus`, `PaginatedResponseImportRunResponse`, `BodyUploadEssentialityFileApiV1ImportsUploadsPost`.

- [ ] **Step 1: Run codegen**

Run (from repo root):
```bash
make generate-api
```
Expected: writes `frontend/openapi.json` from `app.openapi()`, then orval emits `src/shared/lib/api/imports/imports.ts` + model files.

- [ ] **Step 2: Verify the four hooks exist**

Run:
```bash
grep -nE "useStartImportApiV1ImportsPost|useListImportRunsApiV1ImportsGet|useGetImportRunApiV1ImportsImportRunIdGet|useUploadEssentialityFileApiV1ImportsUploadsPost" frontend/src/shared/lib/api/imports/imports.ts
```
Expected: all four names present. If any differ, note the actual name and substitute it in later tasks.

- [ ] **Step 3: Verify the models are exported**

Run:
```bash
grep -rnE "ImportRunResponse|StartImportBody|UploadResponse|export const ImportType|export const ImportStatus" frontend/src/shared/lib/api/model/index.ts
```
Expected: `ImportRunResponse`, `StartImportBody`, `UploadResponse` re-exported; `ImportType` and `ImportStatus` are const-object enums with values `proteome|gene_enrichment|go_ontology` and `queued|running|succeeded|failed|cancelled`. Confirm the enum keys equal the lowercase values.

- [ ] **Step 4: Verify the upload op builds FormData**

Run:
```bash
grep -nA18 "uploadEssentialityFileApiV1ImportsUploadsPost = " frontend/src/shared/lib/api/imports/imports.ts
```
Expected: the operation constructs `new FormData()` and `append('file', ...)`, so the mutation variables are `{ data: BodyUploadEssentialityFileApiV1ImportsUploadsPost }` with body `{ file: Blob }` → call as `mutateAsync({ data: { file } })`. If instead the body is passed straight through (no `FormData()`), Task 3's `useUploadEssentiality` must build the `FormData` itself; record which is the case.

- [ ] **Step 5: Type-check the generated client**

Run:
```bash
cd frontend && ./node_modules/.bin/tsc --noEmit
```
Expected: PASS (no errors from the new generated files).

- [ ] **Step 6: Commit**

```bash
git add frontend/openapi.json frontend/src/shared/lib/api/imports frontend/src/shared/lib/api/model
git commit -m "feat(imports): regenerate API client with /imports hooks + models"
```

---

## Task 2: Types & label maps

**Files:**
- Create: `frontend/src/features/import-hub/types/index.ts`
- Test: `frontend/src/features/import-hub/types/index.test.ts`

**Interfaces:**
- Consumes (Task 1): `ImportRunResponse`, `StartImportBody`, `UploadResponse`, `ImportType`, `ImportStatus` from `@/shared/lib/api/model`.
- Produces: type `ImportRun`; `BadgeVariant`; consts `IMPORT_TYPE_LABELS`, `STATUS_VARIANTS`; re-exports `ImportType`, `ImportStatus`, `StartImportBody`, `UploadResponse`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/import-hub/types/index.test.ts
import { describe, expect, it } from "vitest";

import { ImportStatus, ImportType } from "@/shared/lib/api/model";

import { IMPORT_TYPE_LABELS, STATUS_VARIANTS } from "./index";

describe("import-hub type maps", () => {
  it("has a label for every import type", () => {
    for (const t of Object.values(ImportType)) {
      expect(IMPORT_TYPE_LABELS[t]).toBeTruthy();
    }
  });

  it("has a badge variant for every status", () => {
    for (const s of Object.values(ImportStatus)) {
      expect(STATUS_VARIANTS[s]).toBeTruthy();
    }
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/types/index.test.ts`
Expected: FAIL — cannot resolve `./index`.

- [ ] **Step 3: Write the implementation**

```ts
// frontend/src/features/import-hub/types/index.ts
import type { ComponentProps } from "react";

import type { Badge } from "@/shared/components/ui/badge";
import { ImportStatus, ImportType } from "@/shared/lib/api/model";
import type {
  ImportRunResponse,
  StartImportBody,
  UploadResponse,
} from "@/shared/lib/api/model";

/** Narrowed alias — one import run (list row or detail). */
export type ImportRun = ImportRunResponse;

export type { StartImportBody, UploadResponse };
export { ImportStatus, ImportType };

/** Badge variant union, derived from the Badge component's own prop type. */
export type BadgeVariant = NonNullable<ComponentProps<typeof Badge>["variant"]>;

/** Human-readable labels for the 3 import types. */
export const IMPORT_TYPE_LABELS: Record<ImportType, string> = {
  [ImportType.proteome]: "Proteome",
  [ImportType.gene_enrichment]: "Gene enrichment",
  [ImportType.go_ontology]: "GO ontology",
};

/** Badge variant per run status (badge variants: default/secondary/destructive/outline/success/warning/ghost/link). */
export const STATUS_VARIANTS: Record<ImportStatus, BadgeVariant> = {
  [ImportStatus.queued]: "secondary",
  [ImportStatus.running]: "warning",
  [ImportStatus.succeeded]: "success",
  [ImportStatus.failed]: "destructive",
  [ImportStatus.cancelled]: "outline",
};
```

> If `ImportType.proteome` / `ImportStatus.queued` member access fails because the generated enum keys differ from their values, switch the computed keys to string literals (`proteome:`, `queued:`, …) — the `Record<ImportType, …>` / `Record<ImportStatus, …>` typing still enforces completeness.

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/types/index.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/types
git commit -m "feat(imports): import-hub type aliases + label/status maps"
```

---

## Task 3: Data hooks (`use-imports.ts`)

**Files:**
- Create: `frontend/src/features/import-hub/hooks/use-imports.ts`
- Test: `frontend/src/features/import-hub/hooks/use-imports.test.ts`

**Interfaces:**
- Consumes (Task 1): the four generated hooks + `getListImportRunsApiV1ImportsGetQueryKey`; `ImportStatus`.
- Produces: `useImportList(cursor?: string)`, `useImportRun(id: string)`, `useStartImport()`, `useUploadEssentiality()`. The start mutation's variables are `{ data: StartImportBody }`; upload's are `{ data: { file: Blob } }`; upload resolves to `UploadResponse` (`{ upload_ref }`).

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/features/import-hub/hooks/use-imports.test.ts
import { describe, expect, it, vi } from "vitest";

import { getListImportRunsApiV1ImportsGetQueryKey } from "@/shared/lib/api/imports/imports";

const mockInvalidateQueries = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

// biome-ignore lint/suspicious/noExplicitAny: captured callback shapes
let capturedStart: any = {};
// biome-ignore lint/suspicious/noExplicitAny: captured callback shapes
let capturedRun: any = {};

vi.mock("@/shared/lib/api/imports/imports", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/lib/api/imports/imports")>();
  return {
    ...actual,
    // biome-ignore lint/suspicious/noExplicitAny: test stub
    useStartImportApiV1ImportsPost: (options: any) => {
      capturedStart = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
    useUploadEssentialityFileApiV1ImportsUploadsPost: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useListImportRunsApiV1ImportsGet: () => ({ data: undefined, isLoading: false }),
    // biome-ignore lint/suspicious/noExplicitAny: test stub
    useGetImportRunApiV1ImportsImportRunIdGet: (_id: string, options: any) => {
      capturedRun = options;
      return { data: undefined, isLoading: false };
    },
  };
});

vi.mock("@/shared/lib/toast", () => ({ showSuccess: vi.fn() }));

import { useImportRun, useStartImport } from "./use-imports";

describe("useStartImport", () => {
  it("invalidates the list query key on success", () => {
    mockInvalidateQueries.mockClear();
    useStartImport();
    capturedStart.mutation?.onSuccess?.({}, {}, undefined);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: getListImportRunsApiV1ImportsGetQueryKey(),
    });
  });
});

describe("useImportRun polling", () => {
  it("polls every 2s while active and stops on a terminal status", () => {
    useImportRun("run-1");
    const refetch = capturedRun.query?.refetchInterval;
    expect(refetch).toBeDefined();
    expect(refetch({ state: { data: { status: "running" } } })).toBe(2000);
    expect(refetch({ state: { data: { status: "queued" } } })).toBe(2000);
    expect(refetch({ state: { data: { status: "succeeded" } } })).toBe(false);
    expect(refetch({ state: { data: undefined } })).toBe(false);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/hooks/use-imports.test.ts`
Expected: FAIL — cannot resolve `./use-imports`.

- [ ] **Step 3: Write the implementation**

```ts
// frontend/src/features/import-hub/hooks/use-imports.ts
import { useQueryClient } from "@tanstack/react-query";

import {
  getListImportRunsApiV1ImportsGetQueryKey,
  useGetImportRunApiV1ImportsImportRunIdGet,
  useListImportRunsApiV1ImportsGet,
  useStartImportApiV1ImportsPost,
  useUploadEssentialityFileApiV1ImportsUploadsPost,
} from "@/shared/lib/api/imports/imports";
import { ImportStatus } from "@/shared/lib/api/model";
import { showSuccess } from "@/shared/lib/toast";

/** Statuses still in progress — poll while in one of these. */
const ACTIVE_STATUSES: ImportStatus[] = [ImportStatus.queued, ImportStatus.running];

/** List import runs (cursor pagination). No auto-poll — the list has a manual refresh. */
export function useImportList(cursor?: string) {
  return useListImportRunsApiV1ImportsGet({ cursor: cursor ?? undefined });
}

/** Fetch one run; polls every 2s while queued/running, stops on a terminal status. */
export function useImportRun(id: string) {
  return useGetImportRunApiV1ImportsImportRunIdGet(id, {
    query: {
      refetchInterval: (query) => {
        const status = query.state.data?.status;
        return status && ACTIVE_STATUSES.includes(status) ? 2000 : false;
      },
    },
  });
}

/** Start an import; invalidates the list and toasts on success. */
export function useStartImport() {
  const queryClient = useQueryClient();
  return useStartImportApiV1ImportsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListImportRunsApiV1ImportsGetQueryKey(),
        });
        showSuccess("Import started");
      },
    },
  });
}

/** Upload an essentiality file → resolves to { upload_ref }. */
export function useUploadEssentiality() {
  return useUploadEssentialityFileApiV1ImportsUploadsPost({
    mutation: { onSuccess: () => showSuccess("File uploaded") },
  });
}
```

> Task 1 confirmed the generated upload op builds `FormData` internally, so this wrapper returns the raw mutation unchanged (above). Note: orval types the body field `file` as `string` (FastAPI binary quirk), so the **caller** (Task 7) casts its `File` with `as unknown as string` — this hook needs no change.

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/hooks/use-imports.test.ts`
Expected: PASS (both suites).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/hooks
git commit -m "feat(imports): use-imports hooks (list, polled get, start, upload)"
```

---

## Task 4: List columns (`import-columns.tsx`)

**Files:**
- Create: `frontend/src/features/import-hub/components/import-columns.tsx`
- Test: `frontend/src/features/import-hub/components/import-columns.test.tsx`

**Interfaces:**
- Consumes (Task 2): `ImportRun`, `IMPORT_TYPE_LABELS`, `STATUS_VARIANTS`; `Badge`.
- Produces: `importColumnDefs: ColDef<ImportRun>[]`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/import-hub/components/import-columns.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ReactElement } from "react";

import type { ImportRun } from "../types";
import { importColumnDefs } from "./import-columns";

// biome-ignore lint/suspicious/noExplicitAny: cell renderer prop shape
function cellFor(field: string): (p: any) => ReactElement {
  const col = importColumnDefs.find((c) => c.field === field);
  if (!col?.cellRenderer) throw new Error(`no renderer for ${field}`);
  // biome-ignore lint/suspicious/noExplicitAny: ag-grid renderer cast
  return col.cellRenderer as any;
}

const run = {
  id: "r1",
  import_type: "proteome",
  target_key: "UP000001584",
  status: "succeeded",
  progress: {},
  summary: {},
  requested_by: "u1",
  created_at: "2026-06-22T10:00:00Z",
  finished_at: null,
} as unknown as ImportRun;

describe("import columns", () => {
  it("renders the raw status text in the status cell", () => {
    const Status = cellFor("status");
    render(<Status data={run} />);
    expect(screen.getByText("succeeded")).toBeInTheDocument();
  });

  it("renders the human type label in the type cell", () => {
    const Type = cellFor("import_type");
    render(<Type data={run} />);
    expect(screen.getByText("Proteome")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/import-columns.test.tsx`
Expected: FAIL — cannot resolve `./import-columns`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/features/import-hub/components/import-columns.tsx
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";

import { Badge } from "@/shared/components/ui/badge";

import { IMPORT_TYPE_LABELS, STATUS_VARIANTS, type ImportRun } from "../types";

function TargetCell({ data, value }: ICellRendererParams<ImportRun, string>) {
  if (!data) return <span>—</span>;
  return (
    <Link
      href={`/admin/imports/${data.id}`}
      className="font-medium text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value || "—"}
    </Link>
  );
}

function TypeCell({ data }: ICellRendererParams<ImportRun>) {
  if (!data) return <span>—</span>;
  return <Badge variant="secondary">{IMPORT_TYPE_LABELS[data.import_type]}</Badge>;
}

function StatusCell({ data }: ICellRendererParams<ImportRun>) {
  if (!data) return <span>—</span>;
  return <Badge variant={STATUS_VARIANTS[data.status]}>{data.status}</Badge>;
}

function DateCell({ value }: ICellRendererParams<ImportRun, string | null>) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  return <span>{new Date(value).toLocaleString()}</span>;
}

export const importColumnDefs: ColDef<ImportRun>[] = [
  { headerName: "Target", field: "target_key", flex: 1, minWidth: 200, cellRenderer: TargetCell },
  { headerName: "Type", field: "import_type", width: 170, cellRenderer: TypeCell, sortable: false },
  { headerName: "Status", field: "status", width: 130, cellRenderer: StatusCell, sortable: false },
  { headerName: "Created", field: "created_at", width: 190, cellRenderer: DateCell },
  { headerName: "Finished", field: "finished_at", width: 190, cellRenderer: DateCell },
];
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/import-columns.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/components/import-columns.tsx frontend/src/features/import-hub/components/import-columns.test.tsx
git commit -m "feat(imports): import list column defs with status/type badges"
```

---

## Task 5: Organism combobox (`organism-combobox.tsx`)

**Files:**
- Create: `frontend/src/features/import-hub/components/organism-combobox.tsx`
- Test: `frontend/src/features/import-hub/components/organism-combobox.test.tsx`

**Interfaces:**
- Consumes: `useOrganisms` from `@/features/taxonomy/hooks/use-organisms` (signature `useOrganisms({ name }, cursor?)` → `{ data: { items: OrganismResponse[] }, isLoading }`; each item has `id`, `scientific_name`, `ncbi_tax_id?`); `Input`.
- Produces: `OrganismCombobox({ onSelect, placeholder? })` where `onSelect(organismId: string, label: string)`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/import-hub/components/organism-combobox.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useOrganismsMock = vi.fn();
vi.mock("@/features/taxonomy/hooks/use-organisms", () => ({
  useOrganisms: (...args: unknown[]) => useOrganismsMock(...args),
}));

import { OrganismCombobox } from "./organism-combobox";

describe("OrganismCombobox", () => {
  it("lists results and calls onSelect with id + label", () => {
    useOrganismsMock.mockReturnValue({
      data: {
        items: [
          { id: "org-1", scientific_name: "Mycobacterium tuberculosis", ncbi_tax_id: 1773 },
        ],
      },
      isLoading: false,
    });
    const onSelect = vi.fn();
    render(<OrganismCombobox onSelect={onSelect} />);
    fireEvent.focus(screen.getByRole("combobox"));
    fireEvent.click(screen.getByText("Mycobacterium tuberculosis — 1773"));
    expect(onSelect).toHaveBeenCalledWith("org-1", "Mycobacterium tuberculosis — 1773");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/organism-combobox.test.tsx`
Expected: FAIL — cannot resolve `./organism-combobox`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/features/import-hub/components/organism-combobox.tsx
"use client";

import { useRef, useState } from "react";

import { useOrganisms } from "@/features/taxonomy/hooks/use-organisms";
import { Input } from "@/shared/components/ui/input";

interface OrganismComboboxProps {
  onSelect: (organismId: string, label: string) => void;
  placeholder?: string;
}

export function OrganismCombobox({ onSelect, placeholder }: OrganismComboboxProps) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleChange(raw: string) {
    setQuery(raw);
    setOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebounced(raw.trim()), 300);
  }

  const { data, isLoading } = useOrganisms({ name: debounced || undefined });
  const items = data?.items ?? [];

  function pick(id: string, label: string) {
    onSelect(id, label);
    setQuery(label);
    setOpen(false);
  }

  return (
    <div className="relative">
      <Input
        value={query}
        placeholder={placeholder ?? "Search organisms…"}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => setOpen(true)}
        role="combobox"
        aria-expanded={open}
        autoComplete="off"
      />
      {open && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border bg-popover py-1 text-popover-foreground shadow-md">
          {isLoading && <li className="px-3 py-2 text-sm text-muted-foreground">Searching…</li>}
          {!isLoading && items.length === 0 && (
            <li className="px-3 py-2 text-sm text-muted-foreground">No organisms found</li>
          )}
          {items.map((org) => {
            const label = `${org.scientific_name}${org.ncbi_tax_id ? ` — ${org.ncbi_tax_id}` : ""}`;
            return (
              <li key={org.id}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => pick(org.id, label)}
                >
                  {label}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/organism-combobox.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/components/organism-combobox.tsx frontend/src/features/import-hub/components/organism-combobox.test.tsx
git commit -m "feat(imports): searchable organism combobox (Input + filtered list)"
```

---

## Task 6: Simple param forms (go_ontology + proteome)

**Files:**
- Create: `frontend/src/features/import-hub/components/param-forms/go-ontology-form.tsx`
- Create: `frontend/src/features/import-hub/components/param-forms/proteome-form.tsx`
- Test: `frontend/src/features/import-hub/components/param-forms/proteome-form.test.tsx`
- Test: `frontend/src/features/import-hub/components/param-forms/go-ontology-form.test.tsx`

**Interfaces:**
- Consumes (Task 3): `useStartImport` (variables `{ data: StartImportBody }`).
- Produces: `GoOntologyForm({ onSuccess })`, `ProteomeForm({ onSuccess })`. Each owns its `useForm` + submit button and calls `onSuccess()` after a successful start.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/features/import-hub/components/param-forms/proteome-form.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mutateAsync = vi.fn().mockResolvedValue({});
vi.mock("../../hooks/use-imports", () => ({
  useStartImport: () => ({ mutateAsync, isPending: false }),
}));

import { ProteomeForm } from "./proteome-form";

describe("ProteomeForm", () => {
  it("requires a proteome_id before submitting", async () => {
    mutateAsync.mockClear();
    render(<ProteomeForm onSuccess={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    expect(await screen.findByText(/proteome id is required/i)).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("submits composed params and calls onSuccess", async () => {
    mutateAsync.mockClear();
    const onSuccess = vi.fn();
    render(<ProteomeForm onSuccess={onSuccess} />);
    fireEvent.change(screen.getByLabelText(/uniprot proteome id/i), {
      target: { value: "UP000001584" },
    });
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        data: {
          import_type: "proteome",
          params: { proteome_id: "UP000001584", force: false, dry_run: false, limit: null },
        },
      }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });
});
```

```tsx
// frontend/src/features/import-hub/components/param-forms/go-ontology-form.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mutateAsync = vi.fn().mockResolvedValue({});
vi.mock("../../hooks/use-imports", () => ({
  useStartImport: () => ({ mutateAsync, isPending: false }),
}));

import { GoOntologyForm } from "./go-ontology-form";

describe("GoOntologyForm", () => {
  it("submits a go_ontology import with force=false by default", async () => {
    mutateAsync.mockClear();
    const onSuccess = vi.fn();
    render(<GoOntologyForm onSuccess={onSuccess} />);
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        data: { import_type: "go_ontology", params: { force: false } },
      }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/param-forms`
Expected: FAIL — cannot resolve `./proteome-form` / `./go-ontology-form`.

- [ ] **Step 3: Write the implementations**

```tsx
// frontend/src/features/import-hub/components/param-forms/go-ontology-form.tsx
"use client";

import { useForm } from "react-hook-form";

import { Button } from "@/shared/components/ui/button";
import { DialogFooter } from "@/shared/components/ui/dialog";

import { useStartImport } from "../../hooks/use-imports";

export function GoOntologyForm({ onSuccess }: { onSuccess: () => void }) {
  const start = useStartImport();
  const { register, handleSubmit } = useForm<{ force: boolean }>({
    defaultValues: { force: false },
  });

  const onSubmit = async (values: { force: boolean }) => {
    try {
      await start.mutateAsync({
        data: { import_type: "go_ontology", params: { force: values.force } },
      });
      onSuccess();
    } catch {
      // global mutation toast surfaces the error
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div className="grid gap-5 py-4">
        <p className="text-sm text-muted-foreground">
          Imports the Gene Ontology graph. Enable “force” to re-import even when already current.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("force")} /> Force re-import
        </label>
      </div>
      <DialogFooter>
        <Button type="submit" disabled={start.isPending}>
          {start.isPending ? "Starting…" : "Start import"}
        </Button>
      </DialogFooter>
    </form>
  );
}
```

```tsx
// frontend/src/features/import-hub/components/param-forms/proteome-form.tsx
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/shared/components/ui/button";
import { DialogFooter } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

import { useStartImport } from "../../hooks/use-imports";

const schema = z.object({
  proteome_id: z.string().min(1, "Proteome ID is required"),
  force: z.boolean(),
  dry_run: z.boolean(),
  limit: z.string().optional(), // numeric text; coerced on submit
});
type Values = z.infer<typeof schema>;

export function ProteomeForm({ onSuccess }: { onSuccess: () => void }) {
  const start = useStartImport();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { proteome_id: "", force: false, dry_run: false, limit: "" },
  });

  const onSubmit = async (values: Values) => {
    const params = {
      proteome_id: values.proteome_id.trim(),
      force: values.force,
      dry_run: values.dry_run,
      limit: values.limit ? Number(values.limit) : null,
    };
    try {
      await start.mutateAsync({ data: { import_type: "proteome", params } });
      onSuccess();
    } catch {
      // global mutation toast surfaces the error
    }
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <div className="grid gap-5 py-4">
        <div className="grid gap-2">
          <Label htmlFor="proteome_id">UniProt proteome ID</Label>
          <Input id="proteome_id" placeholder="e.g. UP000001584" {...form.register("proteome_id")} />
          {form.formState.errors.proteome_id && (
            <p className="text-xs text-destructive">{form.formState.errors.proteome_id.message}</p>
          )}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="prot_limit">
            Limit <span className="text-muted-foreground font-normal text-xs">(optional)</span>
          </Label>
          <Input id="prot_limit" type="number" min={1} placeholder="All" {...form.register("limit")} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("force")} /> Force re-import
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("dry_run")} /> Dry run (no writes)
        </label>
      </div>
      <DialogFooter>
        <Button type="submit" disabled={start.isPending}>
          {start.isPending ? "Starting…" : "Start import"}
        </Button>
      </DialogFooter>
    </form>
  );
}
```

- [ ] **Step 4: Run them to verify they pass**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/param-forms`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/components/param-forms/go-ontology-form.tsx frontend/src/features/import-hub/components/param-forms/go-ontology-form.test.tsx frontend/src/features/import-hub/components/param-forms/proteome-form.tsx frontend/src/features/import-hub/components/param-forms/proteome-form.test.tsx
git commit -m "feat(imports): go_ontology + proteome param sub-forms"
```

---

## Task 7: Gene-enrichment param form (`gene-enrichment-form.tsx`)

**Files:**
- Create: `frontend/src/features/import-hub/components/param-forms/gene-enrichment-form.tsx`
- Test: `frontend/src/features/import-hub/components/param-forms/gene-enrichment-form.test.tsx`

**Interfaces:**
- Consumes: `OrganismCombobox` (Task 5); `useStartImport`, `useUploadEssentiality` (Task 3); `Collapsible/CollapsibleTrigger/CollapsibleContent`.
- Produces: `GeneEnrichmentForm({ onSuccess })`. Composes `params` with exactly one of `organism_id` / `tax_id`, optional `essentiality_upload_ref`, optional `gff_url` / `essentiality_url`, `force`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/import-hub/components/param-forms/gene-enrichment-form.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const startMutate = vi.fn().mockResolvedValue({});
const uploadMutate = vi.fn().mockResolvedValue({ upload_ref: "up-123" });
vi.mock("../../hooks/use-imports", () => ({
  useStartImport: () => ({ mutateAsync: startMutate, isPending: false }),
  useUploadEssentiality: () => ({ mutateAsync: uploadMutate, isPending: false }),
}));
vi.mock("../organism-combobox", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  OrganismCombobox: ({ onSelect }: any) => (
    <button type="button" onClick={() => onSelect("org-7", "M. tb")}>
      pick-org
    </button>
  ),
}));

import { GeneEnrichmentForm } from "./gene-enrichment-form";

describe("GeneEnrichmentForm", () => {
  it("rejects submit when neither organism nor tax_id is provided", async () => {
    startMutate.mockClear();
    render(<GeneEnrichmentForm onSuccess={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    expect(await screen.findByText(/exactly one/i)).toBeInTheDocument();
    expect(startMutate).not.toHaveBeenCalled();
  });

  it("submits the tax_id path with a coerced number", async () => {
    startMutate.mockClear();
    const onSuccess = vi.fn();
    render(<GeneEnrichmentForm onSuccess={onSuccess} />);
    fireEvent.change(screen.getByLabelText(/ncbi tax id/i), { target: { value: "83332" } });
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    await waitFor(() =>
      expect(startMutate).toHaveBeenCalledWith({
        data: { import_type: "gene_enrichment", params: { force: false, tax_id: 83332 } },
      }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("uploads a file and shows the uploaded marker", async () => {
    uploadMutate.mockClear();
    render(<GeneEnrichmentForm onSuccess={() => {}} />);
    const file = new File(["x"], "ess.tsv", { type: "text/tab-separated-values" });
    fireEvent.change(screen.getByLabelText(/essentiality file/i), { target: { files: [file] } });
    await waitFor(() => expect(uploadMutate).toHaveBeenCalledWith({ data: { file } }));
    expect(await screen.findByText(/uploaded ✓/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/param-forms/gene-enrichment-form.test.tsx`
Expected: FAIL — cannot resolve `./gene-enrichment-form`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/features/import-hub/components/param-forms/gene-enrichment-form.tsx
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/shared/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/components/ui/collapsible";
import { DialogFooter } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

import { useStartImport, useUploadEssentiality } from "../../hooks/use-imports";
import { OrganismCombobox } from "../organism-combobox";

const schema = z
  .object({
    organism_id: z.string().optional(),
    tax_id: z.string().optional(), // numeric text; coerced on submit
    gff_url: z.string().url("Enter a valid URL").optional().or(z.literal("")),
    essentiality_url: z.string().url("Enter a valid URL").optional().or(z.literal("")),
    essentiality_upload_ref: z.string().optional(),
    force: z.boolean(),
  })
  .refine((v) => Boolean(v.organism_id) !== Boolean(v.tax_id), {
    message: "Pick an organism OR enter a tax_id — exactly one.",
    path: ["organism_id"],
  });
type Values = z.infer<typeof schema>;

export function GeneEnrichmentForm({ onSuccess }: { onSuccess: () => void }) {
  const start = useStartImport();
  const upload = useUploadEssentiality();
  const [uploadName, setUploadName] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      organism_id: "",
      tax_id: "",
      gff_url: "",
      essentiality_url: "",
      essentiality_upload_ref: "",
      force: false,
    },
  });

  async function handleFile(file: File | undefined) {
    if (!file) return;
    // orval types the multipart body field `file` as `string` (FastAPI binary
    // quirk); the File works at runtime via FormData — cast to satisfy tsc.
    const res = await upload.mutateAsync({ data: { file: file as unknown as string } });
    form.setValue("essentiality_upload_ref", res.upload_ref);
    setUploadName(file.name);
  }

  const onSubmit = async (values: Values) => {
    const params: Record<string, unknown> = { force: values.force };
    if (values.organism_id) params.organism_id = values.organism_id;
    if (values.tax_id) params.tax_id = Number(values.tax_id);
    if (values.gff_url) params.gff_url = values.gff_url;
    if (values.essentiality_url) params.essentiality_url = values.essentiality_url;
    if (values.essentiality_upload_ref) {
      params.essentiality_upload_ref = values.essentiality_upload_ref;
    }
    try {
      await start.mutateAsync({ data: { import_type: "gene_enrichment", params } });
      onSuccess();
    } catch {
      // global mutation toast surfaces the error
    }
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <div className="grid gap-5 py-4">
        {/* Organism picker */}
        <div className="grid gap-2">
          <Label>Organism</Label>
          <Controller
            control={form.control}
            name="organism_id"
            render={({ field }) => <OrganismCombobox onSelect={(id) => field.onChange(id)} />}
          />
          {form.formState.errors.organism_id && (
            <p className="text-xs text-destructive">{form.formState.errors.organism_id.message}</p>
          )}
        </div>

        {/* Manual tax_id fallback */}
        <div className="grid gap-2">
          <Label htmlFor="tax_id">
            …or NCBI tax ID{" "}
            <span className="text-muted-foreground font-normal text-xs">(if not in the list)</span>
          </Label>
          <Input id="tax_id" type="number" min={1} placeholder="e.g. 83332" {...form.register("tax_id")} />
        </div>

        {/* Inline essentiality upload */}
        <div className="grid gap-2">
          <Label htmlFor="essentiality_file">
            Essentiality file{" "}
            <span className="text-muted-foreground font-normal text-xs">(.xlsx / .tsv, optional)</span>
          </Label>
          <Input
            id="essentiality_file"
            type="file"
            accept=".xlsx,.tsv,.txt"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          {upload.isPending && <p className="text-xs text-muted-foreground">Uploading…</p>}
          {uploadName && !upload.isPending && (
            <p className="text-xs text-green-600">Uploaded ✓ {uploadName}</p>
          )}
        </div>

        {/* Force */}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("force")} /> Force re-import
        </label>

        {/* Advanced URLs */}
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button type="button" variant="ghost" size="sm" className="w-fit px-0 text-muted-foreground">
              Advanced
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="grid gap-4 pt-3">
            <div className="grid gap-2">
              <Label htmlFor="gff_url">GFF URL</Label>
              <Input id="gff_url" placeholder="https://…/annotations.gff" {...form.register("gff_url")} />
              {form.formState.errors.gff_url && (
                <p className="text-xs text-destructive">{form.formState.errors.gff_url.message}</p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="essentiality_url">Essentiality URL</Label>
              <Input
                id="essentiality_url"
                placeholder="https://…/essentiality.tsv"
                {...form.register("essentiality_url")}
              />
              {form.formState.errors.essentiality_url && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.essentiality_url.message}
                </p>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      <DialogFooter>
        <Button type="submit" disabled={start.isPending || upload.isPending}>
          {start.isPending ? "Starting…" : "Start import"}
        </Button>
      </DialogFooter>
    </form>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/param-forms/gene-enrichment-form.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/components/param-forms/gene-enrichment-form.tsx frontend/src/features/import-hub/components/param-forms/gene-enrichment-form.test.tsx
git commit -m "feat(imports): gene-enrichment form (organism picker, inline upload, advanced URLs)"
```

---

## Task 8: Start-import dialog (`start-import-dialog.tsx`)

**Files:**
- Create: `frontend/src/features/import-hub/components/start-import-dialog.tsx`
- Test: `frontend/src/features/import-hub/components/start-import-dialog.test.tsx`

**Interfaces:**
- Consumes: `GoOntologyForm`, `ProteomeForm` (Task 6), `GeneEnrichmentForm` (Task 7); `IMPORT_TYPE_LABELS` (Task 2); `ImportType`; Dialog + Select primitives.
- Produces: `StartImportDialog({ open, onOpenChange })`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/import-hub/components/start-import-dialog.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("./param-forms/go-ontology-form", () => ({
  GoOntologyForm: () => <div>go-form</div>,
}));
vi.mock("./param-forms/proteome-form", () => ({
  ProteomeForm: () => <div>proteome-form</div>,
}));
vi.mock("./param-forms/gene-enrichment-form", () => ({
  GeneEnrichmentForm: () => <div>gene-form</div>,
}));

import { StartImportDialog } from "./start-import-dialog";

describe("StartImportDialog", () => {
  it("renders the title and the go_ontology form by default when open", () => {
    render(<StartImportDialog open onOpenChange={() => {}} />);
    expect(screen.getByRole("heading", { name: /new import/i })).toBeInTheDocument();
    expect(screen.getByText("go-form")).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    render(<StartImportDialog open={false} onOpenChange={() => {}} />);
    expect(screen.queryByText("go-form")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/start-import-dialog.test.tsx`
Expected: FAIL — cannot resolve `./start-import-dialog`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/features/import-hub/components/start-import-dialog.tsx
"use client";

import { useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { ImportType } from "@/shared/lib/api/model";

import { IMPORT_TYPE_LABELS } from "../types";
import { GeneEnrichmentForm } from "./param-forms/gene-enrichment-form";
import { GoOntologyForm } from "./param-forms/go-ontology-form";
import { ProteomeForm } from "./param-forms/proteome-form";

const IMPORT_TYPE_VALUES = Object.values(ImportType);

interface StartImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function StartImportDialog({ open, onOpenChange }: StartImportDialogProps) {
  const [importType, setImportType] = useState<ImportType>(ImportType.go_ontology);
  const close = () => onOpenChange(false);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New import</DialogTitle>
          <DialogDescription>Choose an import type and provide its parameters.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-2">
          <Label htmlFor="import_type">Import type</Label>
          <Select value={importType} onValueChange={(v) => setImportType(v as ImportType)}>
            <SelectTrigger id="import_type" aria-label="Import type">
              <SelectValue placeholder="Select a type" />
            </SelectTrigger>
            <SelectContent>
              {IMPORT_TYPE_VALUES.map((t) => (
                <SelectItem key={t} value={t}>
                  {IMPORT_TYPE_LABELS[t]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {importType === ImportType.go_ontology && <GoOntologyForm key="go" onSuccess={close} />}
        {importType === ImportType.proteome && <ProteomeForm key="prot" onSuccess={close} />}
        {importType === ImportType.gene_enrichment && (
          <GeneEnrichmentForm key="gene" onSuccess={close} />
        )}
      </DialogContent>
    </Dialog>
  );
}
```

> The form shown is driven by internal state set from a radix `Select`; radix Select is impractical to drive in jsdom, so the unit test covers the default render. Type-switch behavior is covered by manual verification (it is a single `useState` + conditional render).

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/start-import-dialog.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/components/start-import-dialog.tsx frontend/src/features/import-hub/components/start-import-dialog.test.tsx
git commit -m "feat(imports): start-import dialog with per-type param sub-forms"
```

---

## Task 9: Import list page (`import-list.tsx`)

**Files:**
- Create: `frontend/src/features/import-hub/components/import-list.tsx`
- Test: `frontend/src/features/import-hub/components/import-list.test.tsx`

**Interfaces:**
- Consumes: `useImportList` (Task 3), `importColumnDefs` (Task 4), `StartImportDialog` (Task 8), `DataGrid`, `Button`.
- Produces: `ImportListPage()`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/import-hub/components/import-list.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("../hooks/use-imports", () => ({
  useImportList: () => ({
    data: {
      items: [
        { id: "r1", target_key: "UP000001584", import_type: "proteome", status: "succeeded" },
        { id: "r2", target_key: "83332", import_type: "gene_enrichment", status: "running" },
      ],
      next_cursor: null,
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/shared/components/data-grid/data-grid", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  DataGrid: ({ rowData }: any) => (
    <div data-testid="grid">
      {/* biome-ignore lint/suspicious/noExplicitAny: test stub */}
      {rowData?.map((r: any) => (
        <div key={r.id}>{r.target_key}</div>
      ))}
    </div>
  ),
}));

vi.mock("./start-import-dialog", () => ({ StartImportDialog: () => null }));

import { ImportListPage } from "./import-list";

describe("ImportListPage", () => {
  it("renders run target keys into the grid", () => {
    render(<ImportListPage />);
    expect(screen.getByText("UP000001584")).toBeInTheDocument();
    expect(screen.getByText("83332")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/import-list.test.tsx`
Expected: FAIL — cannot resolve `./import-list`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/features/import-hub/components/import-list.tsx
"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";

import { useImportList } from "../hooks/use-imports";
import { importColumnDefs } from "./import-columns";
import { StartImportDialog } from "./start-import-dialog";

function ImportsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Upload className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No imports yet</p>
      <p className="text-xs">Start your first import with the "New import" button above.</p>
    </div>
  );
}

export function ImportListPage() {
  const router = useRouter();
  const [cursorStack, setCursorStack] = useState<(string | undefined)[]>([undefined]);
  const currentCursor = cursorStack[cursorStack.length - 1];
  const { data, isLoading, isError, refetch } = useImportList(currentCursor);

  const runs = useMemo(() => {
    if (!data?.items) return undefined;
    // biome-ignore lint/suspicious/noExplicitAny: narrowing cast at feature boundary
    return data.items as any[];
  }, [data]);

  const [newOpen, setNewOpen] = useState(false);

  function goNext() {
    const nextCursor = data?.next_cursor;
    if (!nextCursor) return;
    setCursorStack((prev) => [...prev, String(nextCursor)]);
  }
  function goPrev() {
    if (cursorStack.length <= 1) return;
    setCursorStack((prev) => prev.slice(0, -1));
  }

  const hasNext = !!data?.next_cursor;
  const hasPrev = cursorStack.length > 1;

  if (isError) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Imports</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load imports. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Imports</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Run and monitor data imports</p>
        </div>
        <div className="flex items-center gap-3">
          <Button type="button" variant="outline" size="sm" onClick={() => refetch()}>
            Refresh
          </Button>
          <Button type="button" size="sm" onClick={() => setNewOpen(true)}>
            New import
          </Button>
        </div>
      </div>

      <DataGrid
        rowData={runs}
        columnDefs={importColumnDefs}
        loading={isLoading}
        height="calc(100vh - 240px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(run) => router.push(`/admin/imports/${run.id}`)}
        emptyState={<ImportsEmptyState />}
      />

      {(hasPrev || hasNext) && (
        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="outline" size="sm" onClick={goPrev} disabled={!hasPrev}>
            Previous
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={goNext} disabled={!hasNext}>
            Next
          </Button>
        </div>
      )}

      <StartImportDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/import-list.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/components/import-list.tsx frontend/src/features/import-hub/components/import-list.test.tsx
git commit -m "feat(imports): import list page (grid, pagination, refresh, new-import)"
```

---

## Task 10: Import detail page (`import-detail.tsx`)

**Files:**
- Create: `frontend/src/features/import-hub/components/import-detail.tsx`
- Test: `frontend/src/features/import-hub/components/import-detail.test.tsx`

**Interfaces:**
- Consumes: `useImportRun` (Task 3), `IMPORT_TYPE_LABELS`, `STATUS_VARIANTS` (Task 2), `Badge`.
- Produces: `ImportDetailPage({ importRunId: string })`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/import-hub/components/import-detail.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useImportRunMock = vi.fn();
vi.mock("../hooks/use-imports", () => ({ useImportRun: () => useImportRunMock() }));

import { ImportDetailPage } from "./import-detail";

const base = {
  id: "r1",
  import_type: "proteome",
  target_key: "UP000001584",
  phase: null,
  progress: { processed: 0, total: 0 },
  summary: {},
  error: null,
};

describe("ImportDetailPage", () => {
  it("renders the summary on success", () => {
    useImportRunMock.mockReturnValue({
      data: { ...base, status: "succeeded", summary: { proteins: 4008, genes: 3906 } },
      isLoading: false,
      isError: false,
    });
    render(<ImportDetailPage importRunId="r1" />);
    expect(screen.getByText("proteins")).toBeInTheDocument();
    expect(screen.getByText("4008")).toBeInTheDocument();
  });

  it("renders the error on failure", () => {
    useImportRunMock.mockReturnValue({
      data: { ...base, status: "failed", error: "GFF fetch failed" },
      isLoading: false,
      isError: false,
    });
    render(<ImportDetailPage importRunId="r1" />);
    expect(screen.getByText(/gff fetch failed/i)).toBeInTheDocument();
  });

  it("shows a working indicator while active with no total", () => {
    useImportRunMock.mockReturnValue({
      data: { ...base, status: "running" },
      isLoading: false,
      isError: false,
    });
    render(<ImportDetailPage importRunId="r1" />);
    expect(screen.getByText(/working/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/import-detail.test.tsx`
Expected: FAIL — cannot resolve `./import-detail`.

- [ ] **Step 3: Write the implementation**

```tsx
// frontend/src/features/import-hub/components/import-detail.tsx
"use client";

import { Badge } from "@/shared/components/ui/badge";

import { useImportRun } from "../hooks/use-imports";
import { IMPORT_TYPE_LABELS, STATUS_VARIANTS } from "../types";

function asNumber(v: unknown): number {
  return typeof v === "number" ? v : Number(v ?? 0) || 0;
}

export function ImportDetailPage({ importRunId }: { importRunId: string }) {
  const { data, isLoading, isError } = useImportRun(importRunId);

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (isError || !data) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        Failed to load this import run.
      </div>
    );
  }

  const progress = (data.progress as Record<string, unknown>) ?? {};
  const processed = asNumber(progress.processed);
  const total = asNumber(progress.total);
  const isActive = data.status === "queued" || data.status === "running";
  const summaryEntries = Object.entries((data.summary as Record<string, unknown>) ?? {});

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {IMPORT_TYPE_LABELS[data.import_type]}
          </h1>
          <p className="text-sm text-muted-foreground">{data.target_key}</p>
        </div>
        <Badge variant={STATUS_VARIANTS[data.status]}>{data.status}</Badge>
      </div>

      {/* Phase + progress */}
      <div className="flex flex-col gap-2">
        {data.phase && (
          <p className="text-sm">
            Phase: <span className="font-medium">{data.phase}</span>
          </p>
        )}
        {total > 0 ? (
          <div className="flex flex-col gap-1">
            <div className="h-2 w-full overflow-hidden rounded bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${Math.min(100, Math.round((processed / total) * 100))}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {processed} / {total}
            </p>
          </div>
        ) : (
          isActive && <p className="text-sm text-muted-foreground animate-pulse">Working…</p>
        )}
      </div>

      {/* Error */}
      {data.error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {data.error}
        </div>
      )}

      {/* Summary */}
      {summaryEntries.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">Summary</h2>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
            {summaryEntries.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="font-mono">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/components/import-detail.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/components/import-detail.tsx frontend/src/features/import-hub/components/import-detail.test.tsx
git commit -m "feat(imports): import detail with live polling, progress, summary, error"
```

---

## Task 11: Wiring — barrel, pages, nav, final gate

**Files:**
- Create: `frontend/src/features/import-hub/index.ts`
- Create: `frontend/src/app/(dashboard)/admin/imports/page.tsx`
- Create: `frontend/src/app/(dashboard)/admin/imports/[id]/page.tsx`
- Modify: `frontend/src/shared/lib/navigation.ts`
- Test: `frontend/src/shared/lib/navigation.test.ts`

**Interfaces:**
- Consumes: `ImportListPage` (Task 9), `ImportDetailPage` (Task 10), `StartImportDialog` (Task 8); types/maps (Task 2).
- Produces: feature barrel + two App-Router pages + a nav entry.

- [ ] **Step 1: Write the failing nav test**

```ts
// frontend/src/shared/lib/navigation.test.ts
import { describe, expect, it } from "vitest";

import { navigation } from "./navigation";

describe("navigation", () => {
  it("includes an Imports entry under Administration", () => {
    const admin = navigation.groups.find((g) => g.label === "Administration");
    expect(admin?.items.some((i) => i.href === "/admin/imports")).toBe(true);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/shared/lib/navigation.test.ts`
Expected: FAIL — no `/admin/imports` item.

- [ ] **Step 3: Add the nav entry**

In `frontend/src/shared/lib/navigation.ts`, add `Upload` to the lucide import block:
```ts
import {
  Boxes,
  Building2,
  Dna,
  FlaskConical,
  Layers,
  LayoutDashboard,
  Microscope,
  Network,
  ScrollText,
  Upload,
} from "lucide-react";
```
Then add the item to the **Administration** group's `items` array (after Organizations):
```ts
    {
      label: "Administration",
      items: [
        { title: "Organizations", href: "/admin/organizations", icon: Building2 },
        { title: "Imports", href: "/admin/imports", icon: Upload },
        { title: "Audit", href: "/admin/audit", icon: ScrollText },
      ],
    },
```

- [ ] **Step 4: Run the nav test to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/shared/lib/navigation.test.ts`
Expected: PASS.

- [ ] **Step 5: Create the barrel + pages**

```ts
// frontend/src/features/import-hub/index.ts
export type { BadgeVariant, ImportRun } from "./types";
export { IMPORT_TYPE_LABELS, STATUS_VARIANTS } from "./types";

export { ImportDetailPage } from "./components/import-detail";
export { ImportListPage } from "./components/import-list";
export { StartImportDialog } from "./components/start-import-dialog";
```

```tsx
// frontend/src/app/(dashboard)/admin/imports/page.tsx
import { ImportListPage } from "@/features/import-hub";

export default function Page() {
  return <ImportListPage />;
}
```

```tsx
// frontend/src/app/(dashboard)/admin/imports/[id]/page.tsx
import { ImportDetailPage } from "@/features/import-hub";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ImportDetailPage importRunId={id} />;
}
```

> The `(dashboard)` segment has literal parentheses — quote the paths in shell commands: `git add 'frontend/src/app/(dashboard)/admin/imports'`.

- [ ] **Step 6: Full gate — tsc, biome, vitest**

Run:
```bash
cd frontend && ./node_modules/.bin/tsc --noEmit
```
Expected: PASS.

Run:
```bash
cd frontend && ./node_modules/.bin/biome check src/features/import-hub 'src/app/(dashboard)/admin/imports' src/shared/lib/navigation.ts src/shared/lib/navigation.test.ts
```
Expected: PASS. If biome reports fixable issues, run the same command with `--write` and re-run.

Run:
```bash
cd frontend && ./node_modules/.bin/vitest run src/features/import-hub src/shared/lib/navigation.test.ts
```
Expected: PASS — all import-hub suites + nav green.

- [ ] **Step 7: Commit**

```bash
git add 'frontend/src/app/(dashboard)/admin/imports' frontend/src/features/import-hub/index.ts frontend/src/shared/lib/navigation.ts frontend/src/shared/lib/navigation.test.ts
git commit -m "feat(imports): wire import-hub pages, barrel, and nav entry"
```

---

## Manual verification (after all tasks)

With Postgres `:5433`, Valkey `:6380`, backend (`:8001`), frontend, **and the arq worker** running
(`uv run --directory backend arq protcellar.infrastructure.ingestion.worker.WorkerSettings`):

1. Visit `/admin/imports` → empty state or existing runs; "Imports" appears in the sidebar Administration group.
2. New import → **GO ontology** → Start → row appears `queued`; open it → status advances `queued → running → succeeded` without manual refresh (polling), summary renders.
3. New import → **Proteome** → `UP000001584` → Start → detail shows progress bar once `total > 0`.
4. New import → **Gene enrichment** → search organism in the picker (or type tax_id `83332`); attach a `.xlsx`/`.tsv` essentiality file → "Uploaded ✓"; expand **Advanced** to confirm the URL fields; Start.
5. Confirm a validation error toast on a bad upload (`422`) and that the form blocks submit when neither organism nor tax_id is set.

---

## Self-Review

**Spec coverage** (against `2026-06-22-import-hub-frontend-design.md`):
- List (paginated, status/type/target/time) → Tasks 4, 9. ✓
- Start import, 3 types, type-swapped sub-forms → Tasks 6, 7, 8. ✓
- Inline essentiality upload → `upload_ref` → Task 7 (+ hook Task 3). ✓
- Detail with live polling, phase, progress, summary, error → Tasks 3, 10. ✓
- Organism picker + manual tax_id (decision #1) → Tasks 5, 7. ✓
- Collapsible Advanced URL fields (decision #2) → Task 7. ✓
- Show-and-403 role handling (decision #3) → Global Constraints; no code. ✓
- Total-aware progress (decision #4) → Task 10. ✓
- Generic summary render (decision #5) → Task 10. ✓
- Detail-only polling (decision #6) → Task 3 (`useImportList` no poll; `useImportRun` polls). ✓
- Nav + routes → Task 11. ✓
- First step = regenerate client → Task 1. ✓

**Placeholder scan:** no TBD/TODO; every code step contains complete code; every test step contains real assertions. The only conditional notes are codegen-derived (upload FormData shape, enum key casing) with explicit both-branch instructions. ✓

**Type consistency:** hook names identical across Tasks 1/3 (`useStartImportApiV1ImportsPost`, `getListImportRunsApiV1ImportsGetQueryKey`, etc.); wrapper names identical across Tasks 3/6/7/9/10 (`useImportList`, `useImportRun`, `useStartImport`, `useUploadEssentiality`); `ImportRun`/`IMPORT_TYPE_LABELS`/`STATUS_VARIANTS` from Task 2 used consistently in 4/9/10; form prop `{ onSuccess }` uniform across 6/7/8; `OrganismCombobox` prop `onSelect(id, label)` consistent between 5 and 7; start variables `{ data: { import_type, params } }` and upload variables `{ data: { file } }` consistent between 3 and 6/7. ✓
