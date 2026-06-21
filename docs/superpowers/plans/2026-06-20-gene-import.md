# Gene Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `import_proteome` so one run creates `Gene` records from each UniProt entry and links `protein.gene_id`, then load *M. tuberculosis* H37Rv (proteome `UP000001584`, taxon 83332).

**Architecture:** Mirror the protein bulk-import pipeline. A new `BulkUpsertGenes` application use case (idempotent on `(source, source_record_id)`, reusing the existing `GeneRepository.find_by_source_record_id`); two new pure mapper functions that extract genes from UniProt JSON; an **optional** gene collaborator on `ProteomeImportRunner` that upserts genes per chunk and injects `gene_id` into each protein record via `dataclasses.replace`; a `/genes/bulk` route for API parity with `/proteins/bulk` and `/organisms/bulk`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 (async, asyncpg), Lagom DI, returns (Railway `Result`), pytest + pytest-asyncio + testcontainers (real Postgres). Package manager `uv`.

## Global Constraints

- Run everything from `backend/`: `cd backend && uv run <cmd>`.
- Quality gates (must stay clean): `uv run ruff check src tests`, `uv run ruff format --check src tests`, `uv run mypy src` (mypy covers `src` only — test fakes need not satisfy protocols; use `# type: ignore[arg-type]` when passing fakes, mirroring existing tests), `uv run lint-imports`.
- Tests touching the DB (api + runner integration) require Docker (testcontainers spins up Postgres). Mapper + use-case fake tests need no DB.
- **No new runtime dependencies. No database migration** — the `genes` table and `proteins.gene_id` column already exist.
- `Gene` is GLOBAL reference data (`workspace_id = GLOBAL_WORKSPACE_ID`, set in `Gene.__init__`); the bulk upsert runs under `require_admin` (the importer's `_ServiceAuth` and tests' `FakeAuth(role="admin")` satisfy it).
- Reuse the existing `ItemResult` dataclass from `application.protein_catalog.bulk_upsert_proteins` (same sub-package — no import-linter concern).
- Commit after each task. Branch is `feat/gene-import` (already created).

---

### Task 1: `BulkUpsertGenes` application use case

**Files:**
- Create: `backend/src/protcellar/application/protein_catalog/bulk_upsert_genes.py`
- Create: `backend/tests/unit/application/__init__.py` (empty), `backend/tests/unit/application/protein_catalog/__init__.py` (empty)
- Test: `backend/tests/unit/application/protein_catalog/test_bulk_upsert_genes.py`

**Interfaces:**
- Consumes: `Gene` (`domain.protein_catalog.gene`), `GeneRepository`, `UnitOfWork`, `EventDispatcherProtocol`, `require_admin`, `ItemResult` (from `bulk_upsert_proteins`), `CrossReference`, `DomainError`.
- Produces:
  - `GeneImportRecord` (frozen dataclass, kw_only): `primary_name: str`, `organism_id: uuid.UUID`, `source: str`, `source_release: str`, `source_record_id: str`, `source_record_checksum: str`, `synonyms: tuple[str, ...] = ()`, `ncbi_gene_id: str | None = None`, `ensembl_gene_id: str | None = None`, `cross_references: tuple[CrossReference, ...] = ()`.
  - `BulkUpsertGenesCommand(records: tuple[GeneImportRecord, ...], dry_run: bool = False)`.
  - `BulkUpsertGenes` use case → `Result[list[ItemResult], DomainError]`.

- [ ] **Step 1: Write the failing test** — `backend/tests/unit/application/protein_catalog/test_bulk_upsert_genes.py`:

```python
"""Unit tests for BulkUpsertGenes (in-memory fake repo — no DB)."""

from __future__ import annotations

import uuid

import pytest

from protcellar.application.protein_catalog.bulk_upsert_genes import (
    BulkUpsertGenes,
    BulkUpsertGenesCommand,
    GeneImportRecord,
)
from protcellar.domain.protein_catalog.gene import Gene
from tests.fakes.fake_auth import FakeAuth


class _FakeGeneRepo:
    def __init__(self) -> None:
        self.by_srid: dict[tuple[str, str], Gene] = {}

    async def find_by_source_record_id(self, source: str, source_record_id: str) -> Gene | None:
        return self.by_srid.get((source, source_record_id))

    async def save(self, gene: Gene) -> None:
        self.by_srid[(gene.source, gene.source_record_id)] = gene


class _FakeUoW:
    @property
    def is_active(self) -> bool:
        return True

    async def commit(self) -> list:
        return []

    async def rollback(self) -> None:
        return None

    async def __aenter__(self) -> "_FakeUoW":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _NoopDispatcher:
    async def dispatch_all(self, events: object) -> None:
        return None


def _rec(srid: str = "83332:Rv1908c", checksum: str = "c1", primary: str = "katG") -> GeneImportRecord:
    return GeneImportRecord(
        primary_name=primary,
        organism_id=uuid.uuid4(),
        source="uniprot",
        source_release="2026_02",
        source_record_id=srid,
        source_record_checksum=checksum,
        synonyms=("Rv1908c",),
    )


def _uc(repo: _FakeGeneRepo) -> BulkUpsertGenes:
    return BulkUpsertGenes(_FakeUoW(), repo, _NoopDispatcher())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_creates_then_skips_then_updates() -> None:
    repo = _FakeGeneRepo()
    uc = _uc(repo)
    auth = FakeAuth(role="admin")

    r1 = (await uc(BulkUpsertGenesCommand(records=(_rec(),)), auth=auth)).unwrap()
    assert [x.status for x in r1] == ["created"]

    r2 = (await uc(BulkUpsertGenesCommand(records=(_rec(),)), auth=auth)).unwrap()
    assert [x.status for x in r2] == ["skipped"]

    r3 = (
        await uc(
            BulkUpsertGenesCommand(records=(_rec(checksum="c2", primary="katG2"),)), auth=auth
        )
    ).unwrap()
    assert [x.status for x in r3] == ["updated"]
    assert repo.by_srid[("uniprot", "83332:Rv1908c")].primary_name == "katG2"


@pytest.mark.asyncio
async def test_dry_run_persists_nothing() -> None:
    repo = _FakeGeneRepo()
    r = (
        await _uc(repo)(
            BulkUpsertGenesCommand(records=(_rec(),), dry_run=True), auth=FakeAuth(role="admin")
        )
    ).unwrap()
    assert [x.status for x in r] == ["created"]
    assert repo.by_srid == {}
```

