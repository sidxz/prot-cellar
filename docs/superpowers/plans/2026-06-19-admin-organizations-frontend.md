# Frontend Plan 4 — Workspace Config / Admin (Organizations CRUD) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the workspace-scoped Organizations admin feature — browse (list), detail, and create/edit — wiring the already-present "Administration → Organizations" nav link (`/admin/organizations`) to real routes.

**Architecture:** A new `workspace-config` feature slice mirroring the reviewer-approved **strain CRUD** trio in `features/taxonomy` (the closest analog: workspace-scoped, full CRUD **minus delete**). Generated orval hooks wrapped with success-only toast + **generated-query-key** cache invalidation; rhf+zod create/edit dialog; ag-grid list with cursor-stack pagination; detail page with an Edit dialog. Routes live under `(dashboard)/admin/organizations`.

**Tech Stack:** Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind 4 · TanStack Query · orval-generated API client · react-hook-form + zod · shadcn (new-york) · ag-grid · Sentinel auth · vitest.

## Global Constraints

Every task's requirements implicitly include this section.

- **Feature slice:** all non-route code lives under `src/features/workspace-config/` (`types/`, `hooks/`, `components/`, `index.ts` barrel). Routes live under `src/app/(dashboard)/admin/organizations/`.
- **Generated-key invalidation (Plan-2/3 lesson — non-negotiable):** mutation wrappers MUST invalidate the orval-**generated** query-key helpers — `getListOrganizationsApiV1OrganizationsGetQueryKey()` and `getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey(orgId)` — NEVER hand-rolled string keys like `["organizations"]`. The generated query hooks cache by URL; hand-rolled keys invalidate nothing → stale UI after create/edit. Ship the regression test in T1, alongside the hooks.
- **No `onError` on mutations:** the global `MutationCache` already shows the error toast. A per-mutation `onError` double-toasts. Wrappers pass only `{ mutation: { onSuccess } }`.
- **Never send `workspace_id`:** it is derived server-side from the Sentinel auth context. It appears in `OrganizationResponse` (display only), never in any create/update body.
- **Optional strings:** trim and convert empty → `undefined` before sending in a request body.
- **Admin-gating:** organization writes are `require_admin` on the backend. The frontend does NOT pre-gate the UI (mirrors strains, which are editor-gated without a frontend guard; `useAuthz` here only exposes `isAuthenticated`/`isLoading`/`user`/`logout`). A 403 surfaces via the global error toast. Note this as tracked debt, do not build a bespoke guard.
- **No `is_active` mutation:** `is_active` is in `OrganizationResponse` but is absent from both `CreateOrganizationBody` and `UpdateOrganizationBody` — there is no API to deactivate. Display it (badge + `include_inactive` list toggle) but provide NO activate/deactivate control. Note as tracked debt.
- **Design tokens only:** no raw Tailwind color utilities (e.g. `bg-teal-600`). Use semantic tokens / `primary` / Badge variants (Plan-1 lesson).
- **a11y:** labeled inputs (`<Label htmlFor>`), `aria-label` on icon-only and link cells, `<th scope="col">` for native tables; grid cell `<Link>`s call `e.stopPropagation()` so a link click does not also trigger row navigation.
- **Green gate (every task ends green):** `pnpm lint` (= `biome check src/`) exit 0 (8 pre-existing data-grid warnings are acceptable), `pnpm exec tsc --noEmit` clean (there is **no** `typecheck` npm script — invoke the binary), `pnpm test` (= `vitest run`; scope to a file with `pnpm test <path>`) green, and — at the final task — `pnpm build` (= `next build`) green. Package manager is **pnpm**.
- **No new UI dependencies:** the shadcn primitives present are `badge`, `card`, `dialog`, `select`, `textarea` (plus `button`, `input`, `label`, `skeleton`). **`Switch` and `Checkbox` do NOT exist** and radix-switch/checkbox are not installed — do NOT add them. The list's "show inactive" toggle is a plain `Button` (see T3).

### Backend contract (from `frontend/openapi.json`)

```
GET    /api/v1/organizations            -> list   (query: include_inactive=false, cursor?, limit?)
POST   /api/v1/organizations            -> create (body: CreateOrganizationBody)
GET    /api/v1/organizations/{org_id}   -> detail
PATCH  /api/v1/organizations/{org_id}   -> update (body: UpdateOrganizationBody)
# NO DELETE endpoint.
```

`OrganizationType` enum (6 values): `internal`, `pharma_partner`, `cro`, `academic`, `vendor`, `government`.

| Field | Create body | Update body | Response |
|---|---|---|---|
| `name` | required | optional | yes |
| `org_type` | required | optional | yes |
| `contact_name` | optional | optional | yes (nullable) |
| `contact_email` | optional | optional | yes (nullable) |
| `notes` | optional | optional | yes (nullable) |
| `id` / `workspace_id` / `is_active` / `version` | — | — | yes (display only) |

