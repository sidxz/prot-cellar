# Handoff — build Protein Catalog (Phase 2) + Target (Phase 3)

> **Purpose:** orient a fresh session to continue prot-cellar. This is a **map, not a plan** —
> it points at the spec, the built code, and the exemplars to mirror. Do the planning yourself
> (writing-plans) using these references.

## Read first (in order)

1. **Project memory:** `~/.claude/projects/-Users-sidx-workspace-prot-cellar/memory/` (relationship to chem-cellar + current status).
2. **Spec:** `docs/superpowers/specs/2026-06-18-prot-cellar-design.md` — read **§2** (chem-cellar interop seam), **§5.2** (Protein/Gene), **§5.3** (Target/TargetComponent), **§5.5** (CrossReference + identifier registry), **§7** (provenance), **§9** (v1 scope), **§10** (open questions).
3. **Existing plans = the SHAPE to mirror:** `docs/superpowers/plans/2026-06-18-foundation.md` and `…-taxonomy-context.md`.
4. **Ledger (per-task outcomes + tracked debt):** `.git/sdd/progress.md`.
5. **chem-cellar (normative architecture source):** `~/workspace/chem-vault2` (package `cellar`). **Before writing backend code, read its `docs/backend-code-guidelines.md` and `docs/patterns-and-conventions.md`.**

## Current state

- Branch **`feat/foundation`** (NOT merged to main): Foundation + Taxonomy built and green.
  `make test` (30 unit + 2 import-linter contracts) · `make test-api` (16) · `make lint` (ruff+mypy, 110 files).
- Dev infra: `docker compose up` → postgres `127.0.0.1:5433`, valkey `:6380`. `backend/.env` has `DATABASE_URL` + dev Sentinel placeholders.
- 7 tables migrated: organizations, audit_*, organisms, organism_names, strains, proteomes.

## Conventions to mirror (established, verified)

- **Two-pattern tenancy split (security-critical):**
  - *Reference data* (shared) → aggregate sets `workspace_id = GLOBAL_WORKSPACE_ID`; use cases guard `require_admin` only, **no** `require_same_workspace`; reads guard `require_authenticated`; Commands carry **no** `workspace_id`. → **Protein and Gene are reference data** (like Organism/Proteome).
  - *Tenant data* (workspace-scoped) → real `workspace_id`; `require_editor` + `require_same_workspace`; `workspace_id` from `auth.workspace_id` (never body/URL). → **Target is workspace-scoped** (like Strain/Organization).
- **DI split:** `register_<ctx>(container)` lives in `infrastructure/di/_<ctx>.py` (wired into `create_container`); only `*Dep` aliases in `interface/dependencies/_<ctx>.py`. **Routes call use cases, never repositories.**
- **Slice exemplars to copy:**
  - reference slice → copy **Organism** (`domain/taxonomy/organism.py`, `application/taxonomy/*`, `infrastructure/.../taxonomy/organism_repository.py`, `interface/routes/organisms.py`, `infrastructure/di/_taxonomy.py`).
  - workspace-scoped slice → copy **Strain** (`…/strain*`) / **Organization**.
- **Child collections** (Target → TargetComponents) → mirror the Organism `names` pattern (`selectin` + `cascade="all, delete-orphan"`; `_to_model`/`_update_model` replace the collection). The base-repo raw-UPDATE-vs-flush round-trip is **proven safe** (see `test_update_organism_preserves_names`) — but add an analogous round-trip test.
- **Cross-references & IDs:** generic `CrossReference` VO + `infrastructure/identifiers/registry.py` (`validate`, `resolve_url`). Prefixes already seeded: uniprot, ncbitaxon, ncbigene, refseq, ensembl, pdb, interpro, pfam, go, ec, chembl.target, proteome. Validate accessions there; expose resolvable URLs in response DTOs (see `OrganismResponse.ncbi_url`).
- **Provenance + bulk import:** reference aggregates carry inline provenance columns (`source`, `source_release`, `source_record_id` indexed, `source_record_checksum`, `imported_at`) and an **idempotent bulk-upsert** keyed on `(source, source_record_id)` with checksum-skip + `dry_run`. Reuse the **Organism bulk pattern** (`bulk_upsert_organisms.py`).
- **Gotchas:** export `DATABASE_URL` before any `alembic` command; append new model modules to `infrastructure/persistence/sqlalchemy/metadata.py` then inspect autogenerate for **spurious DROPs**; api-test DB is session-shared (use distinct keys per test); **do NOT use `ProvenanceMixin` on a model that also has a `source` enum column** (name clash — add provenance cols inline, see `OrganismModel`); list routes must return `PaginatedResponse(items, next_cursor)`, not a bare list.