- [ ] **Step 2: Run test to verify it fails** — `cd backend && uv run pytest tests/unit/application/protein_catalog/test_bulk_upsert_genes.py -v`
Expected: FAIL with `ModuleNotFoundError: ...bulk_upsert_genes`.

- [ ] **Step 3: Write the implementation** — `backend/src/protcellar/application/protein_catalog/bulk_upsert_genes.py`:

```python
"""Idempotent bulk upsert of gene reference records, keyed on (source, source_record_id)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from returns.result import Result, Success

from protcellar.application.auth import AuthContext, require_admin
from protcellar.application.protein_catalog.bulk_upsert_proteins import ItemResult
from protcellar.application.shared.command import Command
from protcellar.application.shared.event_dispatcher import EventDispatcherProtocol
from protcellar.application.shared.unit_of_work import UnitOfWork
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.repository import GeneRepository
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.shared.errors import DomainError


@dataclass(frozen=True, kw_only=True)
class GeneImportRecord:
    primary_name: str
    organism_id: uuid.UUID
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    synonyms: tuple[str, ...] = ()
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    cross_references: tuple[CrossReference, ...] = ()


@dataclass(frozen=True, kw_only=True)
class BulkUpsertGenesCommand(Command):
    records: tuple[GeneImportRecord, ...]
    dry_run: bool = False


class BulkUpsertGenes:
    def __init__(
        self, uow: UnitOfWork, repo: GeneRepository, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repo, self._dispatcher = uow, repo, dispatcher

    async def __call__(
        self, input: BulkUpsertGenesCommand, auth: AuthContext | None = None
    ) -> Result[list[ItemResult], DomainError]:
        require_admin(auth)
        results: list[ItemResult] = []
        async with self._uow:
            for i, rec in enumerate(input.records):
                try:
                    existing = await self._repo.find_by_source_record_id(
                        rec.source, rec.source_record_id
                    )
                    if existing is not None:
                        if existing.source_record_checksum == rec.source_record_checksum:
                            results.append(
                                ItemResult(index=i, status="skipped", id=str(existing.id))
                            )
                            continue
                        existing.update(
                            primary_name=rec.primary_name,
                            synonyms=list(rec.synonyms),
                            ncbi_gene_id=rec.ncbi_gene_id,
                            ensembl_gene_id=rec.ensembl_gene_id,
                            cross_references=list(rec.cross_references),
                        )
                        existing.source_record_checksum = rec.source_record_checksum
                        existing.source_release = rec.source_release
                        existing.imported_at = datetime.now(UTC)
                        if not input.dry_run:
                            await self._repo.save(existing)
                        results.append(ItemResult(index=i, status="updated", id=str(existing.id)))
                    else:
                        gene = Gene.create(
                            primary_name=rec.primary_name,
                            organism_id=rec.organism_id,
                            synonyms=list(rec.synonyms),
                            ncbi_gene_id=rec.ncbi_gene_id,
                            ensembl_gene_id=rec.ensembl_gene_id,
                            cross_references=list(rec.cross_references),
                        )
                        gene.source = rec.source
                        gene.source_record_id = rec.source_record_id
                        gene.source_record_checksum = rec.source_record_checksum
                        gene.source_release = rec.source_release
                        gene.imported_at = datetime.now(UTC)
                        if not input.dry_run:
                            await self._repo.save(gene)
                        results.append(ItemResult(index=i, status="created", id=str(gene.id)))
                except DomainError as e:
                    results.append(ItemResult(index=i, status="failed", error=e.message))
            if input.dry_run:
                return Success(results)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(results)
```

Also create the two empty `__init__.py` files for the new test package.

- [ ] **Step 4: Run test to verify it passes** — `cd backend && uv run pytest tests/unit/application/protein_catalog/test_bulk_upsert_genes.py -v`
Expected: 2 passed.

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests && uv run mypy src && uv run lint-imports
git add backend/src/protcellar/application/protein_catalog/bulk_upsert_genes.py backend/tests/unit/application
git commit -m "feat(protein-catalog): BulkUpsertGenes use case (idempotent, mirrors protein upsert)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: UniProt → gene mapper functions