Generated symbols to consume (from `src/shared/lib/api/organizations/organizations.ts`):
- `useListOrganizationsApiV1OrganizationsGet(params?)` — `params` = `{ include_inactive?, cursor?, limit? }`
- `useGetOrganizationApiV1OrganizationsOrgIdGet(orgId)`
- `useCreateOrganizationApiV1OrganizationsPost(options)` — mutate vars `{ data: CreateOrganizationBody }`
- `useUpdateOrganizationApiV1OrganizationsOrgIdPatch(options)` — mutate vars `{ orgId: string, data: UpdateOrganizationBody }`
- `getListOrganizationsApiV1OrganizationsGetQueryKey()`
- `getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey(orgId)`

Generated model types (from `@/shared/lib/api/model`): `OrganizationResponse`, `OrganizationType`, `CreateOrganizationBody`, `UpdateOrganizationBody`.

> **Reference templates (already in-repo, reviewer-approved — mirror these exactly):** `features/taxonomy/hooks/use-strains.ts`, `features/taxonomy/hooks/use-strains.test.ts`, `features/taxonomy/components/strain-form-dialog.tsx`, `strain-columns.tsx`, `strain-list.tsx`, `strain-detail.tsx`, `features/taxonomy/types/index.ts`, `features/taxonomy/index.ts`, and the strain routes under `app/(dashboard)/strains/`. The Select-as-filter pattern is in `features/target/components/target-list.tsx`. Read the analog before writing each file.

---

## File Structure

```
src/features/workspace-config/
  types/index.ts                              # T1 — Organization alias, ORG_TYPE_LABELS, filters, form values
  hooks/use-organizations.ts                  # T1 — list/detail/create/update wrappers (generated-key invalidation)
  hooks/use-organizations.test.ts             # T1 — invalidation regression test
  components/organization-form-dialog.tsx     # T2 — rhf+zod create/edit dialog
  components/organization-form-dialog.test.tsx# T2
  components/organization-columns.tsx         # T3 — ag-grid column defs
  components/organization-list.tsx            # T3 — list page (pagination + include_inactive + New)
  components/organization-list.test.tsx       # T3
  components/organization-detail.tsx          # T4 — detail page + Edit dialog
  components/organization-detail.test.tsx     # T4
  index.ts                                    # T5 — barrel

src/app/(dashboard)/admin/organizations/
  page.tsx                                    # T3 — list route
  [id]/page.tsx                               # T4 — detail route
```

Nav (`src/shared/lib/navigation.ts`) already declares the "Administration → Organizations → `/admin/organizations`" item (built in Plan 0). No nav edit is required; T5 only verifies it resolves.

---

## Task 1: Scaffolding — types, hooks, invalidation regression test

**Files:**
- Create: `src/features/workspace-config/types/index.ts`
- Create: `src/features/workspace-config/hooks/use-organizations.ts`
- Test: `src/features/workspace-config/hooks/use-organizations.test.ts`

**Interfaces:**
- Consumes: generated symbols listed in Global Constraints.
- Produces:
  - `type Organization = OrganizationResponse`
  - `const ORG_TYPE_LABELS: Record<OrganizationType, string>`
  - `interface OrganizationListFilters { includeInactive?: boolean }`
  - `interface OrganizationFormValues { name: string; org_type: OrganizationType; contact_name?: string; contact_email?: string; notes?: string }`
  - `useOrganizations(cursor?: string, includeInactive?: boolean)` → list query
  - `useOrganization(id: string)` → detail query
  - `useCreateOrganization()` → mutation; vars `{ data }`
  - `useUpdateOrganization()` → mutation; vars `{ orgId, data }`

- [ ] **Step 1: Write the types file**

```typescript
// src/features/workspace-config/types/index.ts
import type {
  CreateOrganizationBody,
  OrganizationResponse,
  OrganizationType,
  UpdateOrganizationBody,
} from "@/shared/lib/api/model";

/** Narrowed alias — organization (no narrowing needed beyond the generated type). */
export type Organization = OrganizationResponse;

// Re-export the generated body/enum types so feature code imports them from one place.
export type { CreateOrganizationBody, OrganizationType, UpdateOrganizationBody };

/** Human-readable labels for all 6 organization_type values. */
export const ORG_TYPE_LABELS: Record<OrganizationType, string> = {
  internal: "Internal",
  pharma_partner: "Pharma partner",
  cro: "CRO",
  academic: "Academic",
  vendor: "Vendor",
  government: "Government",
};

/** Filter parameters for listing organizations. */
export interface OrganizationListFilters {
  includeInactive?: boolean;
}

/** Form values for creating or editing an organization. */
export interface OrganizationFormValues {
  name: string;
  org_type: OrganizationType;
  contact_name?: string;
  contact_email?: string;
  notes?: string;
}
```

- [ ] **Step 2: Write the hooks file**

Mirror `use-strains.ts` exactly, adapting names and adding the `include_inactive` list param.

