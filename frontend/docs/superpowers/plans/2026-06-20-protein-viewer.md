# Protein Rich-Data Viewer — Implementation Plan (Sub-project 3 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline) + TDD. Steps use `- [ ]`.

**Goal:** Surface the captured UniProt richness on `/proteins/[accession]` — function/cofactor text, sequence features, GO terms (+graph), keywords, citations, subcellular-location diagram, and a 3D structure viewer. Spec: `../specs/2026-06-20-protein-viewer-design.md`.

**Architecture:** Enhance the existing `protein-detail.tsx` by composing small section components (`components/sections/`), each taking the typed `Protein` and rendering a `<Card>` or `null`. A pure view-model (`lib/protein-annotations.ts`) groups the raw arrays. 3a = data sections (no network); 3b = external embeds (QuickGO image, pdbe-molstar, Swiss-BioPics), each isolated in a client component with a graceful fallback.

**Tech Stack:** Next.js 16 / React 19 / TS / Tailwind 4 / Radix UI primitives (`shared/components/ui/`) / react-query (orval). Tests: vitest + RTL (`pnpm test`), lint `biome check src/`, typecheck `pnpm exec tsc --noEmit`.

## Global Constraints

- Commit per task on `feat/frontend`; messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Each task ends green: `pnpm test` + `pnpm exec tsc --noEmit` + `biome check src/`.
- Each section component returns `null` when its slice is empty (no empty cards). Mirror `protein-detail.test.tsx` mocking patterns.
- Regenerate the API client (`backend: python -m protcellar.scripts.export_openapi` → `frontend: pnpm generate:api`) whenever backend DTOs change.

---

## Task 1: Regenerate API client + widen Protein type  ✅ DONE

> Status: GREEN. Added `backend/.../scripts/export_openapi.py` (dumps `app.openapi()` → `frontend/openapi.json`, 20 paths). Ran `pnpm generate:api`; `ProteinResponse` now carries `features`/`comments`/`isoforms`/`keyword_refs`/`citations`; widened `Protein.protein_names` with `short_names`/`ec_numbers`. typecheck clean; 62 tests pass.

## Task 2: View-model `protein-annotations.ts` (+ tests)  ✅ DONE

> Status: GREEN. `commentsByType` / `goTermsByAspect` (parses `GoTerm` → aspect+name+evidence) / `structures` (PDB/AlphaFoldDB/EMDB with method/resolution/chains) / `featuresByCategory` (feature_type → category map). Confirmed DTO shapes: `CommentResponse{comment_type,text,payload,evidence}`, `FeatureResponse{feature_type,start,end,description,...}`, `ProteinXrefResponse{database,accession,curie,url,properties}`. 5 tests; tsc/biome clean.

**Files:** create `src/features/protein-catalog/lib/protein-annotations.ts`, `...lib/protein-annotations.test.ts`.

**Produces (confirm exact field names against the generated `ProteinResponseCommentsItem`/`...FeaturesItem`/`...KeywordRefsItem`/`...CitationsItem` first):**
- `commentsByType(p): Record<string, Comment[]>` — index comments by `comment_type`.
- `goTermsByAspect(p): { F: GoRef[]; P: GoRef[]; C: GoRef[] }` — GO cross-refs (`database === "GO"`) split on the `properties.GoTerm` prefix (`F:`/`P:`/`C:`); ids in `accession`.
- `structures(p): { pdb: XRef[]; alphafold: XRef[]; emdb: XRef[] }` — cross-refs by structure DB.
- `featuresByCategory(p): Record<string, Feature[]>` — group features by a category map of `feature.type`.

- [ ] Confirm generated field names (read `src/shared/lib/api/model/proteinResponse*.ts` + the items).
- [ ] Write failing tests with a rich `Protein` fixture (asserts each grouping).
- [ ] Run `pnpm test protein-annotations` → fail.
- [ ] Implement the pure functions.
- [ ] Green + tsc + biome.
- [ ] Commit `feat(protein-viewer): annotation view-model (comments/GO/structures/features)`.

## Task 3: FunctionSection + FeaturesSection + compose page (+ tests)  ✅ DONE

> Status: GREEN. `FunctionSection` (FUNCTION/CATALYTIC ACTIVITY/COFACTOR/… comment groups; `commentLines` extracts text + reaction.name + cofactor names) and `FeaturesSection` (features grouped by category, capped at 15/category). `protein-detail.tsx` restructured into a responsive two-column layout (`lg:grid-cols-[2fr_1fr]`): main = Function/Features/Sequence, side = Metadata; cross-refs full-width. 73 tests; tsc/biome clean. Note: tooling via `./node_modules/.bin/{vitest,tsc,biome}` (the `pnpm exec` deps-check is flaky in this env).

**Files:** create `components/sections/function-section.tsx`, `components/sections/features-section.tsx`; modify `components/protein-detail.tsx` (two-column layout, compose sections); tests `components/sections/*.test.tsx`.

