# GO Ontology Ingestion — Implementation Plan (Sub-project 2 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Steps use `- [ ]`; flip to `[x]` as completed.

**Goal:** Ingest `go-basic.obo` into a new `gene_ontology` context (`go_terms` + `go_edges`), via a version-gated idempotent import pipeline (obonet), with a `descendants()` recursive CTE and a `descendants=true` option on the protein `go_term` filter.

**Architecture:** Lean reference-data context — `GoTerm`/`GoEdge` are plain frozen dataclasses (not UoW aggregates); the repository does **bulk** Postgres upserts (chunked under the 65 535-param limit) and a recursive-CTE descendants query. Import pipeline mirrors the UniProt one (fetch → parse → version-gate → upsert). The `descendants` expansion happens in the `ListProteins` use case so the protein repo stays GO-agnostic.

**Tech Stack:** Python 3.13, async SQLAlchemy 2.0 (+ `postgresql.insert` for upsert), Alembic, obonet (new), httpx, pytest+testcontainers.

## Global Constraints

- Alembic head: **`d4f6a8c0e2b4`** (protein cross-references). Task 1's migration sets `down_revision='d4f6a8c0e2b4'`.
- Commit per task on `feat/frontend`; messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Each task ends green (`.venv/bin/pytest`), ruff-clean (`ruff check src/`), mypy-clean (`mypy src/protcellar/`).
- Bulk upserts MUST chunk rows (≤5000/statement) to stay under Postgres' 65 535 bind-param ceiling.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `pyproject.toml` / `uv.lock` | add `obonet` | 1 |
| `domain/gene_ontology/{__init__,go_term,repository}.py` | `GoTerm`/`GoEdge` records + `GoOntologyRepository` protocol | 1 |
| `.../sqlalchemy/gene_ontology/{__init__,models,go_ontology_repository}.py` | `GoTermModel`/`GoEdgeModel` + repo (bulk upsert, find, descendants, version) | 1,2 |
| `alembic/versions/<rev>_go_ontology_tables.py` | `go_terms` + `go_edges` | 1 |
| `infrastructure/ingestion/go_obo.py` | obonet → `(terms, edges, version)` | 3 |
| `infrastructure/ingestion/go_import_runner.py` | version-probe + read + upsert | 4 |
| `scripts/import_go_ontology.py` | CLI | 4 |
| `application/protein_catalog/list_proteins.py` + `.../protein_repository.py` + `interface/routes/proteins.py` | `descendants=true` expansion | 5 |

---

## Task 1: `gene_ontology` context — models, migration, bulk-upsert repository  ✅ DONE

> Status: GREEN. Migration `e6a8c0d2f4b6` (head). `GoTerm`/`GoEdge` records + `GoOntologyRepository` protocol + `go_terms`/`go_edges` models + `SQLAlchemyGoOntologyRepository` (chunked `pg_insert.on_conflict_do_update` upsert / `replace_edges` / `find_term` / `latest_source_version`). `obonet` added. Test green; ruff/mypy clean.

**Files:** create `domain/gene_ontology/__init__.py`, `domain/gene_ontology/go_term.py`, `domain/gene_ontology/repository.py`, `.../sqlalchemy/gene_ontology/__init__.py`, `.../sqlalchemy/gene_ontology/models.py`, `.../sqlalchemy/gene_ontology/go_ontology_repository.py`, `alembic/versions/<rev>_go_ontology_tables.py`; test `tests/unit/infrastructure/test_go_ontology_repository.py`.

**Produces:** `GoTerm(go_id, name, namespace, definition, is_obsolete, replaced_by)`, `GoEdge(child_go_id, parent_go_id, relation)` (frozen dataclasses); `GoOntologyRepository` with `upsert_terms(terms, *, source_version)`, `replace_edges(edges)`, `find_term(go_id) -> GoTerm | None`, `latest_source_version() -> str | None` (and `descendants` added in Task 2).