**Files:**
- Modify: `backend/src/protcellar/infrastructure/ingestion/uniprot_mapper.py`
- Test: `backend/tests/unit/infrastructure/test_uniprot_mapper.py` (extend)

**Interfaces:**
- Consumes: `GeneImportRecord` (Task 1), the existing `_values` helper in the mapper.
- Produces (both pure, no I/O):
  - `map_uniprot_genes(entry: dict, *, organism_id: uuid.UUID, tax_id: int | str, source: str = "uniprot", source_release: str = "") -> list[GeneImportRecord]`
  - `gene_key_for_entry(entry: dict, *, tax_id: int | str) -> str | None` — the `source_record_id` of the entry's first (primary) gene, for protein linking.

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/unit/infrastructure/test_uniprot_mapper.py`:

```python
from protcellar.infrastructure.ingestion.uniprot_mapper import (  # noqa: E402
    gene_key_for_entry,
    map_uniprot_genes,
)


def test_extracts_gene_with_name_and_locus() -> None:
    org = uuid.uuid4()
    genes = map_uniprot_genes(
        _ENTRY, organism_id=org, tax_id=83332, source="uniprot", source_release="2026_02"
    )
    assert len(genes) == 1
    g = genes[0]
    assert g.primary_name == "katG"
    assert g.source_record_id == "83332:Rv1908c"  # locus tag is the stable key
    assert "Rv1908c" in g.synonyms
    assert g.organism_id == org
    assert g.source == "uniprot"
    assert g.source_record_checksum  # non-empty content hash


def test_gene_key_for_entry_matches_record() -> None:
    assert gene_key_for_entry(_ENTRY, tax_id=83332) == "83332:Rv1908c"


def test_locus_only_entry_uses_locus_as_primary_name() -> None:
    entry = {"genes": [{"orderedLocusNames": [{"value": "Rv0001"}]}]}
    genes = map_uniprot_genes(entry, organism_id=uuid.uuid4(), tax_id=83332)
    assert genes[0].primary_name == "Rv0001"
    assert genes[0].source_record_id == "83332:Rv0001"
    assert genes[0].synonyms == ()


def test_entry_without_genes_yields_nothing() -> None:
    assert map_uniprot_genes({"primaryAccession": "X"}, organism_id=uuid.uuid4(), tax_id=83332) == []
    assert gene_key_for_entry({"primaryAccession": "X"}, tax_id=83332) is None


def test_ncbi_gene_id_from_single_geneid_xref() -> None:
    entry = {
        "genes": [{"geneName": {"value": "katG"}}],
        "uniProtKBCrossReferences": [{"database": "GeneID", "id": "888090"}],
    }
    g = map_uniprot_genes(entry, organism_id=uuid.uuid4(), tax_id=83332)[0]
    assert g.ncbi_gene_id == "888090"
    assert g.source_record_id == "83332:katG"  # no locus tag → geneName is the key
```

- [ ] **Step 2: Run to verify failure** — `cd backend && uv run pytest tests/unit/infrastructure/test_uniprot_mapper.py -v -k "gene"`
Expected: FAIL with `ImportError: cannot import name 'map_uniprot_genes'`.

- [ ] **Step 3: Implement the mapper functions** — add to `backend/src/protcellar/infrastructure/ingestion/uniprot_mapper.py`. Add `import hashlib` to the top imports, add `from protcellar.application.protein_catalog.bulk_upsert_genes import GeneImportRecord` to the imports, and append:

```python
def map_uniprot_genes(
    entry: dict[str, Any],
    *,
    organism_id: uuid.UUID,
    tax_id: int | str,
    source: str = "uniprot",
    source_release: str = "",
) -> list[GeneImportRecord]:
    """Extract one GeneImportRecord per usable gene block on a UniProtKB entry."""
    out: list[GeneImportRecord] = []
    for gene in entry.get("genes") or []:
        primary = _gene_primary_name(gene)
        basis = _gene_key_basis(gene)
        if primary is None or basis is None:
            continue
        ncbi = _ncbi_gene_id(entry)
        synonyms = _gene_synonyms(gene, primary)
        out.append(
            GeneImportRecord(
                primary_name=primary,
                organism_id=organism_id,
                source=source,
                source_release=source_release,
                source_record_id=f"{tax_id}:{basis}",
                source_record_checksum=_gene_checksum(primary, synonyms, ncbi),
                synonyms=synonyms,
                ncbi_gene_id=ncbi,
            )
        )
    return out


def gene_key_for_entry(entry: dict[str, Any], *, tax_id: int | str) -> str | None:
    """source_record_id of the entry's primary (first) gene — used to link the protein."""
    genes = entry.get("genes") or []
    if not genes:
        return None
    basis = _gene_key_basis(genes[0])
    return f"{tax_id}:{basis}" if basis else None


def _gene_primary_name(gene: dict[str, Any]) -> str | None:
    """Human-friendly name: geneName, else first ordered-locus name, else first ORF name."""
    name = (gene.get("geneName") or {}).get("value")
    if name:
        return name
    for key in ("orderedLocusNames", "orfNames"):
        vals = _values(gene.get(key))
        if vals:
            return vals[0]
    return None


