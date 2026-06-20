# Protein Rich-Data Viewer — Design (Sub-project 3 of 3)

**Goal:** Make the captured UniProt richness **visible** on the protein detail page (`/proteins/[accession]`): function / cofactor / subcellular-location text, the **subcellular-location diagram**, the **GO graph**, sequence **features**, **keywords**, **citations**, and an embedded **3D structure viewer**. This is the visible payoff of the whole "can we have those?" program — pieces 1 & 2 made the data captured + queryable; this surfaces it.

**Context:** Next.js 16 App Router (RSC), React 19, TypeScript, Tailwind 4, Radix UI primitives (`shared/components/ui/`), react-query via **orval-generated** hooks from `openapi.json`, feature-sliced under `src/features/`. The detail page already exists — `src/features/protein-catalog/components/protein-detail.tsx` (header + badges, metadata card, `<SequenceViewer>`, `<CrossReferenceLinks>`). We **enhance** it by composing new section components; we don't rebuild it.

**Prerequisite (blocking):** the generated `ProteinResponse` is stale — it lacks the fields the backend now returns (`features`, `comments`, `isoforms`, `keyword_refs`, `citations`, and the enriched `protein_names.short_names`/`ec_numbers`). **Step 0 of the plan: regenerate `openapi.json` from the backend app, then run `pnpm generate:api` (orval)** so the DTOs carry the rich fields. Everything else consumes the regenerated types.

**Non-goals:** GO subtree-filter UI in the *list* page (the backend filter exists; a list-filter UI can come later); editing rich data; server-side rendering of the external embeds.

---

## Decomposition (the plan builds in this order)

**Piece 3a — data sections (no external embeds).** Highest value, lowest risk; just renders already-fetched data.
**Piece 3b — visual embeds.** GO graph, subcellular diagram, 3D structure — external widgets.

## Architecture

All new pieces are small section components under `src/features/protein-catalog/components/sections/`, each taking the typed `Protein` and rendering a `<Card>` (or returning `null` when its data is absent). `protein-detail.tsx` composes them in a two-column responsive layout (main column: function/features/structures; side column: GO, location, keywords, citations). No new data fetching for 3a (everything is on the `Protein` from `useProtein`); 3b embeds fetch from external services client-side.

A typed view-model in `features/protein-catalog/lib/protein-annotations.ts` groups the raw arrays for display: `commentsByType(protein)`, `goTermsByAspect(protein)` (split GO cross-refs by `C:`/`F:`/`P:` prefix in `properties.GoTerm`), `structures(protein)` (PDB/AlphaFold/EMDB cross-refs with method/resolution), `featuresByCategory(protein)`. Unit-tested pure functions.

## Components

**3a (data):**
- `FunctionSection` — `FUNCTION`, `CATALYTIC ACTIVITY`, `COFACTOR`, `PATHWAY`, `SUBUNIT`, `INDUCTION`, `DISRUPTION PHENOTYPE` comments → labelled text blocks (structured payloads like catalytic `reaction` rendered as a sub-line).
- `FeaturesSection` — a compact table of `features` (type, position `start..end`, description), grouped by category; long lists collapsible.
- `GoTermsSection` — GO cross-refs grouped by aspect (Function / Process / Component), each a chip linking to QuickGO. (Graph added in 3b.)
- `KeywordsSection` — `keyword_refs` as badges grouped by category.
- `CitationsSection` — `citations` (title, journal, authors, year) with PubMed/DOI links; collapsible.
- `IsoformsSection` — only when `isoforms` present.
- EC numbers + short names folded into the existing header/names area.

**3b (embeds):**
- `GoGraphCard` — embeds QuickGO's graph image: `https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{comma-ids}/chart` as an `<img>` (with a link out to the interactive QuickGO view). Simple, no JS dep.
- `SubcellularLocationCard` — Swiss-BioPics cell diagram. Investigate the `<sib-swissbiopics-sl>` web component (loaded via CDN script in a client component) keyed on the SUBCELLULAR LOCATION terms; fallback to the location text + a link if the component can't be wired cleanly.
- `StructureViewerCard` — embeds **PDBe Mol\*** (`pdbe-molstar` web component via CDN) showing the first PDB id from `structures`; a selector lists the other PDB ids; when no PDB, show the AlphaFold model (`AlphaFoldDB` xref) via its Mol\* embed. Loaded only in a client component, after mount.

## Data flow

`useProtein(accession)` already returns the full `ProteinResponse`. After regen it carries the rich arrays. Section components receive `protein` and read their slice; the view-model functions do the grouping. The GO graph + structure embeds derive their ids from `protein.cross_references`; the subcellular diagram from the `SUBCELLULAR LOCATION` comment. No new backend calls for the detail page.

## Error handling / resilience

- Each section returns `null` when its data is empty → no empty cards.
- External embeds (3b) are isolated in client components with their own load/error states; a failed embed shows a graceful fallback (link out) and never breaks the page (error boundary around each embed).
- The page renders fully from `useProtein` even if every embed fails.

## Testing (vitest + RTL, mirroring `protein-detail.test.tsx`)

- View-model functions: unit tests on `commentsByType` / `goTermsByAspect` / `structures` / `featuresByCategory` with representative `Protein` fixtures.
- Sections: render with a mocked `useProtein` returning a rich fixture; assert function text, a feature row, GO chips, keyword badges, a citation link appear; assert empty-data → section absent.
- Embeds (3b): mock the external widgets (don't load real CDNs in jsdom) and assert the right ids are passed + the fallback renders on error. Follow the existing pattern of mocking heavy components (as `DataGrid` is mocked).

## Rollout sequence (for the plan)

1. **Regen**: dump `openapi.json` from the backend app; `pnpm generate:api`; widen the `Protein` feature type to include the rich arrays; verify `pnpm test` + typecheck green.
2. View-model `protein-annotations.ts` + tests.
3. `FunctionSection` + `FeaturesSection` + compose into `protein-detail.tsx` (two-column layout) + tests.
4. `GoTermsSection` + `KeywordsSection` + `CitationsSection` + `IsoformsSection` + tests.
5. (3b) `GoGraphCard` (QuickGO image) + test.
6. (3b) `StructureViewerCard` (pdbe-molstar) + test.
7. (3b) `SubcellularLocationCard` (Swiss-BioPics, with text fallback) + test.