```typescript
// src/features/workspace-config/hooks/use-organizations.ts
import { useQueryClient } from "@tanstack/react-query";

import {
  getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey,
  getListOrganizationsApiV1OrganizationsGetQueryKey,
  useCreateOrganizationApiV1OrganizationsPost,
  useGetOrganizationApiV1OrganizationsOrgIdGet,
  useListOrganizationsApiV1OrganizationsGet,
  useUpdateOrganizationApiV1OrganizationsOrgIdPatch,
} from "@/shared/lib/api/organizations/organizations";
import { showSuccess } from "@/shared/lib/toast";

/** List organizations with optional cursor pagination and an include-inactive toggle. */
export function useOrganizations(cursor?: string, includeInactive?: boolean) {
  return useListOrganizationsApiV1OrganizationsGet({
    cursor: cursor ?? undefined,
    include_inactive: includeInactive ?? undefined,
  });
}

/** Fetch a single organization by id. */
export function useOrganization(id: string) {
  return useGetOrganizationApiV1OrganizationsOrgIdGet(id);
}

/**
 * Create a new organization.
 * On success: invalidates the organizations list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useCreateOrganizationApiV1OrganizationsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListOrganizationsApiV1OrganizationsGetQueryKey(),
        });
        showSuccess("Organization created");
      },
    },
  });
}

/**
 * Update an existing organization.
 * On success: invalidates both the list and the specific detail, then toasts.
 * No onError — the global MutationCache handles the error toast.
 */
export function useUpdateOrganization() {
  const queryClient = useQueryClient();
  return useUpdateOrganizationApiV1OrganizationsOrgIdPatch({
    mutation: {
      onSuccess: (_data, variables) => {
        queryClient.invalidateQueries({
          queryKey: getListOrganizationsApiV1OrganizationsGetQueryKey(),
        });
        queryClient.invalidateQueries({
          queryKey: getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey(variables.orgId),
        });
        showSuccess("Organization updated");
      },
    },
  });
}
```

> If `useListOrganizationsApiV1OrganizationsGet` rejects an `include_inactive: undefined` param at the type level, omit it conditionally (build the params object and only set `include_inactive` when `includeInactive` is truthy). Read the generated `ListOrganizationsApiV1OrganizationsGetParams` type first.

- [ ] **Step 3: Write the failing regression test**

Mirror `use-strains.test.ts` — capture the `onSuccess` each wrapper hands the generated hook, invoke it, assert the **generated** keys and negative-assert the hand-rolled keys.

```typescript
// src/features/workspace-config/hooks/use-organizations.test.ts
import { describe, expect, it, vi } from "vitest";

import {
  getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey,
  getListOrganizationsApiV1OrganizationsGetQueryKey,
} from "@/shared/lib/api/organizations/organizations";

const mockInvalidateQueries = vi.fn();
const mockQueryClient = { invalidateQueries: mockInvalidateQueries };

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mockQueryClient,
}));

let capturedCreateOptions: { mutation?: { onSuccess?: (...args: unknown[]) => void } } = {};
let capturedUpdateOptions: { mutation?: { onSuccess?: (...args: unknown[]) => void } } = {};

vi.mock("@/shared/lib/api/organizations/organizations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/shared/lib/api/organizations/organizations")>();
  return {
    ...actual,
    useCreateOrganizationApiV1OrganizationsPost: (options: {
      mutation?: { onSuccess?: (...args: unknown[]) => void };
    }) => {
      capturedCreateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
    useUpdateOrganizationApiV1OrganizationsOrgIdPatch: (options: {
      mutation?: { onSuccess?: (...args: unknown[]) => void };
    }) => {
      capturedUpdateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
  };
});

vi.mock("@/shared/lib/toast", () => ({ showSuccess: vi.fn() }));

import { useCreateOrganization, useUpdateOrganization } from "./use-organizations";

describe("useCreateOrganization — cache invalidation", () => {
  it("invalidates the generated list query key on success", () => {
    mockInvalidateQueries.mockClear();
    useCreateOrganization();
    const onSuccess = capturedCreateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();
    onSuccess?.({}, {}, undefined);

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: getListOrganizationsApiV1OrganizationsGetQueryKey(),
    });
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["organizations"] });
  });
});

describe("useUpdateOrganization — cache invalidation", () => {
  it("invalidates BOTH the list key AND the detail key on success", () => {
    mockInvalidateQueries.mockClear();
    useUpdateOrganization();
    const onSuccess = capturedUpdateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();

    const orgId = "test-org-abc";
    onSuccess?.({}, { orgId }, undefined);

    const expectedDetailKey = getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey(orgId);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: getListOrganizationsApiV1OrganizationsGetQueryKey(),
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: expectedDetailKey });
    expect(expectedDetailKey).toContain(`/api/v1/organizations/${orgId}`);
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["organizations"] });
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["organizations", orgId] });
  });
});
```

- [ ] **Step 4: Run the test — expect FAIL then PASS**

Run: `pnpm test src/features/workspace-config/hooks/use-organizations.test.ts`
Expected: starts failing (module not found / wrong keys), passes once Steps 1–2 are in place. Then run the full gate: `pnpm test`, `pnpm exec tsc --noEmit`, `pnpm lint`.

