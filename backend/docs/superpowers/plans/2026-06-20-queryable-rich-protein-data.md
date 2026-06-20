# Queryable Rich Protein Data — Implementation Plan (Sub-project 1 of 3)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, this session). Steps use checkbox (`- [ ]`) syntax; flip to `[x]` as completed.

**Goal:** Normalize the `cross_references` JSON column into an indexed `protein_cross_references` table, add catalog filters to `GET /api/v1/proteins`, and make the proteome re-sync correct (version-gate + membership reconciliation, manual trigger).

**Architecture:** Mirror the established owned-collection pattern (`protein_features` etc.) for the new table; the domain `CrossReference` VO and the API response shape stay identical — only persistence + new query paths change. Re-sync changes live in the existing `ProteomeImportRunner`.

**Tech Stack:** Python 3.13, async SQLAlchemy 2.0, Alembic, Postgres 16, FastAPI, pytest + testcontainers. Run tests from `backend/`: `.venv/bin/pytest`.

## Global Constraints

- Alembic head is **`c2e4a6f8b0d2`** (proteome_proteins). The Task-1 migration sets `down_revision = 'c2e4a6f8b0d2'`; later tasks add no migrations. Single linear head.
- Commit per task on `feat/frontend` (per the user). End commit messages with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Spec deviations (intentional): **(a)** omit the spec's `isoform_id` column — the `CrossReference` VO doesn't capture it, so it'd always be null (add when the VO does). **(b)** `properties` column uses SQLAlchemy `JSON` (matches the 6 existing child tables; filters never read properties, so JSONB's indexability isn't needed). **(c)** keep `_xref_json.py` — `gene_repository` still uses it for `genes.cross_references` (out of scope); only `protein_repository` stops using it.
- Each task ends green (`.venv/bin/pytest`), ruff-clean (`.venv/bin/ruff check src/`), mypy-clean (`.venv/bin/mypy src/protcellar/`).

## File structure

| File | Responsibility | Task |
|---|---|---|
| `.../sqlalchemy/protein_catalog/models.py` | `ProteinCrossReferenceModel` + `cross_reference_rows` relationship; drop `cross_references` column | 1 |
| `backend/alembic/versions/<rev>_protein_cross_references_table.py` | create table + data-migrate JSON→rows + drop column | 1 |
| `.../sqlalchemy/protein_catalog/protein_repository.py` | map `cross_reference_rows`; retire `_xref_json` use; EXISTS filter clauses | 1, 2 |
| `application/protein_catalog/list_proteins.py` | `ListProteinsQuery` filter fields | 2 |
| `interface/routes/proteins.py` | new query params on `list_proteins` | 2 |
| `infrastructure/ingestion/import_runner.py` | version-gate + reconciliation; `ImportSummary` fields | 3, 4 |
| `domain/taxonomy/repository.py` + `.../taxonomy/proteome_repository.py` | `remove_protein` + `list_members` | 4 |
| `scripts/import_proteome.py` | `--force` flag | 3 |

---

## Task 1: Normalize `cross_references` → `protein_cross_references` table  ✅ DONE

> Status: GREEN. Migration `d4f6a8c0e2b4` (head) — creates the table, data-migrates JSON→rows, drops the column. `ProteinCrossReferenceModel` owned collection; repo maps `cross_reference_rows` (retired `_xref_json` use — kept for gene). DB-level RED test + existing API round-trip both green; full suite 103; ruff/mypy clean. (`properties` typed `dict[str,str]` to match the `CrossReference` VO.)

**Files:**
- Modify: `src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/models.py`
- Create: `backend/alembic/versions/d4f6a8c0e2b4_protein_cross_references_table.py`
- Modify: `src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/protein_repository.py`
- Test: `tests/api/test_protein_bulk_import.py` (existing `test_bulk_upsert_is_idempotent` already asserts a PDB cross-ref round-trips → it must stay green after the column→table switch)

**Interfaces produced:** `ProteinCrossReferenceModel` (`protein_cross_references`); `ProteinModel.cross_reference_rows: list[ProteinCrossReferenceModel]`. The domain `Protein.cross_references: list[CrossReference]` and `ProteinResponse.cross_references` are **unchanged**.