def _gene_key_basis(gene: dict[str, Any]) -> str | None:
    """Stable identity: prefer the immutable ordered-locus name (locus tag)."""
    oln = _values(gene.get("orderedLocusNames"))
    if oln:
        return oln[0]
    name = (gene.get("geneName") or {}).get("value")
    if name:
        return name
    orf = _values(gene.get("orfNames"))
    return orf[0] if orf else None


def _gene_synonyms(gene: dict[str, Any], primary_name: str) -> tuple[str, ...]:
    pool: list[str] = []
    name = (gene.get("geneName") or {}).get("value")
    if name:
        pool.append(name)
    pool.extend(_values(gene.get("synonyms")))
    pool.extend(_values(gene.get("orderedLocusNames")))
    pool.extend(_values(gene.get("orfNames")))
    seen: set[str] = set()
    out: list[str] = []
    for n in pool:
        if n and n != primary_name and n not in seen:
            seen.add(n)
            out.append(n)
    return tuple(out)


def _ncbi_gene_id(entry: dict[str, Any]) -> str | None:
    """The NCBI GeneID xref id, but only when exactly one is present (avoid mis-attribution)."""
    ids = [
        x.get("id")
        for x in entry.get("uniProtKBCrossReferences") or []
        if x.get("database") == "GeneID" and x.get("id")
    ]
    return ids[0] if len(ids) == 1 else None


def _gene_checksum(primary_name: str, synonyms: tuple[str, ...], ncbi_gene_id: str | None) -> str:
    basis = "|".join([primary_name, ",".join(sorted(synonyms)), ncbi_gene_id or ""])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
```

> Note the name/key split: `_gene_primary_name` prefers the friendly `geneName`; `_gene_key_basis` prefers the immutable locus tag. So `katG`/`Rv1908c` → name `katG`, key `83332:Rv1908c`.

- [ ] **Step 4: Run to verify pass** — `cd backend && uv run pytest tests/unit/infrastructure/test_uniprot_mapper.py -v`
Expected: all pass (existing + 5 new).

- [ ] **Step 5: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests && uv run mypy src && uv run lint-imports
git add backend/src/protcellar/infrastructure/ingestion/uniprot_mapper.py backend/tests/unit/infrastructure/test_uniprot_mapper.py
git commit -m "feat(ingestion): extract genes from UniProt entries (name/locus-key split)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Runner gene upsert + protein linking + script wiring

**Files:**
- Modify: `backend/src/protcellar/infrastructure/ingestion/import_runner.py`
- Modify: `backend/src/protcellar/scripts/import_proteome.py`
- Test: `backend/tests/unit/infrastructure/test_proteome_import_runner.py` (extend)

**Interfaces:**
- Consumes: `BulkUpsertGenes`, `BulkUpsertGenesCommand` (Task 1); `map_uniprot_genes`, `gene_key_for_entry` (Task 2); `SQLAlchemyGeneRepository`; `dataclasses.replace`.
- Produces: `ProteomeImportRunner.__init__(..., gene_bulk: BulkUpsertGenes | None = None, ...)`; `ImportSummary` gains `genes_created`, `genes_updated`, `genes_skipped`. Behavior unchanged when `gene_bulk is None`.

- [ ] **Step 1: Write the failing test** — append to `backend/tests/unit/infrastructure/test_proteome_import_runner.py`. Add imports at top:

```python
from protcellar.application.protein_catalog.bulk_upsert_genes import BulkUpsertGenes
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
```

Replace the `_runner` helper with a `with_genes` variant and add a gene fixture + test:

```python
def _runner(
    uow: AsyncUnitOfWork,
    meta: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    with_genes: bool = False,
):
    protein_repo = SQLAlchemyProteinRepository(uow)
    bulk = BulkUpsertProteins(uow, protein_repo, _NoopDispatcher())  # type: ignore[arg-type]
    gene_bulk = None
    if with_genes:
        gene_bulk = BulkUpsertGenes(uow, SQLAlchemyGeneRepository(uow), _NoopDispatcher())  # type: ignore[arg-type]
    runner = ProteomeImportRunner(
        uow, _FakeClient(meta, entries), bulk, gene_bulk=gene_bulk, chunk_size=500
    )
    return runner, protein_repo


def _gene_entries(acc1: str, acc2: str, tax_id: int) -> list[dict[str, Any]]:
    gene_block = {"geneName": {"value": "katG"}, "orderedLocusNames": [{"value": "Rv1908c"}]}
    return [
        {
            "primaryAccession": acc1,
            "uniProtkbId": "G1_TEST",
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "sequence": {"value": "MKTAYIAKQR"},
            "organism": {"taxonId": tax_id},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
            "genes": [gene_block],
        },
        {
            "primaryAccession": acc2,
            "uniProtkbId": "G2_TEST",
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "sequence": {"value": "MKTAYIAKQS"},
            "organism": {"taxonId": tax_id},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
            "genes": [gene_block],
        },
    ]


