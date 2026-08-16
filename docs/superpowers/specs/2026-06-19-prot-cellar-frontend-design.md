# prot-cellar Frontend — Design & Scope (v1)

**Status:** Approved for planning
**Date:** 2026-06-19
**Author:** Brainstorming session (Claude Code + sidx)
**Depends on:** `2026-06-18-prot-cellar-design.md` (backend), now feature-complete on `feat/foundation`.

---

## 1. Purpose & Vision

Build the **Next.js frontend** for prot-cellar — the biology-side console for browsing and
curating organisms, strains, proteomes, genes, proteins, and drug targets. It is the
**sibling** of chem-cellar's frontend (`~/workspace/chem-vault2/frontend`): same stack, same
auth, same workspace model, same feature-sliced architecture. The two apps should feel like
one product family while remaining instantly distinguishable.

chem-cellar's frontend is the **normative reference**. This spec records where prot-cellar
mirrors it, where it diverges (bio domain, bio accent), and what chemistry-specific machinery
is deliberately dropped.

### Decisions locked in brainstorming

1. **Design identity** — *sibling look, bio accent*: reuse chem-cellar's design-token system,
   layout shell, fonts, and shadcn primitives, but shift the primary color from chem's blue to
   a biology teal/emerald and use bio iconography.
2. **v1 scope** — *all built backend contexts*: Taxonomy (organisms, strains, proteomes),
   Protein Catalog (proteins, genes), Target (targets), plus Dashboard, Admin (organizations),
   and Audit.
3. **Build cadence** — *checkpoint per context*: scaffold + shared foundation first, then one
   plan per context, each landing green (lint + tests) before the next.
4. **Approach** — *fresh scaffold, port the shared foundation, build features from scratch*
   (not copy-and-prune chem-cellar wholesale).

---

## 2. Approach

Create a clean Next 16 app under `prot-cellar/frontend/`. **Port only chem-cellar's shared
plumbing** — auth wiring, API client, providers, layout shell, ui primitives, design tokens
(retuned to a bio accent), navigation/toast/utils helpers. **Write every feature slice fresh**
against the prot-cellar domain.

Rejected alternative — *copy chem-cellar's `frontend/` wholesale and prune*: faster to a
running shell, but drags chemistry dependencies (RDKit, Ketcher, plotly), dead
screening/SAR/registration code, and chemistry-tuned types into a biology app. That violates
the "clean code, properly architected" requirement.

---

## 3. Architecture — feature-sliced (mirrors chem-cellar)

```
prot-cellar/frontend/
  src/app/
    layout.tsx                       # ThemeProvider → AuthProvider → QueryProvider;
                                     #   IBM Plex Sans/Mono; <Toaster/>, <CommandPalette/>
    globals.css                      # Tailwind 4 theme tokens (OKLch), light/dark
    (dashboard)/
      layout.tsx                     # useAuthz() guard → SidebarProvider + AppSidebar + Header
      page.tsx                       # Dashboard
      proteins/    [page, [accession]]
      genes/       [page, [id]]
      targets/     [page, [id], new/edit]
      organisms/   [page, [id]]
      strains/     [page, [id], new/edit]
      proteomes/   [page, [id]]
      admin/organizations/  admin/audit/
    login/                           # Sentinel IdP buttons + animated background
    auth/callback/                   # AuthzCallback (workspace selection)
    api/auth/mint/                   # BFF: mint Sentinel token (service key never exposed)
    api/config/                      # runtime config (base URLs, build identity)
  src/features/<context>/
    components/  hooks/  types/  lib/  index.ts   # barrel; one feature = one bounded context
  src/shared/
    components/{ui, layout, data-grid, sequence, xrefs, common}
    lib/{api, auth, stores, utils, navigation.ts, toast.ts}
    providers/   hooks/   types/
  tests/   vitest.config.ts   vitest.setup.ts
  biome.json  orval.config.ts  next.config.ts  components.json  Dockerfile  package.json
```

**Feature ↔ context map:** `protein-catalog` (proteins, genes), `target` (targets),
`taxonomy` (organisms, strains, proteomes), `workspace-config` (organizations), `audit`,
`dashboard`.

**Layering (mirrors chem-cellar):** `app/` routes are thin; they compose feature components.
Features own their domain UI, hooks, and types and never import each other's internals (only
via the barrel `index.ts`). `shared/` holds cross-cutting plumbing depended on by all features.

---

## 4. Stack & tooling

Identical to chem-cellar unless noted.

