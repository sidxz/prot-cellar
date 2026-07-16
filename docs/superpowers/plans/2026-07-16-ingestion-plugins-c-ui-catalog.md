# Ingestion Plugins — Plan C: UI Revamp Tier 1 (Catalog + Descriptor Form + Dry-Run Preview)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Depends on:** Plan A (the `generationMethodBadgeVariant` helper + blue `info` badge) and Plan B (`GET /api/v1/plugins`, `POST /api/v1/plugins/{id}/runs`, and the regenerated orval client). Do not start Plan C until Plan B's Task 7 has run `make generate-api` so `frontend/src/shared/lib/api/plugins/plugins.ts` and the plugin model types exist.

**Goal:** Build the three frontend surfaces the current Import Hub UI structurally cannot express — a **plugin catalog** (cards from `GET /plugins`, filterable, source-kind chip in the provenance color language), a **descriptor-driven run form** rendered from the manifest's `ParamField`s, and a **dry-run Preview** ("would create N / update M / skip K / fail J") before committing — while reusing the existing run monitor / history / live progress bar wholesale.

**Architecture:** A new `plugins/` area inside the existing `import-hub` feature (co-located to reuse `useImportRun`'s 2s polling, the runs list, and the local `OrganismCombobox`). Thin hooks wrap the generated plugins client. The run form is a controlled component that renders one input per `ParamField.type`; the backend re-validates against the manifest (422), so the FE form stays simple. Preview and commit both start a plugin `ImportRun` (`dry_run: true` then `false`) reusing the file `upload_ref`; the preview polls the run and shows its summary. A plugin run and a legacy import run are both `ImportRun`s, so the existing monitor renders both — the catalog is **additive**: it coexists with the legacy "New import" dialog until the 3 built-in importers are migrated to manifests (out of scope here).

**Visual execution:** this plan fixes *scope, IA, and behavior* — not pixels. Apply the `frontend-design` skill when building the catalog cards and run panel for spacing, hierarchy, and states.

**Tech Stack:** Next.js App Router, React, TanStack Query (orval-generated hooks), Radix/cva design system (`@/shared/components/ui/*`), vitest + @testing-library/react (no MSW — mock the feature hooks).

## Global Constraints

- **Frontend tooling: direct binaries** — from `frontend/`: `./node_modules/.bin/vitest run <path>`, `./node_modules/.bin/tsc --noEmit`, `./node_modules/.bin/biome check src/` (pnpm exec is flaky here). There is no `typecheck` npm script — call `tsc` via the bin.
- **Generated client is source of truth** — the exact generated hook/type names come from `frontend/src/shared/lib/api/plugins/plugins.ts` (produced by Plan B's `make generate-api`). This plan uses the orval naming convention (`useListPluginsApiV1PluginsGet`, `useStartPluginRunApiV1PluginsPluginIdRunsPost`); **confirm the exact identifiers in that file before importing** and adjust if they differ. Never hand-edit files under `src/shared/lib/api/` (orval-generated, biome-ignored).
- **Test pattern: no MSW** — mock the feature hooks (`vi.mock("../hooks/use-plugins")`) or the generated module, returning stub `{ data, isLoading, isError }` / `{ mutateAsync: vi.fn(), isPending: false }`. Colocate `.test.tsx` per component. `vitest.setup.ts` already polyfills `scrollIntoView`/`ResizeObserver`/`matchMedia` for Radix + cmdk.
- **Design-system primitives available** (`@/shared/components/ui/*`): `Card` (+ `CardHeader/Title/Description/Content/Footer`), `Badge` (variants `default|secondary|destructive|outline|success|warning|ghost|link|info` — `info` added in Plan A), `Dialog`, `Sheet`, `Button` (sizes incl. `sm`/`xs`), `Select`, `Input`, `Label`, `Tooltip`. **No** Checkbox, Progress, or file-upload primitive — use a plain `<input type="checkbox">` and `<Input type="file">` (as the existing forms do). The organism picker is the feature-local `OrganismCombobox` (`../components/organism-combobox`).
- **Reuse, don't rebuild** — the run monitor (`import-detail.tsx`), runs list (`import-list.tsx`), and 2s polling (`useImportRun`) already work and stay. Plugin runs flow through them unchanged.
- **Provenance color language** — the catalog's source-kind chip reuses Plan A's `generationMethodBadgeVariant` so an AI plugin's chip is the same blue as the data it will produce.

---

## File Structure

**Create (frontend):**
- `frontend/src/features/import-hub/plugins/use-plugins.ts` — `usePluginCatalog`, `useStartPluginRun`, `usePluginPreview`.
- `frontend/src/features/import-hub/plugins/plugin-param-form.tsx` — `PluginParamForm` (descriptor-driven).
- `frontend/src/features/import-hub/plugins/plugin-catalog.tsx` — `PluginCatalogPage` + `PluginCard`.
- `frontend/src/features/import-hub/plugins/plugin-run-panel.tsx` — `PluginRunPanel` (form + Preview + Run).
- `frontend/src/app/(dashboard)/admin/plugins/page.tsx` — route page.

**Create (tests):**
- `frontend/src/features/import-hub/plugins/use-plugins.test.ts`
- `frontend/src/features/import-hub/plugins/plugin-param-form.test.tsx`
- `frontend/src/features/import-hub/plugins/plugin-catalog.test.tsx`
- `frontend/src/features/import-hub/plugins/plugin-run-panel.test.tsx`

**Modify:**
- `frontend/src/features/import-hub/index.ts` — export `PluginCatalogPage`.
- (Optional, Tier 2 polish) `frontend/src/features/import-hub/components/import-detail.tsx` — compact created/updated/skipped/failed counts row.
- (Nav) the admin sidebar/nav where the "Imports" link lives — add a "Plugins" link.

---

## Task 1: Thin plugin hooks

**Files:**
- Create: `frontend/src/features/import-hub/plugins/use-plugins.ts`
- Test: `frontend/src/features/import-hub/plugins/use-plugins.test.ts`

**Interfaces:**
- Consumes: generated `useListPluginsApiV1PluginsGet`, `useStartPluginRunApiV1PluginsPluginIdRunsPost`, `useGetImportRunApiV1ImportsImportRunIdGet` (all from `@/shared/lib/api/**`); `ImportStatus` model.
- Produces:
  - `usePluginCatalog()` → query of `PluginManifestResponse[]`.
  - `useStartPluginRun()` → mutation; `mutateAsync({ pluginId, data: { params, dry_run } })` → `ImportRunResponse`.
  - `usePluginPreview(runId: string | null)` → polls the run every 2s while active; disabled when `runId` is null.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/import-hub/plugins/use-plugins.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/plugins/plugins", () => ({
  useListPluginsApiV1PluginsGet: vi.fn(() => ({ data: [], isLoading: false })),
  useStartPluginRunApiV1PluginsPluginIdRunsPost: vi.fn((opts?: unknown) => ({
    mutateAsync: vi.fn(),
    isPending: false,
    _opts: opts,
  })),
}));
vi.mock("@/shared/lib/api/imports/imports", () => ({
  useGetImportRunApiV1ImportsImportRunIdGet: vi.fn((_id: string, opts?: any) => ({
    data: undefined,
    _refetchInterval: opts?.query?.refetchInterval,
  })),
}));

