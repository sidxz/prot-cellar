# GO Ontology Ingestion — Design (Sub-project 2 of 3)

**Goal:** Ingest the Gene Ontology DAG as reference data so the catalog supports **subtree queries** (e.g. *"all proteins under oxidoreductase activity, including descendants"*) and so piece 3 has **self-hosted graph data** for the GO graph. Mirrors the UniProt import pipeline (fetch → parse → version-gated idempotent upsert) built in sub-project 1.

**Source:** `http://purl.obolibrary.org/obo/go/go-basic.obo` — ~32 MB, `text/obo`, header `data-version: releases/YYYY-MM-DD` (used for version-gating, like the proteome `modified` date). ~47k terms, `is_a` + `part_of` relations only (the "basic" acyclic-friendly subset).

**Dependency (new):** `obonet` (+ its `networkx` transitive dep), added via `uv add obonet`. `obonet.read_obo(source)` returns a `networkx.MultiDiGraph`: nodes are GO ids carrying `name`/`namespace`/`def`/`is_obsolete`/`replaced_by`; edges are the relations; `graph.graph["data-version"]` gives the release. The parser chosen over hand-rolling per the brainstorm.

**Non-goals (other specs / deferred):** the frontend GO graph rendering (piece 3); GO annotation *evidence* beyond what UniProt already gives us; OWL/full-`go.obo` relations beyond `is_a`/`part_of`.

---

## Storage — new `gene_ontology` bounded context

Mirrors the existing DDD layout (`domain/`, `infrastructure/persistence/sqlalchemy/`).

- **`go_terms`** (`GoTermModel`, `EntityModelMixin` UUID pk + unique `go_id`):
  `go_id` String(12) unique-indexed (e.g. `GO:0016491`), `name` Text, `namespace` String(32) (biological_process / molecular_function / cellular_component), `definition` Text null, `is_obsolete` Boolean, `replaced_by` String(12) null, + provenance (`source` = "go", `source_version` = release date, `imported_at`).
- **`go_edges`** (`GoEdgeModel`, `EntityModelMixin`):
  `child_go_id` String(12) indexed, `parent_go_id` String(12) indexed, `relation` String(16) (`is_a` / `part_of`). Composite index `(parent_go_id, child_go_id)` for descendant walks and `(child_go_id)` for ancestor walks. No DB FK (GO ids are self-consistent reference data; the import maintains integrity).
- **Domain:** `GoTerm` aggregate (the fields above) + `GoEdge` VO (`child_go_id`, `parent_go_id`, `relation`). `GoOntologyRepository` protocol: `upsert_terms(list[GoTerm])`, `replace_edges(list[GoEdge])`, `find_term(go_id) -> GoTerm | None`, `descendants(go_id) -> set[str]`, `latest_source_version() -> str | None`.

## Ingestion pipeline (mirrors UniProt)

- **Parser** `infrastructure/ingestion/go_obo.py` — pure: `parse_obo(graph: MultiDiGraph) -> tuple[list[GoTerm], list[GoEdge], str]` (terms, edges, data-version). Unit-tested by feeding `obonet.read_obo(io.StringIO(fixture_obo))` so no network is touched. (Edge direction from obonet is verified in that test and normalized to child→parent.)
- **Runner** `infrastructure/ingestion/go_import_runner.py` — `GoImportRunner(uow, *, source_url=...)`. Steps: (1) cheap **version probe** — Range-GET the first ~2 KB of the OBO to read `data-version`; if it equals the stored `source_version` and not `force`, return `GoImportSummary(skipped_unchanged=True)`; (2) `obonet.read_obo(source_url)`; (3) `parse_obo`; (4) `upsert_terms` (idempotent on `go_id`) + `replace_edges` (clear this release's edges and re-insert — edges have no natural per-row key); (5) record `source_version`. Returns counts (`terms_upserted`, `edges`, `skipped_unchanged`).
- **CLI** `scripts/import_go_ontology.py`: `python -m protcellar.scripts.import_go_ontology [--force]`. Wires `DatabaseSettings` + the runner, prints the summary.

## Subtree query + filter integration

- `descendants(go_id)` is a **recursive CTE** over `go_edges` (start at `go_id`, repeatedly join `parent_go_id = current` to collect `child_go_id`), returning the full descendant id set (excluding the seed).
- Piece 1's protein filter gains subtree support **in the use case, keeping the protein repo decoupled from GO**: `ListProteins` gains a `GoOntologyRepository` dependency and a `descendants: bool` query field. When `go_term` is set and `descendants=true`, it computes `go_ids = {go_term} | await go_repo.descendants(go_term)` and passes the **set** to the repo; otherwise it passes `{go_term}`. `find_all`'s existing `go_term: str` filter becomes `go_terms: list[str] | None` → `EXISTS (… database='GO' AND accession = ANY(:go_terms))`. The route exposes `go_term` (str) + `descendants` (bool) and `ListProteins` does the expansion.

## Error handling

- OBO HTTP/network errors abort the run (idempotent — safe to re-run); the version probe avoids the 32 MB download when unchanged.
- Obsolete terms are stored with `is_obsolete=true` (not dropped) so existing GO annotations still resolve to a name; `replaced_by` is captured for follow-the-pointer.
- `replace_edges` runs in one transaction so a failed re-import doesn't leave a half-rebuilt edge set.

## Testing

- **Parser** (`go_obo`): a fixture OBO string with 3 terms + `is_a`/`part_of` edges + one obsolete term → assert terms (name/namespace/obsolete) and edges (child/parent/relation) and the parsed `data-version`.
- **Ingestion round-trip** (real DB, fake source via a small OBO fixture or an injected parsed result): run → `go_terms`/`go_edges` rows present; re-run same version → `skipped_unchanged`; `--force` re-runs.
- **`descendants()`**: seed a small DAG (A is_a B, B is_a C) → `descendants("C") == {"A", "B"}` (edges stored child→parent; the CTE walks parent→child to collect descendants); a stray cycle is absorbed by the CTE's `UNION` (visited) semantics.
- **Filter end-to-end**: proteins annotated with a child term are returned by `?go_term=<parent>&descendants=true` but not by `?go_term=<parent>` alone.

## Rollout sequence (for the plan)

1. `uv add obonet`; `gene_ontology` domain + `go_terms`/`go_edges` models + migration + repository (`upsert_terms`/`replace_edges`/`find_term`/`latest_source_version`).
2. `descendants()` recursive CTE + its test.
3. OBO parser (`go_obo`) + test.
4. `GoImportRunner` (version probe + upsert) + CLI + test.
5. Wire `descendants=true` into `ListProteins`/`find_all`/route + test.