| Concern | Choice |
|---|---|
| Framework | Next 16 (App Router, `output: "standalone"`), React 19, TypeScript strict |
| Styling | Tailwind 4 + OKLch CSS variables; shadcn (new-york, base zinc) + radix-ui |
| Data | TanStack Query v5; **orval** generates hooks+types from OpenAPI |
| Auth | `@duar-auth/{js,react,nextjs}` 0.11; runtime `/api/config` + BFF `/api/auth/mint` |
| Tables | ag-grid via a `DataGrid` wrapper; `@tanstack/react-virtual` where needed |
| Forms | react-hook-form + zod (`@hookform/resolvers`) |
| State | zustand (UI/view prefs); server state is TanStack Query |
| Toasts | sonner, wrapped by `shared/lib/toast.ts` (`showSuccess/showError/showInfo`) |
| Icons | lucide-react + @tabler/icons-react |
| Lint/format | biome (2-space, 100 cols); ignores `lib/api/` (generated) + `ui/` (shadcn) |
| Tests | vitest + @testing-library/react (jsdom) |
| Fonts | IBM Plex Sans (`--font-sans`), IBM Plex Mono (`--font-mono`) |

**Dropped from chem-cellar (chemistry-only):** `@rdkit/rdkit`, `ketcher-*`, `plotly.js` /
`react-plotly.js`, and the screening/SAR/chemical-registration features and their deps. The
`next.config.ts` `fs`-stub alias (an RDKit workaround) is therefore also dropped.

**orval input:** `http://localhost:8001/openapi.json` (prot-cellar dev server runs on **8001**;
chem-cellar uses 8000). Output: `src/shared/lib/api/endpoints.ts` (tags-split react-query hooks)
+ `src/shared/lib/api/model/` (types), via the `customInstance` mutator.

---

## 5. Design system — sibling look, bio accent

Keep chem-cellar's entire token structure (OKLch, light/dark with default dark, radius scale
sm/md/lg/xl, sidebar token set, IBM Plex fonts). The single intentional change is **hue**:

- `--primary` shifts from chem's blue (hue ~255) to a **biology teal/emerald** (hue ~165–190),
  keeping comparable lightness/chroma so the UI weight matches its sibling.
- `--success`, `--warning`, `--info`, `--destructive` are retuned to stay clearly
  distinguishable from the green primary (success in particular must not collide with primary).
- Iconography leans bio: lucide `Dna`, `FlaskConical`, `Microscope`, `Network`, `Layers`.

Exact OKLch values are pinned during scaffolding (Plan 0) and reviewed visually; this spec
fixes the *intent*, not the hex.

---

## 6. Bio-specific shared components (the genuinely new UI)

These have no chem-cellar equivalent and are the novel design surface:

- **`SequenceViewer`** (`shared/components/sequence/`) — renders an amino-acid sequence in a
  monospace block with a position ruler, line wrapping, length/mass badges, copy-to-clipboard,
  and FASTA download. The backend content-negotiates `fasta` on `GET /proteins/{accession}`.
- **`CrossReferenceLinks`** (`shared/components/xrefs/`) — renders a `CrossReference[]` as
  resolvable external links. The backend already emits resolved URLs in response DTOs (e.g.
  `ncbi_url`), so this component just presents them grouped by database.
- **`TargetComponentsEditor`** (in the `target` feature) — an ordered list of protein-component
  rows (`protein_id` + `relationship`), enforcing the **single-vs-complex cardinality
  invariant** client-side before submit: `SINGLE_PROTEIN` ⇒ exactly 1; `PROTEIN_COMPLEX` /
  `PROTEIN_FAMILY` / `PROTEIN_PROTEIN_INTERACTION` ⇒ ≥ 2. Mirrors the backend aggregate rule so
  users get immediate feedback; the server remains the source of truth.
- **Organism lineage panel** (in the `taxonomy` feature) — the adjacency-list hierarchy shown
  as a lineage breadcrumb (ancestors) + a direct-children list on the organism detail page. A
  full lazy-loaded taxonomy tree widget is deferred.

---

## 7. Interaction model (per backend tenancy)

The backend splits reference data (shared/global, admin-gated writes) from workspace data
(tenant-scoped, editor writes). The UI follows that split:

| Entity | Tenancy | UI |
|---|---|---|
| Organisms, Proteomes, Genes, Proteins | shared reference | browse + search + detail; edits admin-gated |
| Strains, Targets | workspace-scoped | full CRUD (create/edit dialogs, delete with guard) |
| Organizations | workspace config | admin CRUD |
| Audit | append-only | read-only timeline/table |

List pages use the `DataGrid` (virtualized) for large sets, a search/filter toolbar driven by
the backend's filters, and **cursor (keyset) pagination** via the opaque next-link the API
returns. User view prefs (columns, sort, density) persist to localStorage. Every list and
detail renders explicit **loading skeleton / empty / error** states.

---

## 8. Data flow

```
OpenAPI (8001) --orval--> shared/lib/api/{endpoints.ts, model/}
                              │
        feature hooks/ (query-keys.ts + createCrudHooks() + domain wrappers)
                              │
        feature components/  (lists, details, dialogs)
                              │
   react-hook-form + zod ──submit──> mutation ──> targeted cache invalidation + toast
```