- [ ] **Step 1 — failing test:** the existing `test_bulk_upsert_is_idempotent` (asserts `{"database":"pdb","accession":"6VXX"}` round-trips through bulk→GET) is the regression guard. First, prove the *new table* is the store with a fresh assertion appended to that test file:

```python
@pytest.mark.asyncio
async def test_cross_references_persist_as_rows(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99920)
    rec = {
        "primary_accession": "P0DV01", "organism_id": organism_id, "sequence": "MKT",
        "is_reviewed": True, "source": "uniprot", "source_release": "2026_02",
        "source_record_id": "P0DV01", "source_record_checksum": "crc1",
        "cross_references": [
            {"database": "PDB", "accession": "1ABC", "properties": {"Method": "X-ray"}},
            {"database": "GO", "accession": "GO:0003674"},
        ],
    }
    assert (await client.post("/api/v1/proteins/bulk", json={"records": [rec]})).status_code == 200
    got = (await client.get("/api/v1/proteins/P0DV01")).json()["cross_references"]
    dbs = {x["database"] for x in got}
    assert {"PDB", "GO"} <= dbs
    pdb = next(x for x in got if x["database"] == "PDB")
    assert pdb["accession"] == "1ABC"
```

- [ ] **Step 2 — run, expect FAIL** (collection passes but the run errors/fails until the table exists): `.venv/bin/pytest tests/api/test_protein_bulk_import.py::test_cross_references_persist_as_rows -x -q`.
- [ ] **Step 3 — SA model** (`models.py`): add the `cross_reference_rows` relationship to `ProteinModel` (next to `citations`) and **remove** the `cross_references` JSON column line; append the model class:
```python
    cross_reference_rows: Mapped[list[ProteinCrossReferenceModel]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
        foreign_keys="ProteinCrossReferenceModel.protein_id",
        order_by="ProteinCrossReferenceModel.id",
    )


class ProteinCrossReferenceModel(Base, EntityModelMixin):
    """A normalized cross-reference owned by a Protein (UniProt DR line)."""

    __tablename__ = "protein_cross_references"

    protein_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proteins.id"), nullable=False, index=True
    )
    database: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    accession: Mapped[str] = mapped_column(String(128), nullable=False)
    properties: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (Index("ix_protein_xrefs_db_accession", "database", "accession"),)
```
  Delete the line `cross_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)` from `ProteinModel`.