- [ ] **Step 1 — `uv add obonet`** (from `backend/`): `uv add obonet` → updates pyproject + uv.lock, installs obonet + networkx.
- [ ] **Step 2 — failing test** (`test_go_ontology_repository.py`, function-scoped UoW like `test_proteome_membership`): upsert 2 terms + edges, assert `find_term` returns one with the right namespace; re-upsert with a changed name → updated (idempotent on `go_id`); `latest_source_version()` returns the version.
- [ ] **Step 3 — domain records** (`go_term.py`): two `@dataclass(frozen=True, kw_only=True)` — `GoTerm` (go_id:str, name:str, namespace:str, definition:str|None=None, is_obsolete:bool=False, replaced_by:str|None=None) and `GoEdge` (child_go_id:str, parent_go_id:str, relation:str). `repository.py`: `@runtime_checkable Protocol GoOntologyRepository` with the methods above.
- [ ] **Step 4 — models** (`models.py`): `GoTermModel(Base, EntityModelMixin)` table `go_terms`: `go_id` String(12) unique-indexed, `name` Text, `namespace` String(32), `definition` Text null, `is_obsolete` Boolean default False, `replaced_by` String(12) null, `source` String(16) default "go", `source_version` String(32) null, `imported_at` DateTime(tz) null. `GoEdgeModel(Base, EntityModelMixin)` table `go_edges`: `child_go_id` String(12) indexed, `parent_go_id` String(12) indexed, `relation` String(16); `Index("ix_go_edges_parent_child", "parent_go_id", "child_go_id")`.
- [ ] **Step 5 — migration** `<rev>_go_ontology_tables.py` (down_revision `d4f6a8c0e2b4`): create both tables + indexes (hand-written, matching the models). No data migration.
- [ ] **Step 6 — repository** (`go_ontology_repository.py`): takes a `uow` (`self._uow.session`). `upsert_terms`: chunk terms (≤5000) → `from sqlalchemy.dialects.postgresql import insert as pg_insert`; `pg_insert(GoTermModel).values([... incl id=uuid4(), source_version, imported_at=now ...]).on_conflict_do_update(index_elements=["go_id"], set_={name, namespace, definition, is_obsolete, replaced_by, source_version, imported_at, updated_at=now})`. `replace_edges`: `await session.execute(sa_delete(GoEdgeModel))` then chunked plain inserts (`session.add_all` or `pg_insert` without conflict). `find_term`: select by go_id → `GoTerm`. `latest_source_version`: `select(func.max(GoTermModel.source_version))`.
- [ ] **Step 7 — run green** (`pytest test_go_ontology_repository.py`), ruff, mypy.
- [ ] **Step 8 — commit:** `feat(gene-ontology): go_terms/go_edges tables + bulk-upsert repository`.

## Task 2: `descendants()` recursive CTE

**Files:** modify `go_ontology_repository.py` + protocol; test in the same test file.

**Produces:** `GoOntologyRepository.descendants(go_id) -> set[str]`.

- [ ] **Step 1 — failing test:** seed edges A→B, B→C (child→parent, i.e. `GoEdge(child="A", parent="B")`, `GoEdge(child="B", parent="C")`); assert `descendants("C") == {"A", "B"}`, `descendants("A") == set()`.
- [ ] **Step 2 — run, fail** (method missing).
- [ ] **Step 3 — implement** with a recursive CTE walking `parent_go_id == seed` → collect `child_go_id`, recursing on the children; `UNION` dedups/terminates cycles. SQLAlchemy: `base = select(GoEdgeModel.child_go_id).where(GoEdgeModel.parent_go_id == go_id).cte(recursive=True)`; `cte = base.union(select(GoEdgeModel.child_go_id).join(base, GoEdgeModel.parent_go_id == base.c.child_go_id))`; `return {r[0] for r in (await session.execute(select(cte.c.child_go_id))).all()}`.
- [ ] **Step 4 — green** + ruff + mypy.
- [ ] **Step 5 — commit:** `feat(gene-ontology): descendants() recursive subtree query`.

## Task 3: OBO parser (obonet)

**Files:** create `infrastructure/ingestion/go_obo.py`; test `tests/unit/infrastructure/test_go_obo.py`.

**Produces:** `parse_obo(graph) -> tuple[list[GoTerm], list[GoEdge], str]` (terms, edges, data_version).

- [ ] **Step 1 — failing test:** build a fixture OBO string (header `data-version: releases/2026-05-19`; 3 `[Term]` stanzas with `is_a`/`relationship: part_of`, one `is_obsolete: true` + `replaced_by`), parse via `obonet.read_obo(io.StringIO(obo))`, call `parse_obo(graph)`; assert term count/namespace/obsolete, edge `(child, parent, relation)` tuples (normalized child→parent), and the data_version string.
- [ ] **Step 2 — run, fail** (module missing).
- [ ] **Step 3 — implement:** iterate `graph.nodes(data=True)` → `GoTerm` (id, data["name"], data["namespace"], data.get("def"), data.get("is_obsolete")=="true" or bool, first `data.get("replaced_by")`); iterate `graph.edges(keys=True)` → determine obonet's direction empirically in the test and normalize so the stored edge is `GoEdge(child_go_id=<the more specific term>, parent_go_id=<the is_a/part_of target>, relation=key)`; `data_version = graph.graph.get("data-version", "")`. Keep only `is_a`/`part_of` relations.
- [ ] **Step 4 — green** + ruff + mypy.
- [ ] **Step 5 — commit:** `feat(ingestion): obonet GO OBO parser`.