- `FunctionSection` — renders `FUNCTION`, `CATALYTIC ACTIVITY`, `COFACTOR`, `PATHWAY`, `SUBUNIT`, `INDUCTION`, `DISRUPTION PHENOTYPE` comment groups as labelled `<Card>` blocks; `null` if none.
- `FeaturesSection` — compact table (type · `start..end` · description) grouped by category; collapse groups over ~10 rows; `null` if none.

- [ ] Failing tests: rich fixture → function text + a feature row render; empty fixture → sections absent.
- [ ] Run → fail. Implement. Green.
- [ ] Compose both into `protein-detail.tsx` (responsive two-column: `lg:grid-cols-[2fr_1fr]`). Keep existing metadata/sequence/xref blocks.
- [ ] Update `protein-detail.test.tsx` if layout assertions shift; full `pnpm test` + tsc + biome.
- [ ] Commit `feat(protein-viewer): function + features sections, two-column detail layout`.

## Task 4: GoTermsSection + KeywordsSection + CitationsSection + IsoformsSection (+ tests)  ✅ DONE

> Status: GREEN. Side-column sections: `GoTermsSection` (aspect-grouped chips linking to QuickGO), `KeywordsSection` (named keyword badges), `CitationsSection` (title/journal/year + PubMed/DOI links, capped 5), `IsoformsSection` (accession/name/canonical/note). Composed into the side column; removed the redundant raw-keyword row from MetadataCard. 78 tests; tsc/biome clean.

**Files:** create `components/sections/{go-terms,keywords,citations,isoforms}-section.tsx` + tests; compose into `protein-detail.tsx` (side column).

- `GoTermsSection` — three aspect groups (Function/Process/Component); each term a `<Badge asChild>` link to `https://www.ebi.ac.uk/QuickGO/term/{id}`.
- `KeywordsSection` — `keyword_refs` as `<Badge>`s (group by category if present).
- `CitationsSection` — list (title, journal·year, authors trimmed) with PubMed (`pubmed_id`) + DOI links; collapse over ~5.
- `IsoformsSection` — table of `isoforms` (name, id, sequence description); `null` if none.

- [ ] Failing tests (one per section: rich → renders; empty → absent). Implement. Green.
- [ ] Compose into the side column; full `pnpm test` + tsc + biome.
- [ ] Commit `feat(protein-viewer): GO terms, keywords, citations, isoforms sections`.

## Task 5 (3b): GoGraphCard — QuickGO graph image (+ test)  ✅ DONE

> Status: GREEN. Client component renders the QuickGO chart image (`.../ontology/go/terms/{ids}/chart`, capped 12 ids) with an `onError` → "View on QuickGO" fallback; `null` when no GO ids. Composed into the main column. 81 tests; tsc/biome clean. (Plain `<img>` — biome has no `noImgElement` rule; next/image is wrong for an external dynamic chart.)

**Files:** create `components/sections/go-graph-card.tsx` + test.

- Client component. Builds `https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{ids}/chart?...` from the protein's GO ids (cap ~12 for readability) → `<img>` with `onError` → fallback (text "graph unavailable" + link to QuickGO). `null` if no GO ids.

- [ ] Failing test: rich fixture → `<img>` with the joined ids in `src`; simulate `onError` → fallback link. Implement. Green + tsc + biome.
- [ ] Commit `feat(protein-viewer): GO graph (QuickGO) card`.

## Task 6 (3b): StructureViewerCard — pdbe-molstar (+ test)

**Files:** create `components/sections/structure-viewer-card.tsx` + test; possibly `shared/components/structure/` if reused.

- Client component, mount-gated. Loads the `pdbe-molstar` web component (CDN `<script>`/`<link>` injected once on mount); renders `<pdbe-molstar molecule-id={firstPdbId}>`; a `<Select>` switches PDB ids from `structures(p).pdb`. No PDB → AlphaFold model from `structures(p).alphafold` (its Mol\* embed) → else `null`. Error boundary + fallback list of structure links.

- [ ] Failing test: mock the web component (don't load the CDN in jsdom) → assert the first PDB id is passed + the id `<Select>` lists all; no-structure fixture → card absent. Implement. Green + tsc + biome.
- [ ] Commit `feat(protein-viewer): 3D structure viewer (pdbe-molstar) card`.

## Task 7 (3b): SubcellularLocationCard — Swiss-BioPics (+ test)

**Files:** create `components/sections/subcellular-location-card.tsx` + test.

- Client component. From the `SUBCELLULAR LOCATION` comment: render the location text always; attempt the `<sib-swissbiopics-sl>` web component (CDN-loaded) keyed on the GO cellular-component ids; if the component can't initialise, the text + a UniProt link remain (graceful degradation). `null` if no location comment.

- [ ] Failing test: location fixture → location text renders; no-location → absent; web component mocked. Implement. Green + tsc + biome.
- [ ] Commit `feat(protein-viewer): subcellular-location diagram (Swiss-BioPics) card`.

## Self-review
- Spec coverage: regen→T1; view-model→T2; function/features→T3; GO/keywords/citations/isoforms→T4; GO graph→T5; structure→T6; subcellular→T7. ✓
- Field names: T2 step 1 confirms exact generated names before coding (avoids guessing comment/feature shapes). ✓
- Resilience: every section `null`-guards; every 3b embed has a fallback. ✓