- [ ] **Step 4 — migration** `d4f6a8c0e2b4_protein_cross_references_table.py` (down_revision `c2e4a6f8b0d2`):
```python
def upgrade() -> None:
    op.create_table(
        'protein_cross_references',
        sa.Column('protein_id', sa.Uuid(), nullable=False),
        sa.Column('database', sa.String(length=64), nullable=False),
        sa.Column('accession', sa.String(length=128), nullable=False),
        sa.Column('properties', sa.JSON(), nullable=True),
        sa.Column('evidence', sa.String(length=64), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['protein_id'], ['proteins.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_protein_cross_references_protein_id'), 'protein_cross_references', ['protein_id'])
    op.create_index(op.f('ix_protein_cross_references_database'), 'protein_cross_references', ['database'])
    op.create_index('ix_protein_xrefs_db_accession', 'protein_cross_references', ['database', 'accession'])
    op.execute(
        """
        INSERT INTO protein_cross_references
            (id, protein_id, database, accession, properties, evidence, created_at, updated_at)
        SELECT gen_random_uuid(), p.id, elem->>'database', elem->>'accession',
               elem->'properties', elem->>'evidence', now(), now()
        FROM proteins p, json_array_elements(p.cross_references) AS elem
        WHERE p.cross_references IS NOT NULL
        """
    )
    op.drop_column('proteins', 'cross_references')


def downgrade() -> None:
    op.add_column('proteins', sa.Column('cross_references', sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE proteins p SET cross_references = sub.arr
        FROM (
            SELECT protein_id,
                   json_agg(json_build_object(
                       'database', database, 'accession', accession,
                       'properties', properties, 'evidence', evidence)) AS arr
            FROM protein_cross_references GROUP BY protein_id
        ) sub
        WHERE p.id = sub.protein_id
        """
    )
    op.drop_index('ix_protein_xrefs_db_accession', table_name='protein_cross_references')
    op.drop_index(op.f('ix_protein_cross_references_database'), table_name='protein_cross_references')
    op.drop_index(op.f('ix_protein_cross_references_protein_id'), table_name='protein_cross_references')
    op.drop_table('protein_cross_references')
```
- [ ] **Step 5 — repository** (`protein_repository.py`): import `ProteinCrossReferenceModel`; in `_to_domain` replace `cross_references=xrefs_from_json(model.cross_references)` with a list-comp over `model.cross_reference_rows`; in `_to_model` drop the `cross_references=...` kwarg and after building `model` add `model.cross_reference_rows = [self._xref_to_model(x) for x in aggregate.cross_references]`; in `_update_model` replace the `model.cross_references = ...` line with `model.cross_reference_rows = [...]`; add the static helper; **remove** the now-unused `xrefs_from_json, xrefs_to_json` import.
```python
            cross_references=[
                CrossReference(
                    database=x.database, accession=x.accession,
                    properties=x.properties, evidence=x.evidence,
                )
                for x in model.cross_reference_rows
            ],
```
```python
    @staticmethod
    def _xref_to_model(x: CrossReference) -> ProteinCrossReferenceModel:
        return ProteinCrossReferenceModel(
            database=x.database, accession=x.accession,
            properties=x.properties, evidence=x.evidence,
        )
```
  `CrossReference` is already imported. (Leave `_xref_json.py` in place — gene_repository uses it.)
- [ ] **Step 6 — run, expect PASS:** `.venv/bin/pytest tests/api/test_protein_bulk_import.py -q` (new test + the existing PDB round-trip both green), then `.venv/bin/ruff check src/` and `.venv/bin/mypy src/protcellar/`.
- [ ] **Step 7 — commit:** `feat(protein): normalize cross_references into an indexed protein_cross_references table`.

---

## Task 2: Catalog filters on `GET /api/v1/proteins`  ✅ DONE

> Status: GREEN. `xref_db` / `has_structure` / `go_term` / `keyword` threaded through `ListProteinsQuery` → use-case → `ProteinRepository` protocol → `find_all` (indexed `EXISTS` subqueries over `protein_cross_references` / `protein_keywords`) → route params. Filter test (rich vs bare protein) green; ruff/mypy clean.

**Files:**
- Modify: `src/protcellar/application/protein_catalog/list_proteins.py` (`ListProteinsQuery`)
- Modify: `src/protcellar/infrastructure/persistence/sqlalchemy/protein_catalog/protein_repository.py` (`find_all`)
- Modify: `src/protcellar/interface/routes/proteins.py` (`list_proteins` route)
- Test: `tests/api/test_proteins.py`

**Interfaces consumed:** `ProteinCrossReferenceModel`, `ProteinKeywordModel` (both in the protein_catalog models module). **Produced:** query params `xref_db`, `has_structure`, `go_term`, `keyword`.