## Task 4: GO import runner + CLI

**Files:** create `infrastructure/ingestion/go_import_runner.py`, `scripts/import_go_ontology.py`; test `tests/unit/infrastructure/test_go_import_runner.py`.

**Produces:** `GoImportRunner(uow, *, source_url, read_obo=obonet.read_obo)`; `GoImportSummary(terms_upserted, edges, skipped_unchanged)`; CLI `python -m protcellar.scripts.import_go_ontology [--force]`.

- [ ] **Step 1 — failing test:** inject a fake `read_obo` returning a small obonet graph (built from a fixture OBO string) + a fake `version_probe` returning `releases/2026-05-19`; run → terms/edges land in the DB; re-run same version → `skipped_unchanged`; `--force`/changed version re-runs. (Inject `read_obo` + a `_probe_version` override so no network.)
- [ ] **Step 2 — run, fail.**
- [ ] **Step 3 — implement:** `run(*, force=False) -> GoImportSummary`: `version = self._probe_version()`; if `not force and version == await repo.latest_source_version()` → `skipped_unchanged=True`; else `graph = self._read_obo(self._source_url)`; `terms, edges, data_version = parse_obo(graph)`; `repo.upsert_terms(terms, source_version=data_version)`; `repo.replace_edges(edges)`; commit; return counts. `_probe_version`: Range-GET first 2 KB of `source_url`, regex `^data-version: (\S+)`. CLI wires `DatabaseSettings` + a real `httpx`-less obonet read (obonet reads the URL itself) + prints the summary.
- [ ] **Step 4 — green** + ruff + mypy + `python -m protcellar.scripts.import_go_ontology --help`.
- [ ] **Step 5 — commit:** `feat(ingestion): GO ontology import runner + CLI`.

## Task 5: wire `descendants=true` into the protein filter

**Files:** modify `application/protein_catalog/list_proteins.py`, `.../protein_repository.py` (+ protocol `repository.py`), `interface/routes/proteins.py`, DI wiring `interface/dependencies/_protein_catalog.py`; test `tests/api/test_proteins.py`.

- [ ] **Step 1 — failing test:** import the GO edges (parent `GO:0016491` → child `GO:0016655`) via the repo, and a protein annotated with the child `GO:0016655`; assert `?go_term=GO:0016491&descendants=true` returns it while `?go_term=GO:0016491` (exact) does not.
- [ ] **Step 2 — run, fail.**
- [ ] **Step 3 — implement:** `ListProteinsQuery` gains `descendants: bool = False`; `ListProteins.__init__` gains a `go_repo: GoOntologyRepository`; in `__call__`, if `input.go_term` and `input.descendants`, `go_ids = {input.go_term} | await go_repo.descendants(input.go_term)` else `{input.go_term}` (or `None`), pass `go_terms=sorted(go_ids)` to `find_all`. Change `find_all`'s `go_term: str | None` → `go_terms: list[str] | None`; the GO `EXISTS` clause uses `ProteinCrossReferenceModel.accession.in_(go_terms)`. Route adds `descendants: bool = False`. DI: `_get_use_case(ListProteins)` must resolve `GoOntologyRepository` — register `SQLAlchemyGoOntologyRepository` in the container (`infrastructure/di/container.py`).
- [ ] **Step 4 — green** + full suite + ruff + mypy.
- [ ] **Step 5 — commit:** `feat(protein): go_term subtree filter (descendants=true)`.

## Self-review
- Spec coverage: storage→T1; descendants→T2; parser→T3; runner+CLI→T4; filter→T5. ✓
- Placeholders: `<rev>` assigned at execution; obonet edge direction resolved empirically in T3's test (noted). ✓
- Type consistency: `GoTerm`/`GoEdge` fields used identically across repo/parser/runner; `descendants -> set[str]`; `find_all` `go_terms: list[str]` consumed by T5. ✓
- DI note (T5): `ListProteins` gaining a constructor dep requires the container to provide `GoOntologyRepository` — verify `_get_use_case` auto-wires constructor params (Lagom) or register explicitly.