## Phase 2 — Protein Catalog (spec §5.2) — *reference data, mirror Organism*

- **Protein** (GLOBAL): `primary_accession` (validate via registry `uniprot`), `secondary_accessions`, `entry_name`, `is_reviewed` (Swiss-Prot/TrEMBL), `protein_names`, `organism_id` (FK→`organisms`, **required**), `strain_id?`, `gene_id?`, `sequence` + `seq_length` + `seq_mass` + `seq_crc64`, `protein_existence`, `keywords`, `entry_version`/`sequence_version`, `cross_references`.
- **Gene** (GLOBAL): `primary_name`, `synonyms`, `organism_id`, `ncbi_gene_id`, `ensembl_gene_id`, `hgnc_id`, `cross_references`.
- FKs land on the existing taxonomy `organisms`/`strains` tables.
- Bulk-import (Swiss-Prot) mirroring Organism's. Search by accession (resolve secondary→primary), gene, organism. FASTA + ID-resolution endpoints are v1 (§6) — scope as you see fit.

## Phase 3 — Target (spec §5.3 + §2) — *workspace-scoped, mirror Strain*

- **Target** (workspace-scoped): `pref_name`, `target_type` (ChEMBL enum subset: SINGLE_PROTEIN/PROTEIN_COMPLEX/PROTEIN_FAMILY/PROTEIN_PROTEIN_INTERACTION/NUCLEIC_ACID/ORGANISM/CELL_LINE/TISSUE/UNKNOWN), `organism_id?`, `chembl_id?`, `pharmacological_class?`, `cross_references`.
- **TargetComponent** (entity in the Target aggregate, ordered): `protein_id` (FK→Protein), `relationship` enum (SINGLE_PROTEIN/PROTEIN_SUBUNIT/FAMILY_MEMBER/INTERACTING_PROTEIN).
- **Aggregate invariant (the whole point):** cardinality must match `target_type` — SINGLE_PROTEIN ⇒ exactly 1 component; COMPLEX/FAMILY/PPI ⇒ ≥2. Enforce + unit-test it.
- **Interop seam (§2):** prot-cellar owns Target+Protein; chem-cellar references Target by ID and keeps activities on its side; retain `chembl_id` for reconciliation. (No chem-cellar changes here — just keep the seam clean.)
- Re-enable the import-linter `independence` contract in `backend/pyproject.toml` (currently commented out) listing all existing contexts once `protein_catalog` + `target` exist.

## How to build (workflow used here — reuse it)

1. `writing-plans` → draft **Plan 2 (protein-catalog)**, then later **Plan 3 (target)**, mirroring the taxonomy plan's bite-sized TDD task structure. Protein is a dependency of Target — build Plan 2 fully first.
2. `subagent-driven-development` to execute. Per task: `scripts/task-brief PLAN N` → implementer subagent → `scripts/review-package BASE HEAD` → reviewer subagent → fix loop → append to ledger. (Scripts under the `subagent-driven-development` skill dir.) Use cheap models for transcription, standard for integration, opus for the final whole-branch review.
3. Track in `.git/sdd/progress.md`. Run a final whole-branch review before finishing.

## Carry-forward debt (address opportunistically while in these files)

From `.git/sdd/progress.md`: audit nil-user_id SYSTEM sentinel (faithful chem-cellar port); orphaned `Proteome.update()`/`ProteomeUpdated` (lite — wire or remove); bulk-upsert catches only `DomainError` (non-domain errors abort the batch); proteome→strain FK has no `ondelete` (decide when a DeleteStrain lands); add `[mypy-biopython.*]` to `mypy.ini` when biopython is first imported. `UoWDep` now works (AsyncUnitOfWork was registered in the DI container during final review).