@pytest.mark.asyncio
async def test_import_creates_and_links_genes(import_uow: AsyncUnitOfWork) -> None:
    runner, protein_repo = _runner(
        import_uow, _meta("UP000000066", 99980), _gene_entries("P0DG01", "P0DG02", 99980),
        with_genes=True,
    )

    summary = await runner.run("UP000000066", auth=FakeAuth(role="admin"))

    assert summary.created == 2
    assert summary.genes_created == 1  # the shared gene is deduped within the chunk

    async with import_uow:
        grepo = SQLAlchemyGeneRepository(import_uow)
        gene = await grepo.find_by_source_record_id("uniprot", "99980:Rv1908c")
        assert gene is not None
        assert gene.primary_name == "katG"

        p1 = await protein_repo.find_by_accession("P0DG01")
        p2 = await protein_repo.find_by_accession("P0DG02")
        assert p1 is not None and p1.gene_id == gene.id
        assert p2 is not None and p2.gene_id == gene.id
```

- [ ] **Step 2: Run to verify failure** — `cd backend && uv run pytest tests/unit/infrastructure/test_proteome_import_runner.py -v -k "genes"`
Expected: FAIL — `ProteomeImportRunner.__init__() got an unexpected keyword argument 'gene_bulk'`.

- [ ] **Step 3: Modify the runner** — in `backend/src/protcellar/infrastructure/ingestion/import_runner.py`:

3a. Imports — add:

```python
from dataclasses import dataclass, replace
```

(replace the existing `from dataclasses import dataclass`), and add:

```python
from protcellar.application.protein_catalog.bulk_upsert_genes import (
    BulkUpsertGenes,
    BulkUpsertGenesCommand,
)
from protcellar.infrastructure.ingestion.uniprot_mapper import (
    gene_key_for_entry,
    map_uniprot_entry,
    map_uniprot_genes,
)
```

(merge with the existing `map_uniprot_entry` import line).

3b. `ImportSummary` — add the three gene counters (after `failed`):

```python
    genes_created: int = 0
    genes_updated: int = 0
    genes_skipped: int = 0
```

3c. Constructor — add the optional collaborator:

```python
    def __init__(
        self,
        uow: AsyncUnitOfWork,
        client: ProteomeFetcher,
        bulk_upsert: BulkUpsertProteins,
        *,
        gene_bulk: BulkUpsertGenes | None = None,
        chunk_size: int = 500,
    ) -> None:
        self._uow = uow
        self._client = client
        self._bulk = bulk_upsert
        self._gene_bulk = gene_bulk
        self._chunk_size = chunk_size
```

3d. `run()` — accumulate raw entries (not mapped records) and thread `organism_id`/`tax_id`/`source_release` into `_load_chunk`. Replace the body from `summary = ImportSummary(...)` through the final `return summary`:

```python
        tax_id = (meta.get("taxonomy") or {}).get("taxonId")
        summary = ImportSummary(proteome_id=proteome_id)
        seen: set[str] = set()
        chunk: list[dict[str, Any]] = []
        async for entry in self._client.iter_entries(proteome_id):
            chunk.append(entry)
            seen.add(entry["primaryAccession"])
            summary.entries += 1
            if len(chunk) >= self._chunk_size:
                await self._load_chunk(
                    chunk, proteome_db_id, organism_id, tax_id, source_release,
                    summary, dry_run=dry_run, auth=auth,
                )
                chunk = []
            if limit is not None and summary.entries >= limit:
                break
        if chunk:
            await self._load_chunk(
                chunk, proteome_db_id, organism_id, tax_id, source_release,
                summary, dry_run=dry_run, auth=auth,
            )
        if not dry_run and limit is None:
            await self._reconcile_membership(proteome_db_id, seen, summary)
        return summary
```

3e. Replace `_load_chunk` entirely with the entry-based two-phase version + a gene-dedupe helper:

```python
    async def _load_chunk(
        self,
        entries: list[dict[str, Any]],
        proteome_db_id: uuid.UUID,
        organism_id: uuid.UUID,
        tax_id: Any,
        source_release: str,
        summary: ImportSummary,
        *,
        dry_run: bool,
        auth: AuthContext | None,
    ) -> None:
        gene_id_by_key = await self._upsert_genes(
            entries, organism_id, tax_id, source_release, summary, dry_run=dry_run, auth=auth
        )

        records: list[ProteinImportRecord] = []
        for entry in entries:
            rec = map_uniprot_entry(
                entry, organism_id=organism_id, source="uniprot", source_release=source_release
            )
            if self._gene_bulk is not None:
                key = gene_key_for_entry(entry, tax_id=tax_id)
                gid = gene_id_by_key.get(key) if key else None
                if gid is not None:
                    rec = replace(rec, gene_id=gid)
            records.append(rec)

        command = BulkUpsertProteinsCommand(records=tuple(records), dry_run=dry_run)
        items = (await self._bulk(command, auth=auth)).unwrap()
        for item in items:
            if item.status == "created":
                summary.created += 1
            elif item.status == "updated":
                summary.updated += 1
            elif item.status == "skipped":
                summary.skipped += 1
            else:
                summary.failed += 1
        if dry_run:
            return
        async with self._uow:
            proteome_repo = SQLAlchemyProteomeRepository(self._uow)
            for item in items:
                if item.id and item.status in ("created", "updated", "skipped"):
                    await proteome_repo.add_protein(proteome_db_id, uuid.UUID(item.id))
                    summary.members_linked += 1
            await self._uow.commit()

    async def _upsert_genes(
        self,
        entries: list[dict[str, Any]],
        organism_id: uuid.UUID,
        tax_id: Any,
        source_release: str,
        summary: ImportSummary,
        *,
        dry_run: bool,
        auth: AuthContext | None,
    ) -> dict[str, uuid.UUID]:
        """Upsert all genes in the chunk (deduped by key); return {source_record_id: gene_id}."""
        if self._gene_bulk is None:
            return {}
        by_key: dict[str, GeneImportRecord] = {}
        for entry in entries:
            for rec in map_uniprot_genes(
                entry, organism_id=organism_id, tax_id=tax_id,
                source="uniprot", source_release=source_release,
            ):
                by_key.setdefault(rec.source_record_id, rec)
        if not by_key:
            return {}
        gene_records = list(by_key.values())
        command = BulkUpsertGenesCommand(records=tuple(gene_records), dry_run=dry_run)
        items = (await self._gene_bulk(command, auth=auth)).unwrap()
        gene_id_by_key: dict[str, uuid.UUID] = {}
        for item, rec in zip(items, gene_records, strict=True):
            if item.id:
                gene_id_by_key[rec.source_record_id] = uuid.UUID(item.id)
            if item.status == "created":
                summary.genes_created += 1
            elif item.status == "updated":
                summary.genes_updated += 1
            elif item.status == "skipped":
                summary.genes_skipped += 1
        return gene_id_by_key
