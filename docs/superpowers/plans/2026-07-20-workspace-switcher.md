# Workspace Switcher & Login Continuity Implementation Plan (ProtCellar port)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port chem-vault2's workspace switcher + login continuity to ProtCellar: remember the last workspace so login skips the picker, and add a "Switch workspace" item to a new header user menu.

**Architecture:** Frontend-only. Spec: `docs/superpowers/specs/2026-07-20-workspace-switcher-design.md`. The code below is the final, review-hardened chem-vault2 implementation (StrictMode guard included) with one delta: the localStorage key is `pc-last-workspace-id`. ProtCellar's `header.tsx`, `header.test.tsx`, and the callback picker markup are byte-identical to chem-vault2's pre-change versions, so the ported code applies verbatim.

**Tech Stack:** Next.js App Router, React 19, `@duar-auth/nextjs` 0.17 (authz mode), shadcn/ui, Vitest + @testing-library/react, Biome.

## Global Constraints

- **No new dependencies.**
- **localStorage key is exactly** `pc-last-workspace-id`.
- **All frontend commands run from** `/Users/sidx/workspace/prot-cellar/frontend`.
- **Commits:** Conventional Commits; ALWAYS explicit pathspec (`git commit -m "..." -- <paths>`) — never blanket-add. End messages with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **`pnpm lint` passes/fails by exit code** (biome format violations are error-severity).
- **Vitest does not typecheck** (esbuild strips types). `pnpm build` in Task 3 is the type gate.
- **Do NOT restyle the existing picker markup** — it is moved verbatim out of `page.tsx`; only guard logic wraps it.
- `docs/` is tracked normally in this repo (no force-add needed).

---

### Task 1: Workspace memory helper + login picker guard (TDD)

**Files:**
- Create: `frontend/src/shared/lib/auth/workspace-memory.ts`
- Create: `frontend/src/app/auth/callback/workspace-selector.tsx`
- Create: `frontend/src/app/auth/callback/workspace-selector.test.tsx`
- Modify: `frontend/src/app/auth/callback/page.tsx` (import block lines 3–8; render prop lines 62–82)

**Interfaces:**
- Consumes: `AuthzWorkspaceSelectorProps` from `@duar-auth/nextjs` — `{ workspaces: {id,name,slug,role}[]; onSelect: (workspaceId: string) => void; isLoading: boolean }`.
- Produces (Task 2 relies on these exact names): `rememberedWorkspace(): string | null`, `rememberWorkspace(id: string): void`, `forgetWorkspace(): void` from `@/shared/lib/auth/workspace-memory`; `WorkspaceSelector` from `./workspace-selector`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/app/auth/callback/workspace-selector.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import type { AuthzWorkspaceSelectorProps } from "@duar-auth/nextjs";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceSelector } from "./workspace-selector";

// Typed against the SDK prop so role stays valid if WorkspaceRole is a union.
const WORKSPACES: AuthzWorkspaceSelectorProps["workspaces"] = [
  { id: "ws-1", name: "Alpha Lab", slug: "alpha-lab", role: "admin" },
  { id: "ws-2", name: "Beta Lab", slug: "beta-lab", role: "viewer" },
];

const KEY = "pc-last-workspace-id";