- [ ] **Step 1 — failing test** (`tests/api/test_proteins.py`): import two proteins (one with a PDB xref + `GO:0016491` + keyword `KW-0560`, one bare), then assert each filter narrows the list. Sketch:
```python
@pytest.mark.asyncio
async def test_protein_catalog_filters(client: AsyncClient) -> None:
    org = await _organism(client, 99930)  # helper that POSTs an organism, returns id
    rich = {"primary_accession": "P0DV10", "organism_id": org, "sequence": "MKT",
            "is_reviewed": True, "source": "uniprot", "source_release": "x",
            "source_record_id": "P0DV10", "source_record_checksum": "c",
            "cross_references": [{"database": "PDB", "accession": "1XYZ"},
                                 {"database": "GO", "accession": "GO:0016491"}],
            "keyword_refs": [{"kw_id": "KW-0560"}]}
    bare = {**rich, "primary_accession": "P0DV11", "source_record_id": "P0DV11",
            "cross_references": [], "keyword_refs": []}
    await client.post("/api/v1/proteins/bulk", json={"records": [rich, bare]})

    async def accs(q):
        items = (await client.get(f"/api/v1/proteins{q}")).json()["items"]
        return {p["primary_accession"] for p in items}

    assert "P0DV10" in await accs("?xref_db=PDB") and "P0DV11" not in await accs("?xref_db=PDB")
    assert "P0DV10" in await accs("?has_structure=true")
    assert "P0DV10" in await accs("?go_term=GO:0016491") and "P0DV11" not in await accs("?go_term=GO:0016491")
    assert "P0DV10" in await accs("?keyword=KW-0560")
```
- [ ] **Step 2 — run, expect FAIL** (filters ignored → bare protein also returned): `.venv/bin/pytest tests/api/test_proteins.py::test_protein_catalog_filters -x -q`.
- [ ] **Step 3 — `ListProteinsQuery`**: add `xref_db: str | None = None`, `has_structure: bool | None = None`, `go_term: str | None = None`, `keyword: str | None = None`; the `ListProteins` use case passes them through to `repo.find_all(...)` (add the kwargs to its existing call).
- [ ] **Step 4 — repository `find_all`**: add the four kwargs and the `EXISTS` clauses (import `exists` from sqlalchemy; `ProteinKeywordModel`/`ProteinCrossReferenceModel` already importable):
```python
_STRUCTURE_DBS = ("PDB", "PDBsum", "AlphaFoldDB", "EMDB", "SMR")
...
        if xref_db is not None:
            stmt = stmt.where(exists().where(
                ProteinCrossReferenceModel.protein_id == ProteinModel.id,
                ProteinCrossReferenceModel.database == xref_db))
        if has_structure:
            stmt = stmt.where(exists().where(
                ProteinCrossReferenceModel.protein_id == ProteinModel.id,
                ProteinCrossReferenceModel.database.in_(_STRUCTURE_DBS)))
        if go_term is not None:
            stmt = stmt.where(exists().where(
                ProteinCrossReferenceModel.protein_id == ProteinModel.id,
                ProteinCrossReferenceModel.database == "GO",
                ProteinCrossReferenceModel.accession == go_term))
        if keyword is not None:
            stmt = stmt.where(exists().where(
                ProteinKeywordModel.protein_id == ProteinModel.id,
                ProteinKeywordModel.kw_id == keyword))
```
- [ ] **Step 5 — route `list_proteins`**: add `xref_db: str | None = None`, `has_structure: bool | None = None`, `go_term: str | None = None`, `keyword: str | None = None` params and pass them into `ListProteinsQuery(...)`.
- [ ] **Step 6 — run, expect PASS** + ruff + mypy.
- [ ] **Step 7 — commit:** `feat(protein): catalog filters — xref_db, has_structure, go_term, keyword`.

---

## Task 3: Re-sync version gate (`--force`)

**Files:**
- Modify: `src/protcellar/infrastructure/ingestion/import_runner.py`
- Modify: `src/protcellar/scripts/import_proteome.py` (`--force`)
- Test: `tests/unit/infrastructure/test_proteome_import_runner.py`

**Interfaces produced:** `ImportSummary.skipped_unchanged: bool`; `ProteomeImportRunner.run(..., force: bool = False)`.

- [ ] **Step 1 — failing test**: run the import once (creates proteome with `source_version = meta["modified"]`), run again with the same meta → second run `skipped_unchanged is True`, `entries == 0`; a third run with `force=True` re-processes. Add to the runner test file using its existing `_FakeClient`/`_meta` helpers (give a distinct proteome id/tax id).
- [ ] **Step 2 — run, expect FAIL**.
- [ ] **Step 3 — implement**: add `skipped_unchanged: bool = False` to `ImportSummary`. In `_ensure_proteome`, pass `source_version=meta.get("modified")` to `Proteome.create(...)`. In `run(...)`, after fetching `meta`, load the existing proteome (`SQLAlchemyProteomeRepository(self._uow).find_by_proteome_id(proteome_id)` inside `async with self._uow`); if it exists and `existing.source_version == meta.get("modified")` and not `force`, return `ImportSummary(proteome_id=proteome_id, skipped_unchanged=True)` immediately (before streaming). Thread a `force: bool = False` param through `run`.
- [ ] **Step 4 — CLI**: add `parser.add_argument("--force", action="store_true", ...)` and pass `force=args.force` into `import_proteome(...)` → `runner.run(..., force=...)`.
- [ ] **Step 5 — run, expect PASS** + ruff + mypy.
- [ ] **Step 6 — commit:** `feat(ingestion): version-gated re-sync (--force to override)`.