```

3f. Add the `GeneImportRecord` import used in the type hint above — add to the Task-1 import block:

```python
from protcellar.application.protein_catalog.bulk_upsert_genes import (
    BulkUpsertGenes,
    BulkUpsertGenesCommand,
    GeneImportRecord,
)
```

- [ ] **Step 4: Wire the script** — in `backend/src/protcellar/scripts/import_proteome.py`:

4a. Add imports:

```python
from protcellar.application.protein_catalog.bulk_upsert_genes import BulkUpsertGenes
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
```

4b. In `import_proteome(...)`, build the gene collaborator and pass it in (replace the runner-construction block):

```python
            protein_repo = SQLAlchemyProteinRepository(uow)
            gene_repo = SQLAlchemyGeneRepository(uow)
            bulk = BulkUpsertProteins(uow, protein_repo, _NoopDispatcher())
            gene_bulk = BulkUpsertGenes(uow, gene_repo, _NoopDispatcher())
            runner = ProteomeImportRunner(uow, UniProtClient(http), bulk, gene_bulk=gene_bulk)
            return await runner.run(
                proteome_id, dry_run=dry_run, limit=limit, force=force, auth=_ServiceAuth()
            )
```

4c. Extend the summary print (add genes to the f-string):

```python
    print(
        f"[{summary.proteome_id}] entries={summary.entries} created={summary.created} "
        f"updated={summary.updated} skipped={summary.skipped} failed={summary.failed} "
        f"genes_created={summary.genes_created} genes_updated={summary.genes_updated} "
        f"members_linked={summary.members_linked} dry_run={args.dry_run}"
    )
```

- [ ] **Step 5: Run tests to verify pass** — `cd backend && uv run pytest tests/unit/infrastructure/test_proteome_import_runner.py -v`
Expected: all pass (existing 4 unchanged + new gene test). The existing tests call `_runner(...)` without `with_genes`, so `gene_bulk is None` and behavior is identical.

- [ ] **Step 6: Lint + commit**

```bash
cd backend && uv run ruff check src tests && uv run ruff format src tests && uv run mypy src && uv run lint-imports
git add backend/src/protcellar/infrastructure/ingestion/import_runner.py backend/src/protcellar/scripts/import_proteome.py backend/tests/unit/infrastructure/test_proteome_import_runner.py
git commit -m "feat(ingestion): import + link genes during proteome import

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `/genes/bulk` API route + DI wiring (parity with proteins/organisms)

**Files:**
- Modify: `backend/src/protcellar/interface/routes/genes.py`
- Modify: `backend/src/protcellar/infrastructure/di/_protein_catalog.py`
- Modify: `backend/src/protcellar/interface/dependencies/_protein_catalog.py`
- Modify: `backend/src/protcellar/interface/dependencies/__init__.py`
- Test: `backend/tests/api/test_gene_bulk_import.py` (new)

**Interfaces:**
- Consumes: `BulkUpsertGenes`, `BulkUpsertGenesCommand`, `GeneImportRecord` (Task 1); `CrossReference`; `result_to_response`; `_gene_cmd` (existing DI helper); `_get_use_case`.
- Produces: `POST /api/v1/genes/bulk`; `BulkUpsertGenesDep`; `BulkUpsertGenes` registered in the DI container.

- [ ] **Step 1: Write the failing test** — `backend/tests/api/test_gene_bulk_import.py`:

```python
import pytest
from httpx import AsyncClient


async def _organism(client: AsyncClient, ncbi_tax_id: int) -> str:
    resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": ncbi_tax_id,
            "rank": "species",
            "scientific_name": "Mycobacterium tuberculosis",
        },
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_gene_bulk_upsert_is_idempotent(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99951)
    rec = {
        "primary_name": "katG",
        "organism_id": organism_id,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "99951:Rv1908c",
        "source_record_checksum": "c1",
        "synonyms": ["Rv1908c"],
    }
    first = await client.post("/api/v1/genes/bulk", json={"records": [rec]})
    assert first.status_code == 200
    assert first.json()["summary"]["created"] == 1
    gene_id = first.json()["results"][0]["id"]

    got = await client.get(f"/api/v1/genes/{gene_id}")
    assert got.json()["primary_name"] == "katG"
    assert "Rv1908c" in got.json()["synonyms"]

    second = await client.post("/api/v1/genes/bulk", json={"records": [rec]})
    assert second.json()["summary"]["skipped"] == 1

    rec2 = {**rec, "source_record_checksum": "c2", "primary_name": "katG2"}
    third = await client.post("/api/v1/genes/bulk", json={"records": [rec2]})
    assert third.json()["summary"]["updated"] == 1
    assert (await client.get(f"/api/v1/genes/{gene_id}")).json()["primary_name"] == "katG2"


@pytest.mark.asyncio
async def test_gene_bulk_dry_run_does_not_persist(client: AsyncClient) -> None:
    organism_id = await _organism(client, ncbi_tax_id=99952)
    rec = {
        "primary_name": "dnaA",
        "organism_id": organism_id,
        "source": "uniprot",
        "source_release": "2026_02",
        "source_record_id": "99952:Rv0001",
        "source_record_checksum": "c1",
    }
    dry = await client.post("/api/v1/genes/bulk", json={"records": [rec], "dry_run": True})
    assert dry.json()["summary"]["created"] == 1
    listed = await client.get("/api/v1/genes", params={"name": "dnaA", "organism_id": organism_id})
    assert listed.json()["items"] == []
```

- [ ] **Step 2: Run to verify failure** — `cd backend && uv run pytest tests/api/test_gene_bulk_import.py -v`
Expected: FAIL (404 on `POST /api/v1/genes/bulk`).

- [ ] **Step 3: Register the use case in DI** — in `backend/src/protcellar/infrastructure/di/_protein_catalog.py`, add the import and registration:

```python
from protcellar.application.protein_catalog.bulk_upsert_genes import BulkUpsertGenes
```

and after `container.define(BulkUpsertProteins, _protein_cmd(BulkUpsertProteins))` add:

```python
    container.define(BulkUpsertGenes, _gene_cmd(BulkUpsertGenes))
```

- [ ] **Step 4: Add the dependency alias** — in `backend/src/protcellar/interface/dependencies/_protein_catalog.py`:

```python
from protcellar.application.protein_catalog.bulk_upsert_genes import BulkUpsertGenes
```

add `"BulkUpsertGenesDep"` to `__all__`, and under `# --- Gene Deps ---` add:

```python
BulkUpsertGenesDep = Annotated[BulkUpsertGenes, Depends(_get_use_case(BulkUpsertGenes))]
```

Then in `backend/src/protcellar/interface/dependencies/__init__.py` add `BulkUpsertGenesDep` to both the import-from-`_protein_catalog` block and `__all__` (mirror how `BulkUpsertProteinsDep` appears there).

- [ ] **Step 5: Add the route** — in `backend/src/protcellar/interface/routes/genes.py`:

5a. Add imports:

```python
from protcellar.application.protein_catalog.bulk_upsert_genes import (
    BulkUpsertGenesCommand,
    GeneImportRecord,
)
from protcellar.domain.shared.cross_reference import CrossReference
```

and add `BulkUpsertGenesDep` to the existing `from protcellar.interface.dependencies import (...)` block.

5b. Add the DTOs (after `UpdateGeneBody`):

```python
class BulkCrossReferenceBody(BaseModel):
    database: str
    accession: str
    properties: dict[str, str] | None = None
    evidence: str | None = None


class BulkGeneRecordBody(BaseModel):
    primary_name: str
    organism_id: uuid.UUID
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    synonyms: list[str] = []
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    cross_references: list[BulkCrossReferenceBody] = []


class BulkUpsertGenesBody(BaseModel):
    records: list[BulkGeneRecordBody]
    dry_run: bool = False


class GeneItemResultResponse(BaseModel):
    index: int
    status: str
    id: str | None = None
    error: str | None = None


class GeneBulkSummaryResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    failed: int


class GeneBulkUpsertResponse(BaseModel):
    results: list[GeneItemResultResponse]
    summary: GeneBulkSummaryResponse
```