import { usePluginPreview } from "./use-plugins";

describe("usePluginPreview", () => {
  it("disables the query when runId is null", () => {
    const result = usePluginPreview(null) as unknown as { _refetchInterval?: unknown };
    // When disabled the poll callback returns false for a missing run.
    const interval = result._refetchInterval as (q: { state: { data?: { status?: string } } }) => number | false;
    expect(interval({ state: { data: undefined } })).toBe(false);
  });
});
```

> The generated hook names are the orval convention. If `plugins/plugins.ts` names them differently, update both the `vi.mock` target and the import in `use-plugins.ts`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/plugins/use-plugins.test.ts`
Expected: FAIL — `use-plugins.ts` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/features/import-hub/plugins/use-plugins.ts`:

```ts
import { useGetImportRunApiV1ImportsImportRunIdGet } from "@/shared/lib/api/imports/imports";
import {
  useListPluginsApiV1PluginsGet,
  useStartPluginRunApiV1PluginsPluginIdRunsPost,
} from "@/shared/lib/api/plugins/plugins";
import { ImportStatus } from "@/shared/lib/api/model";
import { showSuccess } from "@/shared/lib/toast";

const ACTIVE_STATUSES: ImportStatus[] = [ImportStatus.queued, ImportStatus.running];

/** Catalog of registered plugins (manifests). */
export function usePluginCatalog() {
  return useListPluginsApiV1PluginsGet();
}