`customInstance` injects the runtime base URL (from `/api/config`) and the Sentinel auth header
on every request, sets JSON content-type (unless `FormData`), returns `undefined` for 204, and
throws `ApiError` carrying FastAPI's `detail` (including structured 422/409 bodies). A global
`MutationCache` error handler surfaces failures via `showError`. Query keys are declared once
per feature in `hooks/query-keys.ts` so invalidation is precise. Orval-widened DTOs are
re-narrowed into domain types in each feature's `types/index.ts` (alias, never duplicate).

---

## 9. Auth & config (ported from chem-cellar)

- Provider stack in root layout: **ThemeProvider → AuthProvider → QueryProvider**.
- `AuthProvider` fetches `/api/config`, calls `setApiBaseUrl()`, then mounts
  `AppConfigProvider` + Sentinel `AuthzProvider`.
- `(dashboard)/layout.tsx` guards with `useAuthz()`: skeleton while loading, redirect to
  `/login` when unauthenticated.
- `/api/auth/mint` is a server route (BFF) that exchanges the IdP token with Sentinel using the
  service key, which is never sent to the browser. `/api/config` reads `APP_*`/`DUAR_*` env
  at request time so one Docker image serves all environments.
- Workspace identity rides in the Sentinel token; `WorkspaceSwitcher` uses `AuthzCallback`.
- Point at the **same identity-service** as chem-cellar (`DUAR_URL=http://localhost:9003`).

---

## 10. Navigation

Single source of truth in `shared/lib/navigation.ts` (drives sidebar + breadcrumbs):

- **Home** — Dashboard (`/`)
- **Catalog** — Proteins (`/proteins`), Genes (`/genes`), Targets (`/targets`)
- **Taxonomy** — Organisms (`/organisms`), Strains (`/strains`), Proteomes (`/proteomes`)
- **Administration** — Organizations (`/admin/organizations`), Audit (`/admin/audit`)

---

## 11. Testing

vitest + @testing-library/react (jsdom), mirroring chem-cellar's setup (ResizeObserver +
storage polyfills). Pragmatic coverage:

- **Unit (pure lib):** sequence formatting/ruler math, target-cardinality validator, cross-ref
  URL grouping, list-param/query-key builders.
- **Component:** the three bio components (`SequenceViewer`, `CrossReferenceLinks`,
  `TargetComponentsEditor`), plus one representative list page and one create/edit dialog per
  context, with API hooks mocked via `vi.mock`.
- biome must pass (`lint`); generated `lib/api/` and shadcn `ui/` are excluded.

E2E (Playwright) is **deferred** to a later pass, consistent with chem-cellar's layering order
(Domain → … → UI → E2E).

---

## 12. Build plan (checkpoint per context)

Each plan lands green (`biome` + `vitest`) and is shown for review before the next.

0. **Scaffold + shared foundation** — Next app, tooling (biome/orval/vitest/Tailwind/shadcn),
   design tokens (bio accent), provider stack, auth + `/api/config` + `/api/auth/mint`, layout
   shell (sidebar/header/nav), `DataGrid`, `customInstance` + `createCrudHooks` + toast, and the
   bio shared components (`SequenceViewer`, `CrossReferenceLinks`). First orval generation
   against the running backend. **Checkpoint.**
1. **Protein Catalog** — proteins (browse/search/detail + `SequenceViewer` + xrefs/FASTA) and
   genes. *(Before Target, which references proteins.)*
2. **Target** — targets list/detail + create/edit with `TargetComponentsEditor` (cardinality
   invariant). Full CRUD (workspace-scoped).
3. **Taxonomy** — organisms (browse/detail + lineage panel), strains (full CRUD), proteomes.
4. **Workspace Config / Admin** — organizations admin CRUD.
5. **Audit + Dashboard** — read-only audit timeline; dashboard summary cards.

Build order rationale: Protein → Target mirrors the backend dependency (targets reference
proteins); taxonomy supplies organism context used across detail pages but its list/detail UI
isn't a hard dependency, so it follows the catalog.

---

## 13. Open items (resolve in plans, not blockers)

1. **Backend availability for orval.** Generation needs the backend running on 8001
   (`make up` + `make dev`). Plan 0 documents the regen workflow; a checked-in
   `openapi.json` snapshot is the fallback for offline generation.
2. **Exact bio palette.** Pin OKLch values in Plan 0 and eyeball light/dark before building
   features.
3. **CommandPalette scope.** Mirror chem-cellar's cmdk palette; seed with navigation +
   entity quick-search in Plan 0, expand per context.
4. **Repo/branch.** Frontend lives in the monorepo at `frontend/`, developed on `feat/frontend`
   (branched from `feat/foundation`).

---

## 14. Out of scope (v1 frontend)

Structure viewers (PDBe-Molstar/Nightingale), sequence-similarity/BLAST UI, typed-annotation
browsers (GO/InterPro/Pfam/EC), pan-proteome features, TDL/tractability facets, version-history
(UniSave) UI, bulk-import UI (the loader calls the API directly), and Playwright E2E. These
track the backend's own "later" list in `2026-06-18-prot-cellar-design.md` §9.