5c. Add the route (after `create_gene`, before `update_gene` — order doesn't matter since `/bulk` is POST and `/{gene_id}` is GET/PATCH, but keep POSTs together):

```python
@router.post("/bulk", response_model=GeneBulkUpsertResponse)
async def bulk_upsert_genes(
    body: BulkUpsertGenesBody,
    auth: AuthDep,
    use_case: BulkUpsertGenesDep,
) -> GeneBulkUpsertResponse:
    command = BulkUpsertGenesCommand(
        records=tuple(
            GeneImportRecord(
                primary_name=r.primary_name,
                organism_id=r.organism_id,
                source=r.source,
                source_release=r.source_release,
                source_record_id=r.source_record_id,
                source_record_checksum=r.source_record_checksum,
                synonyms=tuple(r.synonyms),
                ncbi_gene_id=r.ncbi_gene_id,
                ensembl_gene_id=r.ensembl_gene_id,
                cross_references=tuple(
                    CrossReference(
                        database=xr.database,
                        accession=xr.accession,
                        properties=xr.properties,
                        evidence=xr.evidence,
                    )
                    for xr in r.cross_references
                ),
            )
            for r in body.records
        ),
        dry_run=body.dry_run,
    )
    items = result_to_response(await use_case(command, auth=auth))
    summary = GeneBulkSummaryResponse(
        created=sum(1 for i in items if i.status == "created"),
        updated=sum(1 for i in items if i.status == "updated"),
        skipped=sum(1 for i in items if i.status == "skipped"),
        failed=sum(1 for i in items if i.status == "failed"),
    )
    return GeneBulkUpsertResponse(
        results=[
            GeneItemResultResponse(index=i.index, status=i.status, id=i.id, error=i.error)
            for i in items
        ],
        summary=summary,
    )
```

- [ ] **Step 6: Run tests to verify pass** — `cd backend && uv run pytest tests/api/test_gene_bulk_import.py -v`
Expected: 2 passed. (`tests/api/conftest.py` already includes the gene router — no conftest change needed.)

- [ ] **Step 7: Full suite + lint + commit**

```bash
cd backend && uv run pytest tests/unit tests/api -q && uv run ruff check src tests && uv run ruff format src tests && uv run mypy src && uv run lint-imports
git add backend/src/protcellar/interface/routes/genes.py backend/src/protcellar/infrastructure/di/_protein_catalog.py backend/src/protcellar/interface/dependencies/_protein_catalog.py backend/src/protcellar/interface/dependencies/__init__.py backend/tests/api/test_gene_bulk_import.py
git commit -m "feat(genes): /genes/bulk import route + DI wiring (parity with proteins)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Load *M. tuberculosis* H37Rv (the actual ask) + verify

**Files:** none (operational). This is the acceptance test for the whole plan.

- [ ] **Step 1: Bring up local infra + migrations** — from repo root:

```bash
docker compose up -d postgres valkey
cd backend && export DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar && uv run alembic upgrade head
```

(Or `make up` from the repo root, which does both.)

- [ ] **Step 2: Smoke-test the importer (dry run, small)** — confirms network + mapping without writing:

```bash
cd backend && uv run python -m protcellar.scripts.import_proteome UP000001584 --dry-run --limit 20
```

Expected: a summary line with `entries=20`, `created=20`, and `genes_created>0`, `dry_run=True`.

- [ ] **Step 3: Run the full import** (~4,000 entries; takes a few minutes):

```bash
cd backend && uv run python -m protcellar.scripts.import_proteome UP000001584
```

Expected: `entries≈4000 created≈4000 ... genes_created>0 members_linked≈4000 dry_run=False`.

- [ ] **Step 4: Verify via SQL** — proteins exist, genes exist, and proteins are linked:

```bash
cd backend && export DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar && uv run python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from protcellar.infrastructure.persistence.settings import DatabaseSettings

async def main():
    e = create_async_engine(DatabaseSettings().database_url)
    async with e.connect() as c:
        for label, q in [
            ('proteins', 'select count(*) from proteins'),
            ('genes', 'select count(*) from genes'),
            ('proteins_with_gene', 'select count(*) from proteins where gene_id is not null'),
        ]:
            print(label, (await c.execute(text(q))).scalar())
    await e.dispose()

asyncio.run(main())
"
```

Expected: `proteins` ≈ 4000, `genes` > 0, `proteins_with_gene` is a large fraction of proteins (most H37Rv entries carry a locus tag).

- [ ] **Step 5: Spot-check via the API** (optional, if the backend is running via `make dev`): `GET /api/v1/proteins/P9WIE5` returns katG with a `gene_id`; `GET /api/v1/genes?name=katG` returns the gene. No commit (operational task).

---

## Self-Review

**Spec coverage:**
- Spec §"`BulkUpsertGenes`" → Task 1. ✓
- Spec §"Mapper additions" (`map_uniprot_genes`, `gene_key_for_entry`, name/key split, NCBI GeneID, checksum) → Task 2. ✓
- Spec §"Runner change" (optional collaborator, two-phase chunk, `replace(gene_id=…)`, summary counters) + §"Script wiring" → Task 3. ✓
- Spec §"Testing" #1 (mapper) → Task 2; #2 (bulk import via API) → Task 4; #3 (runner integration, create + link + dedupe) → Task 3; #4 (full gates) → Tasks 1–4 lint/commit steps. ✓
- Spec §"Final Step" (run import for UP000001584 + verify) → Task 5. ✓
- Idempotency (keyed on `(source, source_record_id)`, checksum-gated) → Task 1 logic + Task 2 stable key; verified by Task 4's idempotency test. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. ✓

**Type consistency:** `GeneImportRecord` fields are identical across Task 1 (definition), Task 2 (construction in `map_uniprot_genes`), Task 3 (type hint in `_upsert_genes`), and Task 4 (route construction). `source_record_id` format `"{tax_id}:{basis}"` is identical in `map_uniprot_genes` and `gene_key_for_entry` (both via `_gene_key_basis`). `ItemResult{index,status,id,error}` reused unchanged. Runner `gene_bulk` kw-only with `None` default matches all `_runner(...)` call sites (existing tests omit it). ✓

**No-migration check:** `genes` table and `proteins.gene_id` FK already exist; no Alembic revision is created or needed. ✓