/** Start a plugin run (dry-run preview or real). Toasts on success. */
export function useStartPluginRun() {
  return useStartPluginRunApiV1PluginsPluginIdRunsPost({
    mutation: { onSuccess: () => showSuccess("Plugin run started") },
  });
}

/** Poll a (preview) run every 2s while active; disabled when runId is null. */
export function usePluginPreview(runId: string | null) {
  return useGetImportRunApiV1ImportsImportRunIdGet(runId ?? "", {
    query: {
      enabled: Boolean(runId),
      refetchInterval: (query) => {
        const status = query.state.data?.status;
        return status && ACTIVE_STATUSES.includes(status) ? 2000 : false;
      },
    },
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/plugins/use-plugins.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/plugins/use-plugins.ts frontend/src/features/import-hub/plugins/use-plugins.test.ts
git commit -m "feat(import-hub): plugin catalog + run + preview hooks"
```

---

## Task 2: Descriptor-driven param form

**Files:**
- Create: `frontend/src/features/import-hub/plugins/plugin-param-form.tsx`
- Test: `frontend/src/features/import-hub/plugins/plugin-param-form.test.tsx`

**Interfaces:**
- Consumes: `ParamFieldResponse` (`@/shared/lib/api/model`); `OrganismCombobox` (`../components/organism-combobox`); `useUploadEssentiality` (`../hooks/use-imports`).
- Produces: `PluginParamForm({ params, values, onChange })` — a controlled form rendering one input per `ParamField.type` (`string`/`number`/`enum`/`organism`/`file_upload`/`bool`), calling `onChange(next)` on every edit. `values: Record<string, unknown>`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/import-hub/plugins/plugin-param-form.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/use-imports", () => ({
  useUploadEssentiality: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock("../components/organism-combobox", () => ({
  OrganismCombobox: () => <div data-testid="organism-combobox" />,
}));

import { PluginParamForm } from "./plugin-param-form";

const params = [
  { key: "organism_id", label: "Organism", type: "organism", required: true, options: [] },
  { key: "upload", label: "Table", type: "file_upload", required: true, options: [] },
  { key: "condition", label: "Condition", type: "string", required: false, options: [] },
  { key: "force", label: "Force", type: "bool", required: false, options: [] },
] as any;

describe("PluginParamForm", () => {
  it("renders an input per descriptor field, by type", () => {
    render(<PluginParamForm params={params} values={{}} onChange={() => {}} />);
    expect(screen.getByTestId("organism-combobox")).toBeInTheDocument();
    expect(screen.getByLabelText("Condition")).toBeInTheDocument();
    expect(screen.getByLabelText("Force")).toBeInTheDocument();
    // file_upload renders a native file input
    expect(document.querySelector('input[type="file"]')).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/plugins/plugin-param-form.test.tsx`
Expected: FAIL — `plugin-param-form.tsx` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/features/import-hub/plugins/plugin-param-form.tsx`:

```tsx
"use client";

import type { ParamFieldResponse } from "@/shared/lib/api/model";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

import { OrganismCombobox } from "../components/organism-combobox";
import { useUploadEssentiality } from "../hooks/use-imports";

type Values = Record<string, unknown>;

interface PluginParamFormProps {
  params: ParamFieldResponse[];
  values: Values;
  onChange: (next: Values) => void;
}

export function PluginParamForm({ params, values, onChange }: PluginParamFormProps) {
  const upload = useUploadEssentiality();
  const set = (key: string, value: unknown) => onChange({ ...values, [key]: value });

  async function handleFile(key: string, file: File | undefined) {
    if (!file) return;
    // orval types the multipart body field `file` as string; cast to satisfy tsc.
    const res = await upload.mutateAsync({ data: { file: file as unknown as string } });
    set(key, res.upload_ref);
  }

  return (
    <div className="flex flex-col gap-4">
      {params.map((pf) => (
        <div key={pf.key} className="grid gap-1.5">
          <Label htmlFor={pf.key}>
            {pf.label}
            {pf.required ? <span className="text-destructive"> *</span> : null}
          </Label>

          {pf.type === "organism" ? (
            <OrganismCombobox onSelect={(id) => set(pf.key, id)} />
          ) : pf.type === "enum" ? (
            <Select value={(values[pf.key] as string) ?? ""} onValueChange={(v) => set(pf.key, v)}>
              <SelectTrigger id={pf.key} aria-label={pf.label}>
                <SelectValue placeholder="Select…" />
              </SelectTrigger>
              <SelectContent>
                {(pf.options ?? []).map((o) => (
                  <SelectItem key={o} value={o}>
                    {o}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : pf.type === "bool" ? (
            <input
              id={pf.key}
              type="checkbox"
              className="size-4"
              checked={Boolean(values[pf.key])}
              onChange={(e) => set(pf.key, e.target.checked)}
            />
          ) : pf.type === "file_upload" ? (
            <Input
              id={pf.key}
              type="file"
              onChange={(e) => handleFile(pf.key, e.target.files?.[0])}
            />
          ) : (
            <Input
              id={pf.key}
              type={pf.type === "number" ? "number" : "text"}
              value={(values[pf.key] as string) ?? ""}
              onChange={(e) => set(pf.key, e.target.value)}
            />
          )}

          {pf.help ? <p className="text-xs text-muted-foreground">{pf.help}</p> : null}
        </div>
      ))}
    </div>
  );
}
```

`ponytail:` no zod schema — the param set is dynamic and the backend re-validates against the manifest (422). The form only collects values.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/plugins/plugin-param-form.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/plugins/plugin-param-form.tsx frontend/src/features/import-hub/plugins/plugin-param-form.test.tsx
git commit -m "feat(import-hub): descriptor-driven plugin param form"
```

---

## Task 3: Plugin catalog

**Files:**
- Create: `frontend/src/features/import-hub/plugins/plugin-catalog.tsx`
- Test: `frontend/src/features/import-hub/plugins/plugin-catalog.test.tsx`

**Interfaces:**
- Consumes: `usePluginCatalog` (Task 1); `generationMethodBadgeVariant` (Plan A, `@/features/protein-catalog/components/sections/editable-record-table`); `Card`/`Badge`/`Button`.
- Produces: `PluginCatalogPage` — renders `PluginCard`s from the catalog, a record-type filter, a source-kind chip colored via `generationMethodBadgeVariant(default_generation_method)`, a "needs config" badge when `requires_secrets.length > 0`, and opens `PluginRunPanel` on a card's "Run" button.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/import-hub/plugins/plugin-catalog.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const manifests = [
  {
    id: "dejesus_essentiality",
    name: "DeJesus essentiality",
    description: "Load essentiality calls.",
    target_records: ["essentiality"],
    default_generation_method: "imported",
    params: [],
    requires_secrets: [],
  },
  {
    id: "ai_miner",
    name: "AI essentiality miner",
    description: "LLM-extracted calls.",
    target_records: ["essentiality"],
    default_generation_method: "ai_extracted",
    params: [],
    requires_secrets: ["OPENAI_API_KEY"],
  },
];

vi.mock("./use-plugins", () => ({
  usePluginCatalog: () => ({ data: manifests, isLoading: false, isError: false }),
}));
vi.mock("./plugin-run-panel", () => ({ PluginRunPanel: () => null }));

import { PluginCatalogPage } from "./plugin-catalog";

describe("PluginCatalogPage", () => {
  it("renders a card per plugin with a source-kind chip and a needs-config badge", () => {
    render(<PluginCatalogPage />);
    expect(screen.getByText("DeJesus essentiality")).toBeInTheDocument();
    expect(screen.getByText("AI essentiality miner")).toBeInTheDocument();
    // AI plugin surfaces a "needs config" badge (requires a secret)
    expect(screen.getByText(/needs config/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/plugins/plugin-catalog.test.tsx`
Expected: FAIL — `plugin-catalog.tsx` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/features/import-hub/plugins/plugin-catalog.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";

import { generationMethodBadgeVariant } from "@/features/protein-catalog/components/sections/editable-record-table";
import type { PluginManifestResponse } from "@/shared/lib/api/model";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

import { usePluginCatalog } from "./use-plugins";
import { PluginRunPanel } from "./plugin-run-panel";

const humanize = (s: string) => s.replace(/_/g, " ");

function PluginCard({ m, onRun }: { m: PluginManifestResponse; onRun: () => void }) {
  const method = m.default_generation_method;
  const isAi = method.startsWith("ai_");
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle>{m.name}</CardTitle>
          <Badge variant={generationMethodBadgeVariant(method)}>
            {isAi ? "AI" : humanize(method)}
          </Badge>
        </div>
        <CardDescription>{m.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-1.5">
        {m.target_records.map((r) => (
          <Badge key={r} variant="outline">
            {humanize(r)}
          </Badge>
        ))}
        {m.requires_secrets.length > 0 ? <Badge variant="warning">needs config</Badge> : null}
      </CardContent>
      <CardFooter className="mt-auto">
        <Button size="sm" onClick={onRun}>
          Run
        </Button>
      </CardFooter>
    </Card>
  );
}

export function PluginCatalogPage() {
  const { data, isLoading, isError } = usePluginCatalog();
  const [recordFilter, setRecordFilter] = useState<string>("all");
  const [selected, setSelected] = useState<PluginManifestResponse | null>(null);

  const recordTypes = useMemo(() => {
    const set = new Set<string>();
    for (const m of data ?? []) for (const r of m.target_records) set.add(r);
    return [...set];
  }, [data]);

  const visible = useMemo(
    () =>
      (data ?? []).filter(
        (m) => recordFilter === "all" || m.target_records.includes(recordFilter),
      ),
    [data, recordFilter],
  );

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading plugins…</p>;
  if (isError) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        Failed to load plugins.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Plugins</h1>
          <p className="text-sm text-muted-foreground">
            Ingestion sources that fill target-biology records. AI-produced values render blue.
          </p>
        </div>
        <Select value={recordFilter} onValueChange={setRecordFilter}>
          <SelectTrigger aria-label="Filter by record type" className="w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All record types</SelectItem>
            {recordTypes.map((r) => (
              <SelectItem key={r} value={r}>
                {humanize(r)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((m) => (
          <PluginCard key={m.id} m={m} onRun={() => setSelected(m)} />
        ))}
      </div>

      {selected ? (
        <PluginRunPanel
          manifest={selected}
          open={selected !== null}
          onOpenChange={(open) => !open && setSelected(null)}
        />
      ) : null}
    </div>
  );
}
```

`ponytail:` "needs config" is shown whenever the manifest declares required secrets — the FE can't see whether the env var is actually set. Wire a real `secrets_ready` flag from the backend only if operators find the always-on badge noisy.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/plugins/plugin-catalog.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/plugins/plugin-catalog.tsx frontend/src/features/import-hub/plugins/plugin-catalog.test.tsx
git commit -m "feat(import-hub): plugin catalog cards + record-type filter + provenance chip"
```

---

## Task 4: Run flow with dry-run preview

**Files:**
- Create: `frontend/src/features/import-hub/plugins/plugin-run-panel.tsx`
- Test: `frontend/src/features/import-hub/plugins/plugin-run-panel.test.tsx`

**Interfaces:**
- Consumes: `useStartPluginRun`, `usePluginPreview` (Task 1); `PluginParamForm` (Task 2); `Dialog`/`Button`; `useRouter` (`next/navigation`).
- Produces: `PluginRunPanel({ manifest, open, onOpenChange })` — renders the param form; **Preview** starts a `dry_run: true` run and shows its summary counts when it finishes; **Run** starts a `dry_run: false` run and navigates to `/admin/imports/{id}` (the existing monitor).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/import-hub/plugins/plugin-run-panel.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const startMutate = vi.fn(async () => ({ id: "run-123" }));
vi.mock("./use-plugins", () => ({
  useStartPluginRun: () => ({ mutateAsync: startMutate, isPending: false }),
  usePluginPreview: () => ({
    data: { status: "succeeded", summary: { created: 3, updated: 1, skipped: 0, failed: 0 } },
  }),
}));
vi.mock("./plugin-param-form", () => ({
  PluginParamForm: () => <div data-testid="param-form" />,
}));

import { PluginRunPanel } from "./plugin-run-panel";

const manifest = {
  id: "dejesus_essentiality",
  name: "DeJesus essentiality",
  description: "d",
  target_records: ["essentiality"],
  default_generation_method: "imported",
  params: [],
  requires_secrets: [],
} as any;

describe("PluginRunPanel", () => {
  it("shows dry-run preview counts after Preview", async () => {
    render(<PluginRunPanel manifest={manifest} open onOpenChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /preview/i }));
    expect(startMutate).toHaveBeenCalledWith({
      pluginId: "dejesus_essentiality",
      data: { params: {}, dry_run: true },
    });
    expect(await screen.findByText(/create 3/i)).toBeInTheDocument();
  });

  it("navigates to the monitor after Run", async () => {
    render(<PluginRunPanel manifest={manifest} open onOpenChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByText("DeJesus essentiality")).toBeInTheDocument();
    // push is called with the run route
    expect(push).toHaveBeenCalledWith("/admin/imports/run-123");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/plugins/plugin-run-panel.test.tsx`
Expected: FAIL — `plugin-run-panel.tsx` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/features/import-hub/plugins/plugin-run-panel.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import type { PluginManifestResponse } from "@/shared/lib/api/model";
import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";

import { PluginParamForm } from "./plugin-param-form";
import { useStartPluginRun, usePluginPreview } from "./use-plugins";

type Values = Record<string, unknown>;

interface PluginRunPanelProps {
  manifest: PluginManifestResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function num(v: unknown): number {
  return typeof v === "number" ? v : Number(v ?? 0) || 0;
}

export function PluginRunPanel({ manifest, open, onOpenChange }: PluginRunPanelProps) {
  const router = useRouter();
  const start = useStartPluginRun();
  const [values, setValues] = useState<Values>({});
  const [previewRunId, setPreviewRunId] = useState<string | null>(null);

  const preview = usePluginPreview(previewRunId);
  const summary =
    preview.data?.status === "succeeded"
      ? (preview.data.summary as Record<string, unknown>)
      : null;

  async function onPreview() {
    const run = await start.mutateAsync({
      pluginId: manifest.id,
      data: { params: values, dry_run: true },
    });
    setPreviewRunId(run.id);
  }

  async function onRun() {
    const run = await start.mutateAsync({
      pluginId: manifest.id,
      data: { params: values, dry_run: false },
    });
    onOpenChange(false);
    router.push(`/admin/imports/${run.id}`);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{manifest.name}</DialogTitle>
          <DialogDescription>{manifest.description}</DialogDescription>
        </DialogHeader>

        <PluginParamForm
          params={manifest.params}
          values={values}
          onChange={(next) => {
            setValues(next);
            setPreviewRunId(null); // params changed — stale preview
          }}
        />

        {previewRunId && !summary ? (
          <p className="text-sm text-muted-foreground animate-pulse">Previewing…</p>
        ) : null}
        {summary ? (
          <p className="text-sm">
            Preview: create {num(summary.created)} · update {num(summary.updated)} · skip{" "}
            {num(summary.skipped)} · fail {num(summary.failed)}
          </p>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={onPreview} disabled={start.isPending}>
            Preview
          </Button>
          <Button onClick={onRun} disabled={start.isPending}>
            Run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && ./node_modules/.bin/vitest run src/features/import-hub/plugins/plugin-run-panel.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/import-hub/plugins/plugin-run-panel.tsx frontend/src/features/import-hub/plugins/plugin-run-panel.test.tsx
git commit -m "feat(import-hub): plugin run panel with dry-run preview"
```

---

## Task 5: Mount the catalog page + wire navigation

**Files:**
- Create: `frontend/src/app/(dashboard)/admin/plugins/page.tsx`
- Modify: `frontend/src/features/import-hub/index.ts`
- Modify: the admin nav/sidebar where the "Imports" link is defined

**Interfaces:**
- Produces: the `/admin/plugins` route rendering `PluginCatalogPage`; a "Plugins" nav entry alongside "Imports".

- [ ] **Step 1: Export the page component**

In `frontend/src/features/import-hub/index.ts`, add:

```ts
export { PluginCatalogPage } from "./plugins/plugin-catalog";
```

- [ ] **Step 2: Create the route page**

Create `frontend/src/app/(dashboard)/admin/plugins/page.tsx` (mirror `admin/imports/page.tsx`):

```tsx
import { PluginCatalogPage } from "@/features/import-hub";

export default function Page() {
  return <PluginCatalogPage />;
}
```

- [ ] **Step 3: Add the nav link**

Find the admin nav that renders the "Imports" link (grep the sidebar/nav for `"/admin/imports"`):

```bash
cd frontend && grep -rn '/admin/imports' src/app src/shared src/features --include=*.tsx | grep -iv test
```

Add a sibling entry pointing to `/admin/plugins` labeled "Plugins", copying the exact shape of the "Imports" entry (icon + label + href) used in that nav config. Keep it directly below "Imports".

- [ ] **Step 4: Typecheck, lint, and run the plugins suite**

Run:
```bash
cd frontend
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/biome check src/features/import-hub src/app/(dashboard)/admin/plugins
./node_modules/.bin/vitest run src/features/import-hub
```
Expected: `tsc` clean; biome clean; all import-hub vitest suites PASS. If `tsc` flags the generated plugin hook/type names, reconcile the imports in `use-plugins.ts` / component files against the actual identifiers in `src/shared/lib/api/plugins/plugins.ts` and `src/shared/lib/api/model/`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/(dashboard)/admin/plugins frontend/src/features/import-hub/index.ts frontend/src/features/import-hub/components frontend/src/shared
git commit -m "feat(import-hub): mount /admin/plugins catalog + nav link"
```

---

## Task 6: Tier 2 monitor polish + full gates

**Files:**
- (Optional) Modify: `frontend/src/features/import-hub/components/import-detail.tsx`
- Verification.

**Interfaces:**
- The existing monitor already renders a plugin run's summary via its generic `Object.entries(data.summary)` `<dl>`, so a plugin run's `{created, updated, skipped, failed, total}` shows without changes. This task adds a compact counts row and runs all gates.

- [ ] **Step 1: (Optional) compact counts row**

In `import-detail.tsx`, above the existing generic Summary `<dl>`, add a counts strip when the summary carries the plugin keys — reuse `Badge` for legibility:

```tsx
{["created", "updated", "skipped", "failed"].some((k) => k in ((data.summary as Record<string, unknown>) ?? {})) ? (
  <div className="flex flex-wrap gap-2 text-sm">
    {(["created", "updated", "skipped", "failed"] as const).map((k) => (
      <span key={k} className="rounded bg-muted px-2 py-0.5">
        {k}: {asNumber((data.summary as Record<string, unknown>)?.[k])}
      </span>
    ))}
  </div>
) : null}
```

(`asNumber` already exists in this file.) `ponytail:` this is pure polish — skip it if the generic `<dl>` reads well enough; the deliverable is the catalog + run flow.

- [ ] **Step 2: Full frontend gates**

Run:
```bash
cd frontend
./node_modules/.bin/vitest run
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/biome check src/
```
Expected: all PASS/clean.

- [ ] **Step 3: Manual acceptance (the spec §16 demo)**

With the backend + worker running (`make dev` or equivalent; ensure the arq worker is up so runs execute):

1. Open `/admin/plugins` → the **DeJesus essentiality** card shows (neutral `imported` chip, `essentiality` record chip).
2. Click **Run** → choose the organism (M. tuberculosis H37Rv) and drop a DeJesus table → **Preview** shows "create N / update M / skip K / fail J".
3. Click **Run** → land on the run monitor, watch live progress → status reaches SUCCEEDED with the counts summary.
4. Open a gene detail page for a locus in the file → its **Essentiality** record shows, Source cell rendered as a colored badge (`imported` → neutral, per Plan A), editable by a human (which flips it to `manual`/foreground).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/import-hub/components/import-detail.tsx
git commit -m "feat(import-hub): surface created/updated/skipped/failed counts on run detail" || echo "nothing to commit"
```

---

## Self-Review (checked against the spec §9)

- **§9 Tier 1.1 catalog** — cards from `GET /plugins`, filterable by record type, source-kind chip in the provenance color language (blue for AI via `generationMethodBadgeVariant`), needs-config badge ✓ (Task 3). Last-run status per card is **deferred** — it needs a per-plugin last-run lookup the current API doesn't provide; the runs list already shows run history. (Noted as a small follow-on, not built.)
- **§9 Tier 1.2 run flow + preview** — param form rendered from the `ParamField` descriptor ✓ (Task 2); dry-run Preview showing would-create/update/skip/fail before committing ✓ (Task 4).
- **§9 Tier 1.3 provenance in data** — delivered by **Plan A** (Source badge + legend + tooltip). Not repeated here. The optional per-table "hide AI predictions" filter remains deferred (Plan A self-review).
- **§9 Tier 2 reuse** — monitor / detail drawer / live progress / runs table kept unchanged; plugin runs flow through them; optional counts-strip polish added ✓ (Task 6).
- **§9 Tier 3 not building** — no marketplace, no pipeline builder, no scheduling, no per-plugin analytics ✓.
- **Scope decision (documented)** — the catalog is additive: the legacy "New import" dialog stays on `/admin/imports` for the 3 built-in importers until they gain manifests; both paths produce `ImportRun`s and share the monitor/history. This coexistence is the honest incremental step, not a regression.
- **Type consistency** — hook names follow the orval convention with an explicit "confirm against the generated file" gate (Task 1, Task 5); `PluginManifestResponse`/`ParamFieldResponse` come from the regenerated model; `mutateAsync({ pluginId, data })` shape flagged for confirmation against `plugins/plugins.ts`.
```