describe("WorkspaceSelector", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("auto-selects the remembered workspace and shows an opening state instead of the picker", () => {
    localStorage.setItem(KEY, "ws-2");
    const onSelect = vi.fn();
    render(<WorkspaceSelector workspaces={WORKSPACES} onSelect={onSelect} isLoading={false} />);
    expect(onSelect).toHaveBeenCalledWith("ws-2");
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/entering beta lab/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /alpha lab/i })).not.toBeInTheDocument();
  });

  it("shows the picker when the remembered workspace is no longer in the list", () => {
    localStorage.setItem(KEY, "ws-gone");
    const onSelect = vi.fn();
    render(<WorkspaceSelector workspaces={WORKSPACES} onSelect={onSelect} isLoading={false} />);
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /alpha lab/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /beta lab/i })).toBeInTheDocument();
  });

  it("shows the picker when nothing is remembered", () => {
    const onSelect = vi.fn();
    render(<WorkspaceSelector workspaces={WORKSPACES} onSelect={onSelect} isLoading={false} />);
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /alpha lab/i })).toBeInTheDocument();
  });

  it("remembers a manual pick before selecting it", () => {
    const onSelect = vi.fn();
    render(<WorkspaceSelector workspaces={WORKSPACES} onSelect={onSelect} isLoading={false} />);
    fireEvent.click(screen.getByRole("button", { name: /alpha lab/i }));
    expect(localStorage.getItem(KEY)).toBe("ws-1");
    expect(onSelect).toHaveBeenCalledWith("ws-1");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test workspace-selector`
Expected: FAIL — cannot resolve import `./workspace-selector`.

- [ ] **Step 3: Create the workspace-memory helper**

Create `frontend/src/shared/lib/auth/workspace-memory.ts`:

```ts
// Remembered workspace so interactive logins skip the picker.
// Survives logout on purpose (the SDK's sentinel_workspace_id does not) —
// "Switch workspace" in the header user menu clears it to bring the picker back.
const KEY = "pc-last-workspace-id";

export function rememberedWorkspace(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function rememberWorkspace(id: string): void {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    // storage unavailable (private mode) — picker just shows every time
  }
}

export function forgetWorkspace(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}
```

- [ ] **Step 4: Create the WorkspaceSelector guard component**

Create `frontend/src/app/auth/callback/workspace-selector.tsx`. The picker markup is the existing markup moved verbatim out of `page.tsx` — do not restyle it:

```tsx
"use client";

import type { AuthzWorkspaceSelectorProps } from "@duar-auth/nextjs";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/shared/components/ui/button";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { rememberWorkspace, rememberedWorkspace } from "@/shared/lib/auth/workspace-memory";

type Decision = { kind: "pending" } | { kind: "picker" } | { kind: "auto"; id: string };

export function WorkspaceSelector({ workspaces, onSelect, isLoading }: AuthzWorkspaceSelectorProps) {
  const [decision, setDecision] = useState<Decision>({ kind: "pending" });
  // Dev StrictMode re-runs the mount effect before the decision state is visible;
  // the ref keeps the auto-select mint from firing twice (same pattern as the SDK's
  // own single-workspace auto-select guard).
  const autoFiredRef = useRef(false);

  // Skip the picker when the remembered workspace is still available —
  // "Switch workspace" in the header menu forgets it and brings the picker back.
  // One-time decision made in an effect: localStorage is client-only, so a
  // useState initializer would cause a hydration mismatch.
  useEffect(() => {
    if (decision.kind !== "pending" || isLoading || autoFiredRef.current) return;
    const remembered = rememberedWorkspace();
    if (remembered && workspaces.some((ws) => ws.id === remembered)) {
      autoFiredRef.current = true;
      setDecision({ kind: "auto", id: remembered });
      onSelect(remembered);
    } else {
      setDecision({ kind: "picker" });
    }
  }, [decision.kind, isLoading, workspaces, onSelect]);

  if (decision.kind !== "picker") {
    const ws = decision.kind === "auto" ? workspaces.find((w) => w.id === decision.id) : null;
    return (
      <div>
        <h2 className="text-sm font-medium text-muted-foreground">
          {ws ? `Entering ${ws.name}…` : "Signing in..."}
        </h2>
        <div className="mt-4 space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-sm font-medium text-muted-foreground">Select workspace to continue</h2>
      <div className="mt-4 space-y-2">
        {workspaces.map((ws) => (
          <Button
            key={ws.id}
            variant="outline"
            className="w-full justify-start rounded-[11px]"
            disabled={isLoading}
            onClick={() => {
              rememberWorkspace(ws.id);
              onSelect(ws.id);
            }}
          >
            <span className="truncate">{ws.name}</span>
            <span className="ml-auto text-xs text-muted-foreground">{ws.role}</span>
          </Button>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Wire the component into the callback page**

In `frontend/src/app/auth/callback/page.tsx`, replace the import block (lines 3–8) with:

```tsx
import { ProteinFold } from "@/shared/components/backgrounds/protein-fold";
import { LogoMark } from "@/shared/components/ui/logo-mark";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { AuthzCallback } from "@duar-auth/nextjs";
import { useRouter } from "next/navigation";
import { WorkspaceSelector } from "./workspace-selector";
```

(The `Button` import is removed — it moved into `workspace-selector.tsx`.)

Then replace the whole inline `workspaceSelector` render prop (lines 62–82, from `workspaceSelector={({ workspaces, onSelect, isLoading: selecting }) => (` through its closing `)}`) with:

```tsx
                workspaceSelector={(props) => <WorkspaceSelector {...props} />}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pnpm test workspace-selector`
Expected: PASS — 4 tests.

- [ ] **Step 7: Lint**

Run: `pnpm lint`
Expected: exit code 0. If format errors: `pnpm lint:fix` (never with `--unsafe`), re-run, confirm exit 0.

- [ ] **Step 8: Commit**

```bash
cd /Users/sidx/workspace/prot-cellar
git add frontend/src/shared/lib/auth/workspace-memory.ts frontend/src/app/auth/callback/workspace-selector.tsx frontend/src/app/auth/callback/workspace-selector.test.tsx frontend/src/app/auth/callback/page.tsx
git commit -m "feat(frontend): remember last workspace; auto-skip login picker

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- frontend/src/shared/lib/auth/workspace-memory.ts frontend/src/app/auth/callback/workspace-selector.tsx frontend/src/app/auth/callback/workspace-selector.test.tsx frontend/src/app/auth/callback/page.tsx
```

---

### Task 2: Header user menu with "Switch workspace"

**Files:**
- Modify: `frontend/src/shared/components/layout/header.test.tsx` (currently asserts the standalone logout button)
- Modify: `frontend/src/shared/components/layout/header.tsx` (full rewrite below; currently 68 lines)

**Interfaces:**
- Consumes: `forgetWorkspace()` from `@/shared/lib/auth/workspace-memory` (Task 1); shadcn `dropdown-menu` (already at `frontend/src/shared/components/ui/dropdown-menu.tsx`; its `DropdownMenuItem` supports `variant="destructive"`).
- Produces: nothing consumed later — final chrome change.

- [ ] **Step 1: Update the header test to the new menu structure (RED)**

Replace the entire contents of `frontend/src/shared/components/layout/header.test.tsx` with:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Header } from "./header";

const logoutMock = vi.fn();

vi.mock("@duar-auth/nextjs", () => ({
  useAuthz: () => ({
    user: { name: "Ada Lovelace", email: "ada@example.com" },
    logout: logoutMock,
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

vi.mock("./theme-toggle", () => ({ ThemeToggle: () => null }));
vi.mock("./font-size-control", () => ({ FontSizeControl: () => null }));

function openUserMenu() {
  fireEvent.keyDown(screen.getByRole("button", { name: /account menu/i }), { key: "Enter" });
}

describe("Header", () => {
  beforeEach(() => {
    logoutMock.mockClear();
    localStorage.clear();
  });

  it("shows the signed-in user's identity", () => {
    render(<Header />);
    expect(screen.getByText("AL")).toBeInTheDocument(); // initials
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
  });

  it("signs out via the user menu", () => {
    render(<Header />);
    openUserMenu();
    fireEvent.click(screen.getByRole("menuitem", { name: /sign out/i }));
    expect(logoutMock).toHaveBeenCalled();
  });

  it("Switch workspace forgets the remembered workspace, then logs out", () => {
    localStorage.setItem("pc-last-workspace-id", "ws-1");
    render(<Header />);
    openUserMenu();
    fireEvent.click(screen.getByRole("menuitem", { name: /switch workspace/i }));
    expect(localStorage.getItem("pc-last-workspace-id")).toBeNull();
    expect(logoutMock).toHaveBeenCalled();
  });
});
```

Note: Radix menus don't open on `fireEvent.click`/`pointerDown` under jsdom; the `keyDown` Enter opener is the pattern proven in chem-vault2.

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm test header`
Expected: FAIL — no button named /account menu/ and no menuitems yet.

- [ ] **Step 3: Rewrite header.tsx (GREEN)**

Replace the entire contents of `frontend/src/shared/components/layout/header.tsx` with:

```tsx
"use client";

import { useAuthz } from "@duar-auth/nextjs";
import { Building2, ChevronDown, LogOut, Search } from "lucide-react";

import { Avatar, AvatarFallback } from "@/shared/components/ui/avatar";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Separator } from "@/shared/components/ui/separator";
import { forgetWorkspace } from "@/shared/lib/auth/workspace-memory";
import { useCommandPaletteStore } from "@/shared/lib/stores/command-palette-store";
import { Breadcrumbs } from "./breadcrumbs";
import { FontSizeControl } from "./font-size-control";
import { ThemeToggle } from "./theme-toggle";

export function Header() {
  const { user, logout } = useAuthz();
  const openPalette = useCommandPaletteStore((s) => s.setOpen);

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "?";

  return (
    <header className="flex h-10 shrink-0 items-center gap-2 border-b border-border/60 px-4">
      <Breadcrumbs />
      <div className="ml-auto flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => openPalette(true)}
          className="hidden gap-2 text-muted-foreground md:flex"
        >
          <Search className="size-4" />
          <span className="text-xs">Search</span>
          <kbd className="pointer-events-none ml-1 inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
            <span className="text-xs">&#8984;</span>K
          </kbd>
        </Button>
        <FontSizeControl />
        <ThemeToggle />
        <Separator orientation="vertical" className="mx-1.5 data-[orientation=vertical]:h-5" />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-auto gap-2 px-2 py-1">
              <span className="sr-only">Account menu</span>
              <Avatar className="size-7 rounded-lg">
                <AvatarFallback className="rounded-lg text-xs">{initials}</AvatarFallback>
              </Avatar>
              <div className="hidden flex-col text-left leading-tight sm:flex">
                <span className="text-xs font-medium">{user?.name ?? "User"}</span>
                <span className="text-[10px] text-muted-foreground">{user?.email ?? ""}</span>
              </div>
              <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <p className="truncate text-sm font-medium">{user?.name ?? "User"}</p>
              <p className="truncate text-xs font-normal text-muted-foreground">
                {user?.email ?? ""}
              </p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onSelect={() => {
                // Forget the remembered workspace so the next sign-in shows the picker.
                forgetWorkspace();
                logout();
              }}
            >
              <Building2 />
              Switch workspace
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onSelect={() => logout()}>
              <LogOut />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Run header tests to verify they pass**

Run: `pnpm test header`
Expected: PASS — 3 tests.

- [ ] **Step 5: Lint + full test suite**

Run: `pnpm lint && pnpm test`
Expected: both exit 0; full suite green.

- [ ] **Step 6: Commit**

```bash
cd /Users/sidx/workspace/prot-cellar
git add frontend/src/shared/components/layout/header.tsx frontend/src/shared/components/layout/header.test.tsx
git commit -m "feat(frontend): header user menu with Switch workspace (chem-vault2 parity)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- frontend/src/shared/components/layout/header.tsx frontend/src/shared/components/layout/header.test.tsx
```

---

### Task 3: Type gate, spec sync, runtime verification

**Files:**
- Modify: `docs/superpowers/specs/2026-07-20-workspace-switcher-design.md` (status line)

**Interfaces:**
- Consumes: everything from Tasks 1–2. No new code.

- [ ] **Step 1: Type gate**

Run: `pnpm build`
Expected: build succeeds (only typecheck in this repo). If it fails on files from Tasks 1–2, fix minimally and commit as `fix(frontend): ...` (explicit pathspec). If it fails on unrelated files, stop and report.

- [ ] **Step 2: Sync the spec**

In `docs/superpowers/specs/2026-07-20-workspace-switcher-design.md`, replace:

```markdown
**Status:** Approved (same-day port of the chem-vault2 design)
```

with:

```markdown
**Status:** Implemented (2026-07-20, workspace-switcher branch)
```

- [ ] **Step 3: Commit spec sync**

```bash
cd /Users/sidx/workspace/prot-cellar
git add docs/superpowers/specs/2026-07-20-workspace-switcher-design.md
git commit -m "docs: mark workspace-switcher spec implemented

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -- docs/superpowers/specs/2026-07-20-workspace-switcher-design.md
```

- [ ] **Step 4: Runtime verification (main session)**

From the MAIN session (not a subagent): adapt chem-vault2's mock-auth Playwright harness (Google authorize → crafted id_token echoing nonce; `**/authz/resolve` → two workspaces; `**/api/auth/mint` → crafted authz JWT echoing workspace_id) against ProtCellar dev on **:3001**, key `pc-last-workspace-id`, and check: fresh-login picker → pick → land → reload continuity; re-login auto-skip; Switch workspace → memory cleared → picker returns.