- [ ] **Step 5: Commit**

```bash
git add src/features/workspace-config/types src/features/workspace-config/hooks
git commit -m "feat(frontend): workspace-config scaffolding — org types + hooks (generated-key invalidation) + regression test"
```

---

## Task 2: Organization create/edit form dialog

**Files:**
- Create: `src/features/workspace-config/components/organization-form-dialog.tsx`
- Test: `src/features/workspace-config/components/organization-form-dialog.test.tsx`

**Interfaces:**
- Consumes: `useCreateOrganization`, `useUpdateOrganization` (T1); `ORG_TYPE_LABELS`, `Organization`, `OrganizationType` (T1); shadcn `Dialog`, `Input`, `Label`, `Textarea`, `Button`, `Select*` (`@/shared/components/ui/*`).
- Produces: `OrganizationFormDialog` with props `{ open: boolean; onOpenChange: (open: boolean) => void; organization?: Organization }`. Presence of `organization` ⇒ edit mode (mirrors strain dialog's `strain?` contract — the detail page's Edit button passes `organization={org}`).

Mirror `strain-form-dialog.tsx`. Differences: `org_type` is a **Select** (not free text, not disabled in edit — it IS in `UpdateOrganizationBody`); `contact_email` gets zod email validation; no organism-id / metadata-JSON fields.

- [ ] **Step 1: Write the failing test**

```tsx
// organization-form-dialog.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Stub the mutation hooks so no network/QueryClient is needed.
vi.mock("../hooks/use-organizations", () => ({
  useCreateOrganization: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateOrganization: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { OrganizationFormDialog } from "./organization-form-dialog";

describe("OrganizationFormDialog", () => {
  it("renders create-mode title and the name field when open with no organization", () => {
    render(<OrganizationFormDialog open onOpenChange={() => {}} />);
    expect(screen.getByRole("heading", { name: /new organization/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
  });

  it("renders edit-mode title when an organization is supplied", () => {
    render(
      <OrganizationFormDialog
        open
        onOpenChange={() => {}}
        organization={
          {
            id: "o1",
            workspace_id: "w1",
            name: "Acme Bio",
            org_type: "pharma_partner",
            contact_name: null,
            contact_email: null,
            notes: null,
            is_active: true,
            version: 1,
          } as never
        }
      />,
    );
    expect(screen.getByRole("heading", { name: /edit organization/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it — expect FAIL** (`OrganizationFormDialog` not defined). `pnpm test organization-form-dialog`.

- [ ] **Step 3: Implement the dialog**

```tsx
// organization-form-dialog.tsx
"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { Textarea } from "@/shared/components/ui/textarea";

import { useCreateOrganization, useUpdateOrganization } from "../hooks/use-organizations";
import { ORG_TYPE_LABELS, type Organization, type OrganizationType } from "../types";

const ORG_TYPE_VALUES = Object.keys(ORG_TYPE_LABELS) as [OrganizationType, ...OrganizationType[]];

