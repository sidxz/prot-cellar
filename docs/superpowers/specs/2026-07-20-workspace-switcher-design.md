# Workspace Switcher & Login Continuity — Design (ProtCellar port)

**Date:** 2026-07-20
**Status:** Implemented (2026-07-20, workspace-switcher branch)
**Scope:** Frontend only. No backend changes, no new dependencies.
**Origin:** `chem-vault2/docs/superpowers/specs/2026-07-20-workspace-switcher-design.md` —
implemented, reviewed, and runtime-verified (16/16 E2E) in chem-vault2 today. This spec
records only the ProtCellar deltas; rationale lives in the origin spec.

## Problem

ProtCellar has no way to switch workspaces. Its previous switcher was removed in commit
`13a45bd` ("static ProtCellar brand block; remove user menu, About dialog, dead
workspace switcher") for the same root cause as chem-vault2's: the Sentinel authz-mode
SDK keeps the IdP token memory-only, so a stored-credential switcher could never list
workspaces nor re-mint. Separately, multi-workspace users see the workspace picker on
every interactive login.

## What we adopt (daikon/chem-vault2 parity)

1. **Last-workspace memory** — app-owned localStorage key that survives logout and
   auto-skips the login picker while it points at a workspace the user can still access.
2. **"Switch workspace" affordance** — header avatar dropdown item that clears that
   memory and logs out; the next login shows the picker again.

**Out of scope: an in-place switcher** — same reasons as the origin spec (short-lived
memory-only IdP token; mid-session re-mint swaps the authz token under other open tabs).

**Refresh continuity needs no work** — same SDK (`@sentinel-auth/*` 0.17), silent reauth
re-mints the persisted workspace.

## ProtCellar deltas vs the origin design

- **localStorage key: `pc-last-workspace-id`** — follows this repo's `pc-` kebab
  prefix convention (`pc-genes-filters`, `pc-preferences`, …), not chem-vault2's dotted
  `cellar.lastWorkspaceId`.
- Everything else is structurally identical: same file paths, same component code
  (including the StrictMode auto-select ref guard and the per-browser memory semantics
  note below, both of which came out of chem-vault2's final review).

## Design (same three pieces)

1. **`frontend/src/shared/lib/auth/workspace-memory.ts`** — `rememberedWorkspace()`,
   `rememberWorkspace(id)`, `forgetWorkspace()` over `pc-last-workspace-id`, try/catch
   around storage. The SDK's `sentinel_workspace_id` is wiped by `logout()`, so it
   cannot carry cross-login continuity — surviving logout is the feature.
   - The memory is per-browser, not per-user: on a shared machine the next signer-in
     auto-enters the previous user's remembered workspace if they are also a member
     (the mint always runs against the signer-in's own membership — authorized by
     design). Accepted; parity with daikon and chem-vault2.
2. **Callback picker guard** — `frontend/src/app/auth/callback/workspace-selector.tsx`
   (own file for testability), wired into `page.tsx`'s `workspaceSelector` render prop.
   Auto-selects the remembered workspace when still in the list ("Entering …" state),
   falls back to the existing picker otherwise; manual picks are remembered.
3. **Header user menu** — `frontend/src/shared/components/layout/header.tsx`: avatar +
   name/email cluster becomes a DropdownMenu (label, separator, **Switch workspace** =
   `forgetWorkspace(); logout();`, destructive **Sign out** = `logout()`); the
   standalone sign-out icon button is absorbed.

## Testing

- Vitest component tests: `workspace-selector.test.tsx` (auto-select / stale / none /
  manual-pick-remembers, single-fire assertion) and `header.test.tsx` updated to the
  menu structure (identity, sign-out via menu, switch-workspace forgets key).
- Runtime E2E: chem-vault2's mock-auth Playwright harness adapted to ProtCellar
  (frontend :3001), run by the controller after implementation.

## Files touched

- **New:** `frontend/src/shared/lib/auth/workspace-memory.ts`
- **New:** `frontend/src/app/auth/callback/workspace-selector.tsx`
- **New:** `frontend/src/app/auth/callback/workspace-selector.test.tsx`
- `frontend/src/app/auth/callback/page.tsx`
- `frontend/src/shared/components/layout/header.tsx`
- `frontend/src/shared/components/layout/header.test.tsx`