---

## Task 4: Re-sync membership reconciliation

**Files:**
- Modify: `src/protcellar/domain/taxonomy/repository.py` (protocol)
- Modify: `src/protcellar/infrastructure/persistence/sqlalchemy/taxonomy/proteome_repository.py`
- Modify: `src/protcellar/infrastructure/ingestion/import_runner.py`
- Test: `tests/unit/infrastructure/test_proteome_import_runner.py`

**Interfaces produced:** `ProteomeRepository.remove_protein(proteome_id, protein_id)`; `ProteomeRepository.list_members(proteome_id) -> list[tuple[uuid.UUID, str]]`; `ImportSummary.members_pruned: int`.

- [ ] **Step 1 — failing test**: import accessions `{P0DV20, P0DV21, P0DV22}`; re-import `{P0DV20, P0DV21}` with a bumped `modified`; assert `members_pruned == 1` and `list_protein_ids` no longer contains P0DV22's id, while P0DV20/21 remain.
- [ ] **Step 2 — run, expect FAIL**.
- [ ] **Step 3 — repo**: add to the `ProteomeRepository` Protocol and `SQLAlchemyProteomeRepository`:
```python
    async def remove_protein(self, proteome_id: uuid.UUID, protein_id: uuid.UUID) -> None:
        await self._session.execute(
            sa_delete(ProteomeProteinModel).where(
                ProteomeProteinModel.proteome_id == proteome_id,
                ProteomeProteinModel.protein_id == protein_id))

    async def list_members(self, proteome_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
        stmt = (select(ProteomeProteinModel.protein_id, ProteinModel.primary_accession)
                .join(ProteinModel, ProteinModel.id == ProteomeProteinModel.protein_id)
                .where(ProteomeProteinModel.proteome_id == proteome_id))
        return [(r[0], r[1]) for r in (await self._session.execute(stmt)).all()]
```
  Import `delete as sa_delete` and `ProteinModel` in the proteome repository.
- [ ] **Step 4 — runner**: in `run(...)`, accumulate `seen: set[str]` of `entry["primaryAccession"]` as you map each entry; add `members_pruned: int = 0` to `ImportSummary`; after the streaming loop (skip when `dry_run`), open `async with self._uow`, call `list_members(proteome_db_id)`, and for each `(pid, acc)` whose `acc not in seen`, `remove_protein(proteome_db_id, pid)` + `summary.members_pruned += 1`, then commit.
- [ ] **Step 5 — run, expect PASS** + full suite (`.venv/bin/pytest -q`) + ruff + mypy.
- [ ] **Step 6 — commit:** `feat(ingestion): reconcile proteome membership on re-sync (prune departed accessions)`.

---

## Self-review

- **Spec coverage:** Part A → Task 1; Part B → Task 2; Part C version-gate → Task 3, reconciliation → Task 4. ✓
- **Placeholders:** migration `<rev>` resolved to `d4f6a8c0e2b4`; all code shown. ✓
- **Type consistency:** `cross_reference_rows` relationship name used in model + repo; `_xref_to_model` returns `ProteinCrossReferenceModel`; `list_members` returns `list[tuple[UUID, str]]` consumed by Task 4's runner loop; `_STRUCTURE_DBS` defined where used. ✓
- **Deviations** (isoform_id omitted, `JSON` not JSONB, `_xref_json` kept for gene) are recorded in Global Constraints. ✓