const formSchema = z.object({
  name: z.string().min(1, "Name is required"),
  org_type: z.enum(ORG_TYPE_VALUES),
  contact_name: z.string().optional(),
  // Optional, but must be a valid email when provided.
  contact_email: z.string().trim().email("Enter a valid email address").optional().or(z.literal("")),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

const CREATE_DEFAULTS: FormValues = {
  name: "",
  org_type: "internal",
  contact_name: "",
  contact_email: "",
  notes: "",
};

function toFormValues(org: Organization): FormValues {
  return {
    name: org.name,
    org_type: org.org_type,
    contact_name: org.contact_name ?? "",
    contact_email: org.contact_email ?? "",
    notes: org.notes ?? "",
  };
}

interface OrganizationFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pass an organization to switch to edit mode. */
  organization?: Organization;
}

export function OrganizationFormDialog({
  open,
  onOpenChange,
  organization,
}: OrganizationFormDialogProps) {
  const isEdit = !!organization;
  const createMutation = useCreateOrganization();
  const updateMutation = useUpdateOrganization();
  const isPending = isEdit ? updateMutation.isPending : createMutation.isPending;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: CREATE_DEFAULTS,
  });

  useEffect(() => {
    if (open) {
      form.reset(organization ? toFormValues(organization) : CREATE_DEFAULTS);
    }
  }, [open, organization, form]);

  const orgType = form.watch("org_type");

  const onSubmit = async (values: FormValues) => {
    const contact_name = values.contact_name?.trim() || undefined;
    const contact_email = values.contact_email?.trim() || undefined;
    const notes = values.notes?.trim() || undefined;
    try {
      if (isEdit && organization) {
        await updateMutation.mutateAsync({
          orgId: organization.id,
          data: { name: values.name, org_type: values.org_type, contact_name, contact_email, notes },
        });
      } else {
        await createMutation.mutateAsync({
          data: { name: values.name, org_type: values.org_type, contact_name, contact_email, notes },
        });
      }
      onOpenChange(false);
    } catch {
      // Errors surface via the global mutation toast — do not add a second toast here.
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Organization" : "New Organization"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)}>
          <div className="grid gap-5 py-4">
            {/* Name */}
            <div className="grid gap-2">
              <Label htmlFor="org_name">Name</Label>
              <Input
                id="org_name"
                placeholder="e.g. Acme Biopharma"
                aria-label="Name"
                {...form.register("name")}
              />
              {form.formState.errors.name && (
                <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>

            {/* Org type */}
            <div className="grid gap-2">
              <Label htmlFor="org_type">Type</Label>
              <Select
                value={orgType}
                onValueChange={(v) => form.setValue("org_type", v as OrganizationType)}
              >
                <SelectTrigger id="org_type" aria-label="Type">
                  <SelectValue placeholder="Select a type" />
                </SelectTrigger>
                <SelectContent>
                  {ORG_TYPE_VALUES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {ORG_TYPE_LABELS[value]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {form.formState.errors.org_type && (
                <p className="text-xs text-destructive">{form.formState.errors.org_type.message}</p>
              )}
            </div>

            {/* Contact name */}
            <div className="grid gap-2">
              <Label htmlFor="contact_name">
                Contact name{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input id="contact_name" placeholder="e.g. Jane Doe" {...form.register("contact_name")} />
            </div>

            {/* Contact email */}
            <div className="grid gap-2">
              <Label htmlFor="contact_email">
                Contact email{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="contact_email"
                type="email"
                placeholder="e.g. jane@acme.com"
                {...form.register("contact_email")}
              />
              {form.formState.errors.contact_email && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.contact_email.message}
                </p>
              )}
            </div>

            {/* Notes */}
            <div className="grid gap-2">
              <Label htmlFor="notes">
                Notes <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Textarea id="notes" rows={3} placeholder="Free-form notes…" {...form.register("notes")} />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isPending}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || form.formState.isSubmitting}>
              {isPending
                ? isEdit
                  ? "Saving…"
                  : "Creating…"
                : isEdit
                  ? "Save Changes"
                  : "Create Organization"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

> Verify the shadcn `Select` value-binding idiom against `target-form-dialog.tsx`. If that file uses a `Controller` for the Select, prefer matching it for consistency (the `setValue` form above is acceptable if it keeps validation working — confirm `org_type` errors still surface). Either way, the Select must be a controlled value bound to the form.

- [ ] **Step 4: Run the test — expect PASS**, then `pnpm exec tsc --noEmit` and `pnpm lint`.

- [ ] **Step 5: Commit**

```bash
git add src/features/workspace-config/components/organization-form-dialog.tsx src/features/workspace-config/components/organization-form-dialog.test.tsx
git commit -m "feat(frontend): organization create/edit form dialog (rhf+zod, email-validated, org_type select)"
```

---

## Task 3: Organization list page (columns + grid + filter) and route

**Files:**
- Create: `src/features/workspace-config/components/organization-columns.tsx`
- Create: `src/features/workspace-config/components/organization-list.tsx`
- Test: `src/features/workspace-config/components/organization-list.test.tsx`
- Create: `src/app/(dashboard)/admin/organizations/page.tsx`

**Interfaces:**
- Consumes: `useOrganizations` (T1); `ORG_TYPE_LABELS`, `Organization` (T1); `OrganizationFormDialog` (T2); `DataGrid` (`@/shared/components/data-grid/data-grid`); `Badge`, `Button` from `@/shared/components/ui/*`. (No Switch/Checkbox — the inactive toggle is a `Button`.)
- Produces: `OrganizationListPage`. Columns: **Name** (link → `/admin/organizations/{id}`, `stopPropagation`), **Type** (Badge via `ORG_TYPE_LABELS`), **Contact** (contact_name; em-dash fallback), **Email** (contact_email; em-dash fallback), **Status** (Badge — "Active" `default` variant / "Inactive" `secondary`).

- [ ] **Step 1: Write `organization-columns.tsx`**

Mirror `strain-columns.tsx` (NameCell with `stopPropagation`, em-dash fallbacks). Add Type and Status badge cells:

```tsx
// organization-columns.tsx
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";

import { Badge } from "@/shared/components/ui/badge";
import { ORG_TYPE_LABELS, type Organization } from "../types";

function NameCell({ data, value }: ICellRendererParams<Organization, string>) {
  if (!data || !value) return <span>—</span>;
  return (
    <Link
      href={`/admin/organizations/${data.id}`}
      className="font-medium text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value}
    </Link>
  );
}

function TypeCell({ data }: ICellRendererParams<Organization>) {
  if (!data) return <span>—</span>;
  return <Badge variant="secondary">{ORG_TYPE_LABELS[data.org_type]}</Badge>;
}

function TextCell({ value }: ICellRendererParams<Organization, string | null>) {
  if (!value) return <span>—</span>;
  return <span>{value}</span>;
}

function StatusCell({ data }: ICellRendererParams<Organization>) {
  if (!data) return <span>—</span>;
  return (
    <Badge variant={data.is_active ? "default" : "secondary"}>
      {data.is_active ? "Active" : "Inactive"}
    </Badge>
  );
}

export const organizationColumnDefs: ColDef<Organization>[] = [
  { headerName: "Name", field: "name", flex: 1, minWidth: 220, cellRenderer: NameCell },
  { headerName: "Type", field: "org_type", width: 160, cellRenderer: TypeCell, sortable: false },
  { headerName: "Contact", field: "contact_name", width: 180, cellRenderer: TextCell, sortable: false },
  { headerName: "Email", field: "contact_email", width: 220, cellRenderer: TextCell, sortable: false },
  { headerName: "Status", field: "is_active", width: 120, cellRenderer: StatusCell, sortable: false },
];
```

- [ ] **Step 2: Write the list page**

Mirror `strain-list.tsx` (cursor-stack pagination, error/empty states, New button → create dialog). Add the `include_inactive` toggle, which must reset pagination when changed.

```tsx
// organization-list.tsx
"use client";

import { Building2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";

import { useOrganizations } from "../hooks/use-organizations";
import { organizationColumnDefs } from "./organization-columns";
import { OrganizationFormDialog } from "./organization-form-dialog";

function OrganizationsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Building2 className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No organizations found</p>
      <p className="text-xs">Create your first organization using the "New Organization" button above.</p>
    </div>
  );
}

export function OrganizationListPage() {
  const router = useRouter();
  const [includeInactive, setIncludeInactive] = useState(false);
  const [cursorStack, setCursorStack] = useState<(string | undefined)[]>([undefined]);
  const currentCursor = cursorStack[cursorStack.length - 1];

  const { data, isLoading, isError } = useOrganizations(currentCursor, includeInactive);

  const organizations = useMemo(() => {
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
  function toggleInactive(next: boolean) {
    setIncludeInactive(next);
    setCursorStack([undefined]); // reset pagination when the filter changes
  }

  const hasNext = !!data?.next_cursor;
  const hasPrev = cursorStack.length > 1;

  if (isError) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Organizations</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load organizations. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Organizations</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Manage workspace organizations</p>
        </div>
        <div className="flex items-center gap-3">
          {/* No Switch/Checkbox primitive in the repo — a Button toggle keeps us dependency-free. */}
          <Button
            type="button"
            variant={includeInactive ? "secondary" : "outline"}
            size="sm"
            aria-pressed={includeInactive}
            onClick={() => toggleInactive(!includeInactive)}
          >
            {includeInactive ? "Showing inactive" : "Show inactive"}
          </Button>
          <Button type="button" size="sm" onClick={() => setNewOpen(true)}>
            New Organization
          </Button>
        </div>
      </div>

      <DataGrid
        rowData={organizations}
        columnDefs={organizationColumnDefs}
        loading={isLoading}
        height="calc(100vh - 240px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(org) => router.push(`/admin/organizations/${org.id}`)}
        emptyState={<OrganizationsEmptyState />}
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

      <OrganizationFormDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  );
}
```

> The "show inactive" toggle is a plain `Button` (above) because the repo has no Switch/Checkbox primitive and we must not add a dependency. `toggleInactive` flips the flag AND resets `cursorStack` to `[undefined]` so pagination restarts when the filter changes.

- [ ] **Step 3: Write the route**

```tsx
// src/app/(dashboard)/admin/organizations/page.tsx
import { OrganizationListPage } from "@/features/workspace-config";

export default function Page() {
  return <OrganizationListPage />;
}
```

- [ ] **Step 4: Write the test** (mirror `strain-list.test.tsx` — mock `next/navigation`, stub `DataGrid`, mock `useOrganizations` to return two rows, assert a row name reaches the grid).

```tsx
// organization-list.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("../hooks/use-organizations", () => ({
  useOrganizations: () => ({
    data: {
      items: [
        { id: "o1", name: "Acme Bio", org_type: "pharma_partner", is_active: true },
        { id: "o2", name: "Globex CRO", org_type: "cro", is_active: false },
      ],
      next_cursor: null,
    },
    isLoading: false,
    isError: false,
  }),
}));

// Stub DataGrid to render row names so we can assert data flow without ag-grid in jsdom.
vi.mock("@/shared/components/data-grid/data-grid", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  DataGrid: ({ rowData }: any) => (
    <div data-testid="grid">{rowData?.map((r: any) => <div key={r.id}>{r.name}</div>)}</div>
  ),
}));

import { OrganizationListPage } from "./organization-list";

describe("OrganizationListPage", () => {
  it("renders organization names from the hook into the grid", () => {
    render(<OrganizationListPage />);
    expect(screen.getByText("Acme Bio")).toBeInTheDocument();
    expect(screen.getByText("Globex CRO")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run the gate** — `pnpm test`, `pnpm exec tsc --noEmit`, `pnpm lint`. All green.

- [ ] **Step 6: Commit**

```bash
git add src/features/workspace-config/components/organization-columns.tsx src/features/workspace-config/components/organization-list.tsx src/features/workspace-config/components/organization-list.test.tsx "src/app/(dashboard)/admin/organizations/page.tsx"
git commit -m "feat(frontend): organization list page (grid, include-inactive toggle, cursor pagination, New Organization) + route"
```

---

## Task 4: Organization detail page and route

**Files:**
- Create: `src/features/workspace-config/components/organization-detail.tsx`
- Test: `src/features/workspace-config/components/organization-detail.test.tsx`
- Create: `src/app/(dashboard)/admin/organizations/[id]/page.tsx`

**Interfaces:**
- Consumes: `useOrganization` (T1); `ORG_TYPE_LABELS`, `Organization` (T1); `OrganizationFormDialog` (T2); `Card*`, `Badge`, `Button`, `Skeleton`.
- Produces: `OrganizationDetailPage` with props `{ organizationId: string }`.

Mirror `strain-detail.tsx`: `DetailSkeleton`, `MetadataRow`, error/not-found, header with Edit button, metadata `<dl>`, edit dialog. Metadata rows: Type (Badge), Status (Active/Inactive Badge), Contact name, Contact email (as `mailto:` link when present), Notes, and a muted footer with workspace id + version.

- [ ] **Step 1: Write the failing test**

```tsx
// organization-detail.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const org = {
  id: "o1",
  workspace_id: "w1",
  name: "Acme Bio",
  org_type: "pharma_partner",
  contact_name: "Jane Doe",
  contact_email: "jane@acme.com",
  notes: "Primary partner",
  is_active: true,
  version: 3,
};

vi.mock("../hooks/use-organizations", () => ({
  useOrganization: () => ({ data: org, isLoading: false, isError: false }),
  useCreateOrganization: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateOrganization: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { OrganizationDetailPage } from "./organization-detail";

describe("OrganizationDetailPage", () => {
  it("renders the organization name and a mailto link for the contact email", () => {
    render(<OrganizationDetailPage organizationId="o1" />);
    expect(screen.getByRole("heading", { name: "Acme Bio" })).toBeInTheDocument();
    const mail = screen.getByRole("link", { name: /jane@acme\.com/i });
    expect(mail).toHaveAttribute("href", "mailto:jane@acme.com");
  });
});
```

- [ ] **Step 2: Run it — expect FAIL.** `pnpm test organization-detail`.

- [ ] **Step 3: Implement the detail page** (mirror `strain-detail.tsx`; use `Building2` icon; metadata rows below).

```tsx
// organization-detail.tsx  (key body — mirror strain-detail.tsx scaffolding for skeleton/not-found)
"use client";

import { Building2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";

import { useOrganization } from "../hooks/use-organizations";
import { ORG_TYPE_LABELS } from "../types";
import { OrganizationFormDialog } from "./organization-form-dialog";

function MetadataRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[10rem_1fr] gap-2 py-1.5 border-b border-border/50 last:border-0">
      <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wide self-start pt-0.5">
        {label}
      </dt>
      <dd className="text-sm text-foreground leading-relaxed">{children}</dd>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-label="Loading organization detail">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  );
}

export interface OrganizationDetailPageProps {
  organizationId: string;
}

export function OrganizationDetailPage({ organizationId }: OrganizationDetailPageProps) {
  const { data: org, isLoading, isError } = useOrganization(organizationId);
  const [editOpen, setEditOpen] = useState(false);

  if (isLoading) return <DetailSkeleton />;

  if (isError || !org) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <Building2 className="h-12 w-12 opacity-25" aria-hidden="true" />
        <div>
          <p className="text-base font-semibold text-foreground">Organization not found</p>
          <p className="text-sm mt-1">
            No organization with ID <span className="font-mono">{organizationId}</span> could be located.
          </p>
        </div>
        <Link href="/admin/organizations" className="text-sm text-primary underline-offset-4 hover:underline">
          Back to organizations
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 pb-16">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{org.name}</h1>
          <Badge variant="secondary">{ORG_TYPE_LABELS[org.org_type]}</Badge>
          <Badge variant={org.is_active ? "default" : "secondary"}>
            {org.is_active ? "Active" : "Inactive"}
          </Badge>
          <Button type="button" variant="outline" size="sm" className="ml-auto" onClick={() => setEditOpen(true)}>
            Edit
          </Button>
        </div>
      </header>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold text-foreground">Organization Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col">
            <MetadataRow label="Type">{ORG_TYPE_LABELS[org.org_type]}</MetadataRow>
            <MetadataRow label="Status">{org.is_active ? "Active" : "Inactive"}</MetadataRow>
            {org.contact_name && <MetadataRow label="Contact">{org.contact_name}</MetadataRow>}
            {org.contact_email && (
              <MetadataRow label="Email">
                <a
                  href={`mailto:${org.contact_email}`}
                  className="text-primary underline-offset-2 hover:underline"
                >
                  {org.contact_email}
                </a>
              </MetadataRow>
            )}
            {org.notes && (
              <MetadataRow label="Notes">
                <span className="whitespace-pre-wrap">{org.notes}</span>
              </MetadataRow>
            )}
            <MetadataRow label="Workspace">
              <span className="font-mono text-xs">{org.workspace_id}</span>
            </MetadataRow>
            <MetadataRow label="Version">
              <span className="font-mono text-xs">{org.version}</span>
            </MetadataRow>
          </dl>
        </CardContent>
      </Card>

      <OrganizationFormDialog organization={org} open={editOpen} onOpenChange={setEditOpen} />
    </div>
  );
}
```

- [ ] **Step 4: Write the route**

```tsx
// src/app/(dashboard)/admin/organizations/[id]/page.tsx
import { OrganizationDetailPage } from "@/features/workspace-config";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <OrganizationDetailPage organizationId={id} />;
}
```

- [ ] **Step 5: Run the gate** — `pnpm test`, `pnpm exec tsc --noEmit`, `pnpm lint`. Green.

- [ ] **Step 6: Commit**

```bash
git add src/features/workspace-config/components/organization-detail.tsx src/features/workspace-config/components/organization-detail.test.tsx "src/app/(dashboard)/admin/organizations/[id]/page.tsx"
git commit -m "feat(frontend): organization detail page (metadata, mailto, edit dialog) + route"
```

---

## Task 5: Barrel export + green gate

**Files:**
- Create: `src/features/workspace-config/index.ts`
- Verify: `src/shared/lib/navigation.ts` (already wired — read-only check)

- [ ] **Step 1: Write the barrel**

```typescript
// src/features/workspace-config/index.ts
// Types & label maps
export type {
  Organization,
  OrganizationFormValues,
  OrganizationListFilters,
  OrganizationType,
} from "./types";
export { ORG_TYPE_LABELS } from "./types";

// Hooks
export {
  useCreateOrganization,
  useOrganization,
  useOrganizations,
  useUpdateOrganization,
} from "./hooks/use-organizations";

// Components
export { OrganizationFormDialog } from "./components/organization-form-dialog";
export { OrganizationListPage } from "./components/organization-list";
export { OrganizationDetailPage } from "./components/organization-detail";
```

- [ ] **Step 2: Confirm nav resolves.** Read `src/shared/lib/navigation.ts` and verify the "Administration → Organizations" item points at `/admin/organizations` (it does, from Plan 0). No edit needed — if the href is wrong, fix it to `/admin/organizations`.

- [ ] **Step 3: Full green gate**

Run all and confirm output:
- `pnpm lint` → exit 0 (≤8 pre-existing data-grid warnings only)
- `pnpm exec tsc --noEmit` → exit 0
- `pnpm test` → all green (new files: `use-organizations.test.ts`, `organization-form-dialog.test.tsx`, `organization-list.test.tsx`, `organization-detail.test.tsx`)
- `pnpm build` → success; route manifest includes `/admin/organizations` and `/admin/organizations/[id]`

- [ ] **Step 4: Route smoke (optional, if a dev server is available)**

With the stack running (`make dev`), confirm `/admin/organizations` and a detail route return 200 (or the auth-redirect to `/login` if unauthenticated — both acceptable; a 404 is a failure).

- [ ] **Step 5: Commit**

```bash
git add src/features/workspace-config/index.ts
git commit -m "feat(frontend): workspace-config barrel; Plan 4 (Organizations admin) green gate"
```

---

## Self-Review (run before handing off)

**Spec coverage** (`docs/.../2026-06-19-prot-cellar-frontend-design.md`): line 256 "Workspace Config / Admin — organizations admin CRUD" → T1–T5; line 221 "Administration → Organizations (`/admin/organizations`)" → T3/T4 routes + T5 nav check; line 168 "Organizations | workspace config | admin CRUD" → full CRUD-minus-delete. Audit (`/admin/audit`, line 257) is explicitly **out of scope** — Plan 5, blocked on missing backend audit endpoints.

**Placeholder scan:** every code step contains complete code; no TBD/TODO. The only deferred items are documented tracked debt (no deactivate control; no frontend admin guard).

**Type consistency:** mutation update vars use `{ orgId, data }` consistently (matches generated `useUpdateOrganizationApiV1OrganizationsOrgIdPatch` + the `getGet…QueryKey(orgId)` param). `Organization = OrganizationResponse` used uniformly. `OrganizationFormDialog` prop is `organization?` (edit-mode trigger) in T2, T3, and T4. `org_type` is a controlled Select bound to the zod `z.enum(ORG_TYPE_VALUES)`.

## Tracked debt (carry into the SDD ledger)

1. **No deactivate/reactivate control** — `is_active` is response-only; neither create nor update body carries it. Backend gap; revisit if/when an endpoint is added.
2. **No frontend admin pre-gate** — org CRUD relies on backend `require_admin` + the global 403 error toast (mirrors strain editor-gating). Revisit if `useAuthz` later exposes roles.
3. **`data.items as any[]`** narrowing cast in the list (codebase-wide pattern, disclosed).
