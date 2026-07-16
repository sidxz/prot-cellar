# Ingestion Plugins — Plan B: Plugin Contract + DeJesus Reference Plugin

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Depends on:** Plan A (`generation_method` on the `Provenance` VO + JSON mapping). Do not start Plan B until Plan A's Task 1–2 are merged — Task 1 here imports `GenerationMethod`.

**Goal:** Ship the in-tree, contract-shaped plugin abstraction — a declarative `PluginManifest` + `IngestionPlugin` protocol + `PluginRunContext` + a record-typed `sink` over the existing `BulkUpsert<X>` doorway — a config-driven registry exposed at `GET /api/v1/plugins`, a `POST /api/v1/plugins/{id}/runs` starter, and the reference **DeJesus essentiality** plugin that wraps the known-good normalizer + parser + command and stamps `generation_method=imported` + run lineage.

**Architecture:** A plugin run **is** an `ImportRun`. Integration is one new `ImportType.PLUGIN` member routed to a single `PluginDispatchAdapter` registered in the existing `IMPORT_ADAPTERS` map — so the worker's `IMPORT_ADAPTERS[run.import_type]` lookup dispatches plugin runs with **no plugin-specific branching in `worker.py`**. The 3 legacy importers (`proteome`/`gene_enrichment`/`go_ontology`) are untouched. The **contract** (manifest/protocol/context/sink/validation) lives in `application/plugins/` (pure, so domain/application tests can reference the shapes); the **runnable** pieces (registry, in-tree sink, concrete plugins, dispatch adapter) live in `infrastructure/`, respecting the import-linter layers contract (`interface > infrastructure > application > domain`; lower never imports higher). Plugin params are validated against the manifest descriptor at the interface boundary (`plugins.py` route, which may import the infra registry), then passed through `StartImport` — so `application/imports/params.py` stays registry-free.

**Envelope & sink:** the plugin author writes fetch-and-map only, calling `await ctx.sink.upsert("essentiality", records)` with `EssentialityImportRecord`s. The framework — not the plugin — attaches `generation_method` (from the manifest default), `source_run_id` (the `ImportRun` id, stamped into the record's `extensions` bag for v1), and the target `organism_id`; it reports progress and merges per-row `ItemResult`s into the run summary. `dry_run` flows straight to the command's existing dry-run path. The in-tree sink is the single seam an external HTTP sink swaps for later — the envelope is already record-typed and serializable.

**Tech Stack:** Python ≥3.13, frozen dataclasses + `Protocol` (structural typing, docu-store style — no base class), `StrEnum`, `importlib`-based discovery, arq worker, `returns.Result`, FastAPI + Pydantic, pytest.

## Global Constraints

- **Python ≥3.13** — `StrEnum`, `X | None`, PEP 695. Copied from `backend/pyproject.toml`.
- **Run backend commands from `backend/` via `uv`** — `uv run pytest ...`, `uv run lint-imports`, `uv run ruff check src tests`, `uv run mypy src`.
- **import-linter layers contract ("Clean Architecture layers": `interface > infrastructure > application > domain`)** — a lower layer must NOT import a higher one. Therefore: the plugin **contract** (`application/plugins/**`) may import only `application`/`domain`; the **registry, in-tree sink, concrete plugins, dispatch adapter** live in `infrastructure`; `GET/POST /plugins` live in `interface` (may import the infra registry). `application/imports/params.py` must NOT gain a registry import — plugin param validation happens in the `plugins.py` route.
- **import-linter "Domain purity"** — `protcellar.domain` may not import `application`/`infrastructure`/`interface`/`fastapi`/`sqlalchemy`/`redis`/`lagom`. `ImportType.PLUGIN` (domain enum) stays dependency-free.
- **Non-breaking to legacy importers** — the 3 existing adapters, their param models, and their forms are untouched. `IMPORT_ADAPTERS` gains exactly one entry (`ImportType.PLUGIN`), keeping the `set(IMPORT_ADAPTERS) == set(ImportType)` coverage invariant asserted in `tests/unit/infrastructure/test_import_adapters.py`.
- **Lineage is v1-cheap** — `source_run_id` is written into the existing `extensions` JSON bag (no table migration). `ponytail:` promote it to an indexed column when the v1.1 undo-a-run feature needs efficient `WHERE source_run_id = ?` queries.
- **`generation_method` default for the import doorway** — `BulkUpsertEssentialityCommand.generation_method` defaults to `imported` (it is the bulk *import* path); plugins pass their manifest default explicitly via the sink.
- **Tests** — unit tests are bare `async def` (pytest `asyncio_mode="auto"`) but keep the existing files' explicit `@pytest.mark.asyncio`. In-memory fakes for unit tests (mirror `tests/unit/application/target_biology/test_bulk_upsert_essentiality.py`); `FakeAuth(role="admin")` from `tests/fakes/fake_auth.py`. API/worker tests use the Postgres testcontainer fixtures in `tests/conftest.py`.
- **Full gates** — `make test` (unit + `lint-imports`), `make test-api` (Postgres + Valkey), `make lint` (ruff + mypy). The two pre-existing proteome test-isolation failures noted in project memory are unrelated.

---

## File Structure

**Create (application — the contract, pure):**
- `backend/src/protcellar/application/plugins/__init__.py`
- `backend/src/protcellar/application/plugins/manifest.py` — `ParamType`, `ParamField`, `PluginManifest`.
- `backend/src/protcellar/application/plugins/validation.py` — `validate_against_manifest`.
- `backend/src/protcellar/application/plugins/sink.py` — `Sink` Protocol.
- `backend/src/protcellar/application/plugins/context.py` — `PluginRunContext`.
- `backend/src/protcellar/application/plugins/protocol.py` — `IngestionPlugin` Protocol.

**Create (infrastructure — runnable):**
- `backend/src/protcellar/infrastructure/plugins/__init__.py`
- `backend/src/protcellar/infrastructure/plugins/in_tree_sink.py` — `InTreeSink`.
- `backend/src/protcellar/infrastructure/plugins/registry.py` — `ENABLED_PLUGINS`, `get_plugin`, `all_manifests`.
- `backend/src/protcellar/infrastructure/plugins/dejesus_essentiality/__init__.py` — exports `plugin`.
- `backend/src/protcellar/infrastructure/plugins/dejesus_essentiality/manifest.py` — `MANIFEST`.
- `backend/src/protcellar/infrastructure/plugins/dejesus_essentiality/plugin.py` — `DejesusEssentialityPlugin` + `plugin`.

**Create (interface):**
- `backend/src/protcellar/interface/routes/plugins.py` — `GET /api/v1/plugins`, `POST /api/v1/plugins/{plugin_id}/runs`.

**Modify:**
- `backend/src/protcellar/application/target_biology/bulk_upsert_essentiality.py` — thread `generation_method` + `source_run_id`.
- `backend/src/protcellar/domain/imports/enums.py` — add `ImportType.PLUGIN`.
- `backend/src/protcellar/infrastructure/ingestion/import_adapters.py` — `ImportRuntime.run_id`, `PluginDispatchAdapter`, `_summarize`, `IMPORT_ADAPTERS[PLUGIN]`.
- `backend/src/protcellar/infrastructure/ingestion/worker.py` — pass `run_id=run.id`; set `job_timeout` on `WorkerSettings`.
- `backend/src/protcellar/application/imports/params.py` — `PLUGIN` branches in `validate_params`/`target_key`/`upload_ref_of`.
- `backend/src/protcellar/interface/app.py` — register the plugins router.

**Create (tests):**
- `backend/tests/unit/application/plugins/{__init__.py,test_validation.py}`
- `backend/tests/unit/infrastructure/plugins/{__init__.py,test_in_tree_sink.py,test_registry.py,test_dejesus_plugin.py,test_plugin_dispatch.py}`
- `backend/tests/unit/application/imports/test_plugin_params.py`
- `backend/tests/api/test_plugins_api.py`, `backend/tests/api/test_plugin_run.py`

**Modify (tests):**
- `backend/tests/unit/application/target_biology/test_bulk_upsert_essentiality.py`
- `backend/tests/api/conftest.py` (register the plugins router in the test app)

---

## Task 1: Thread `generation_method` + `source_run_id` through `BulkUpsertEssentiality`

**Files:**
- Modify: `backend/src/protcellar/application/target_biology/bulk_upsert_essentiality.py`
- Test: `backend/tests/unit/application/target_biology/test_bulk_upsert_essentiality.py`

**Interfaces:**
- Consumes: `GenerationMethod` (Plan A, Task 1).
- Produces: `BulkUpsertEssentialityCommand` gains `generation_method: str = GenerationMethod.IMPORTED.value` and `source_run_id: uuid.UUID | None = None`. Each written record's `provenance.generation_method` reflects the command; `extensions["source_run_id"]` is set when `source_run_id` is provided.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/unit/application/target_biology/test_bulk_upsert_essentiality.py` — extend the import block and append two tests:

```python
from protcellar.domain.shared.provenance import GenerationMethod


@pytest.mark.asyncio
async def test_default_generation_method_is_imported() -> None:
    org = uuid.uuid4()
    gene = Gene.create(primary_name="Rv0667", organism_id=org, synonyms=["rpoB"])
    ess_repo = _FakeEssRepo()
    uc = _uc(_FakeGeneRepo([gene]), ess_repo)
    cmd = BulkUpsertEssentialityCommand(
        organism_id=org,
        records=(EssentialityImportRecord(locus_key="rpoB", classification="ES"),),
    )
    (await uc(cmd, auth=_admin())).unwrap()
    assert ess_repo.items[0].provenance.generation_method is GenerationMethod.IMPORTED


@pytest.mark.asyncio
async def test_stamps_generation_method_and_source_run_id() -> None:
    org = uuid.uuid4()
    run_id = uuid.uuid4()
    gene = Gene.create(primary_name="Rv0667", organism_id=org, synonyms=["rpoB"])
    ess_repo = _FakeEssRepo()
    uc = _uc(_FakeGeneRepo([gene]), ess_repo)
    cmd = BulkUpsertEssentialityCommand(
        organism_id=org,
        records=(EssentialityImportRecord(locus_key="rpoB", classification="ES"),),
        generation_method=GenerationMethod.AI_EXTRACTED.value,
        source_run_id=run_id,
    )
    (await uc(cmd, auth=_admin())).unwrap()
    saved = ess_repo.items[0]
    assert saved.provenance.generation_method is GenerationMethod.AI_EXTRACTED
    assert saved.extensions["source_run_id"] == str(run_id)
    assert saved.extensions["raw_call"] == "ES"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/application/target_biology/test_bulk_upsert_essentiality.py -v`
Expected: FAIL — `TypeError: ... got an unexpected keyword argument 'generation_method'`.

- [ ] **Step 3: Write minimal implementation**

In `bulk_upsert_essentiality.py`, extend the provenance import:

```python
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
```

Extend the command:

```python
@dataclass(frozen=True, kw_only=True)
class BulkUpsertEssentialityCommand(Command):
    organism_id: uuid.UUID
    records: tuple[EssentialityImportRecord, ...]
    source_type: str = ProvenanceSourceType.PUBLISHED.value
    generation_method: str = GenerationMethod.IMPORTED.value
    source_run_id: uuid.UUID | None = None
    dry_run: bool = False
```

Update `_provenance` to carry the method, and add an `_extensions` helper (below it):

```python
def _provenance(
    source_type: str, generation_method: str, rec: EssentialityImportRecord
) -> Provenance:
    citations: tuple[Citation, ...] = ()
    if rec.pmid or rec.dataset:
        citations = (Citation(pmid=rec.pmid, label=rec.dataset),)
    return Provenance(
        source_type=ProvenanceSourceType(source_type),
        generation_method=GenerationMethod(generation_method),
        citations=citations,
    )


def _extensions(rec: EssentialityImportRecord, source_run_id: uuid.UUID | None) -> dict[str, object]:
    ext: dict[str, object] = {"raw_call": rec.classification}
    if source_run_id is not None:
        # ponytail: source_run_id in the extensions bag (no migration); promote to
        # an indexed column when the v1.1 undo-a-run feature needs to query by it.
        ext["source_run_id"] = str(source_run_id)
    return ext
```

In `__call__`, update the provenance call and both `extensions=` sites:

```python
                    provenance = _provenance(input.source_type, input.generation_method, rec)
```

```python
                        match.update(
                            classification=classification,
                            condition=rec.condition,
                            method=rec.method,
                            confidence=rec.confidence,
                            provenance=provenance,
                            extensions=_extensions(rec, input.source_run_id),
                        )
```

```python
                        record = Essentiality.create(
                            workspace_id=GLOBAL_WORKSPACE_ID,
                            gene_id=gene.id,
                            classification=classification,
                            condition=rec.condition,
                            method=rec.method,
                            confidence=rec.confidence,
                            provenance=provenance,
                            extensions=_extensions(rec, input.source_run_id),
                        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/application/target_biology/test_bulk_upsert_essentiality.py -v`
Expected: PASS (5 tests — 3 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/application/target_biology/bulk_upsert_essentiality.py backend/tests/unit/application/target_biology/test_bulk_upsert_essentiality.py
git commit -m "feat(target-biology): stamp generation_method + source_run_id on essentiality upsert"
```

---

## Task 2: Plugin contract types + manifest-driven param validation

**Files:**
- Create: `backend/src/protcellar/application/plugins/__init__.py` (docstring only), `manifest.py`, `validation.py`, `sink.py`, `context.py`, `protocol.py`
- Create: `backend/tests/unit/application/plugins/__init__.py` (empty), `test_validation.py`

**Interfaces:**
- Produces:
  - `ParamType(StrEnum)` = `STRING`, `NUMBER`, `ENUM`, `ORGANISM`, `FILE_UPLOAD`, `BOOL`.
  - `ParamField(*, key, label, type: ParamType, required=False, default=None, options: tuple[str,...]=(), help=None)` — frozen.
  - `PluginManifest(*, id, version, name, description, target_records: tuple[str,...], default_generation_method: GenerationMethod, params: tuple[ParamField,...]=(), requires_secrets: tuple[str,...]=())` — frozen.
  - `validate_against_manifest(manifest: PluginManifest, raw: dict[str, Any]) -> dict[str, Any]` — required-field + type checks; raises `DomainValidationError` on bad input; fills defaults; returns a coerced param dict.
  - `Sink(Protocol)`: `async def upsert(self, record_type: str, records: Sequence[object]) -> list[ItemResult]`.
  - `PluginRunContext(*, params, organism_id, load_upload, sink, reporter, auth)` — frozen.
  - `IngestionPlugin(Protocol)`: `@staticmethod def manifest() -> PluginManifest`; `async def run(self, ctx: PluginRunContext) -> None`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/application/plugins/test_validation.py`:

```python
import pytest

from protcellar.application.plugins.manifest import ParamField, ParamType, PluginManifest
from protcellar.application.plugins.validation import validate_against_manifest
from protcellar.domain.shared.errors import DomainValidationError
from protcellar.domain.shared.provenance import GenerationMethod


def _manifest(*params: ParamField) -> PluginManifest:
    return PluginManifest(
        id="t",
        version="1.0.0",
        name="T",
        description="d",
        target_records=("essentiality",),
        default_generation_method=GenerationMethod.IMPORTED,
        params=tuple(params),
    )


def test_required_missing_raises() -> None:
    m = _manifest(ParamField(key="x", label="X", type=ParamType.STRING, required=True))
    with pytest.raises(DomainValidationError):
        validate_against_manifest(m, {})


def test_defaults_are_filled() -> None:
    m = _manifest(ParamField(key="force", label="F", type=ParamType.BOOL, default=False))
    assert validate_against_manifest(m, {}) == {"force": False}


def test_number_is_coerced() -> None:
    m = _manifest(ParamField(key="n", label="N", type=ParamType.NUMBER, required=True))
    assert validate_against_manifest(m, {"n": "83332"}) == {"n": 83332}


def test_enum_rejects_out_of_set() -> None:
    m = _manifest(
        ParamField(key="c", label="C", type=ParamType.ENUM, options=("a", "b"), required=True)
    )
    assert validate_against_manifest(m, {"c": "a"}) == {"c": "a"}
    with pytest.raises(DomainValidationError):
        validate_against_manifest(m, {"c": "z"})


def test_unknown_keys_are_dropped() -> None:
    m = _manifest(ParamField(key="x", label="X", type=ParamType.STRING))
    assert validate_against_manifest(m, {"x": "v", "junk": 1}) == {"x": "v"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/application/plugins/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError: protcellar.application.plugins.manifest`.

- [ ] **Step 3: Write the contract modules**

`backend/src/protcellar/application/plugins/__init__.py`:

```python
"""The ingestion-plugin contract — pure application-layer shapes.

manifest/validation/sink/context/protocol are import-clean (application + domain
only) so tests and the interface layer can reference them without pulling in the
concrete infrastructure registry.
"""
```

`backend/src/protcellar/application/plugins/manifest.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from protcellar.domain.shared.provenance import GenerationMethod


class ParamType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    ENUM = "enum"
    ORGANISM = "organism"  # renders the organism combobox on the FE
    FILE_UPLOAD = "file_upload"  # reuses POST /api/v1/imports/uploads -> upload_ref
    BOOL = "bool"


@dataclass(frozen=True, kw_only=True)
class ParamField:
    """A constrained param descriptor the FE renders without a schema-form library."""

    key: str
    label: str
    type: ParamType
    required: bool = False
    default: object | None = None
    options: tuple[str, ...] = ()  # for ENUM
    help: str | None = None


@dataclass(frozen=True, kw_only=True)
class PluginManifest:
    """Declarative plugin identity — drives the FE catalog + param validation."""

    id: str
    version: str
    name: str
    description: str
    target_records: tuple[str, ...]
    default_generation_method: GenerationMethod
    params: tuple[ParamField, ...] = ()
    requires_secrets: tuple[str, ...] = ()
```

`backend/src/protcellar/application/plugins/validation.py`:

```python
from __future__ import annotations

from typing import Any

from protcellar.application.plugins.manifest import ParamField, ParamType, PluginManifest
from protcellar.domain.shared.errors import DomainValidationError


def validate_against_manifest(manifest: PluginManifest, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate + coerce a raw param dict against a manifest's ParamField descriptor.

    Only keys declared on the manifest survive. Raises DomainValidationError on a
    missing required field or a bad value.
    """
    out: dict[str, Any] = {}
    for pf in manifest.params:
        raw_value = raw.get(pf.key)
        present = raw_value is not None and raw_value != ""
        if not present:
            if pf.required:
                raise DomainValidationError(f"missing required param '{pf.key}'")
            if pf.default is not None:
                out[pf.key] = pf.default
            continue
        out[pf.key] = _coerce(pf, raw_value)
    return out


def _coerce(pf: ParamField, value: Any) -> Any:
    if pf.type is ParamType.NUMBER:
        text = str(value)
        try:
            return float(text) if "." in text else int(text)
        except ValueError as e:
            raise DomainValidationError(f"param '{pf.key}' must be a number") from e
    if pf.type is ParamType.BOOL:
        return bool(value)
    if pf.type is ParamType.ENUM:
        if str(value) not in pf.options:
            raise DomainValidationError(f"param '{pf.key}' must be one of {list(pf.options)}")
        return str(value)
    # STRING, ORGANISM, FILE_UPLOAD — pass through as string.
    return str(value)
```

`backend/src/protcellar/application/plugins/sink.py`:

```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from protcellar.application.target_biology._import_support import ItemResult


class Sink(Protocol):
    """The single seam a plugin writes through. In-tree today; an HTTP client later.

    Records are the per-record import DTOs (e.g. EssentialityImportRecord). The sink
    implementation resolves record_type -> the matching BulkUpsert<X> command and
    stamps generation_method + source_run_id (the plugin never sees those)."""

    async def upsert(self, record_type: str, records: Sequence[object]) -> list[ItemResult]: ...
```

`backend/src/protcellar/application/plugins/context.py`:

```python
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from protcellar.application.auth import AuthContext
from protcellar.application.imports.progress_reporter import ProgressReporter
from protcellar.application.plugins.sink import Sink


@dataclass(frozen=True, kw_only=True)
class PluginRunContext:
    """Everything a plugin needs at run time — mirrors ImportRuntime, minus wiring."""

    params: dict[str, Any]
    organism_id: uuid.UUID | None
    load_upload: Callable[[uuid.UUID], Awaitable[bytes]]
    sink: Sink
    reporter: ProgressReporter
    auth: AuthContext
```

`backend/src/protcellar/application/plugins/protocol.py`:

```python
from __future__ import annotations

from typing import Protocol

from protcellar.application.plugins.context import PluginRunContext
from protcellar.application.plugins.manifest import PluginManifest


class IngestionPlugin(Protocol):
    """Structural — a plugin matches this shape; no base class (docu-store style)."""

    @staticmethod
    def manifest() -> PluginManifest: ...

    async def run(self, ctx: PluginRunContext) -> None: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/application/plugins/test_validation.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Verify layers are intact**

Run: `cd backend && uv run lint-imports`
Expected: all contracts kept — `application.plugins` imports only `application` + `domain`.

- [ ] **Step 6: Commit**

```bash
git add backend/src/protcellar/application/plugins backend/tests/unit/application/plugins
git commit -m "feat(ingestion-plugins): plugin contract (manifest/protocol/context/sink) + validation"
```

---

## Task 3: The in-tree sink

**Files:**
- Create: `backend/src/protcellar/infrastructure/plugins/__init__.py` (docstring only), `in_tree_sink.py`
- Create: `backend/tests/unit/infrastructure/plugins/__init__.py` (empty), `test_in_tree_sink.py`

**Interfaces:**
- Consumes: `Sink` (Task 2), `BulkUpsertEssentiality` + `BulkUpsertEssentialityCommand` (Task 1), `ItemResult`.
- Produces: `InTreeSink(*, essentiality: BulkUpsertEssentiality, organism_id: uuid.UUID | None, generation_method: str, source_run_id: uuid.UUID, dry_run: bool, auth: AuthContext)`. `.upsert("essentiality", records)` builds the command (stamping method/run/dry_run), calls the handler, accumulates results in `.results`, and returns them. Unknown `record_type` raises `ValueError`. Missing `organism_id` for essentiality raises `ValueError`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/infrastructure/plugins/test_in_tree_sink.py`:

```python
import uuid

import pytest
from returns.result import Success

from protcellar.application.target_biology._import_support import ItemResult
from protcellar.application.target_biology.bulk_upsert_essentiality import (
    BulkUpsertEssentialityCommand,
    EssentialityImportRecord,
)
from protcellar.infrastructure.plugins.in_tree_sink import InTreeSink
from tests.fakes.fake_auth import FakeAuth


class _FakeEssentiality:
    def __init__(self) -> None:
        self.commands: list[BulkUpsertEssentialityCommand] = []

    async def __call__(self, cmd: BulkUpsertEssentialityCommand, auth=None):
        self.commands.append(cmd)
        return Success([ItemResult(index=0, status="created", id="abc")])


def _sink(fake: _FakeEssentiality, *, organism_id: uuid.UUID | None, run_id: uuid.UUID) -> InTreeSink:
    return InTreeSink(
        essentiality=fake,  # type: ignore[arg-type]
        organism_id=organism_id,
        generation_method="imported",
        source_run_id=run_id,
        dry_run=False,
        auth=FakeAuth(role="admin"),
    )


@pytest.mark.asyncio
async def test_essentiality_upsert_stamps_and_accumulates() -> None:
    fake = _FakeEssentiality()
    org, run_id = uuid.uuid4(), uuid.uuid4()
    sink = _sink(fake, organism_id=org, run_id=run_id)
    out = await sink.upsert(
        "essentiality", [EssentialityImportRecord(locus_key="rpoB", classification="ES")]
    )
    assert [r.status for r in out] == ["created"]
    assert sink.results == out
    cmd = fake.commands[0]
    assert cmd.organism_id == org
    assert cmd.generation_method == "imported"
    assert cmd.source_run_id == run_id
    assert cmd.dry_run is False


@pytest.mark.asyncio
async def test_unknown_record_type_raises() -> None:
    sink = _sink(_FakeEssentiality(), organism_id=uuid.uuid4(), run_id=uuid.uuid4())
    with pytest.raises(ValueError):
        await sink.upsert("nope", [])


@pytest.mark.asyncio
async def test_essentiality_without_organism_raises() -> None:
    sink = _sink(_FakeEssentiality(), organism_id=None, run_id=uuid.uuid4())
    with pytest.raises(ValueError):
        await sink.upsert("essentiality", [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/infrastructure/plugins/test_in_tree_sink.py -v`
Expected: FAIL — `ModuleNotFoundError: protcellar.infrastructure.plugins.in_tree_sink`.

- [ ] **Step 3: Write minimal implementation**

`backend/src/protcellar/infrastructure/plugins/__init__.py`:

```python
"""Runnable plugin infrastructure: registry, in-tree sink, concrete plugins."""
```

`backend/src/protcellar/infrastructure/plugins/in_tree_sink.py`:

```python
from __future__ import annotations

import uuid
from collections.abc import Sequence

from protcellar.application.auth import AuthContext
from protcellar.application.plugins.sink import Sink
from protcellar.application.target_biology._import_support import ItemResult
from protcellar.application.target_biology.bulk_upsert_essentiality import (
    BulkUpsertEssentiality,
    BulkUpsertEssentialityCommand,
    EssentialityImportRecord,
)


class InTreeSink(Sink):
    """Routes record_type -> the wired BulkUpsert<X> command, stamping the run's
    generation_method + source_run_id + dry_run. Accumulates every ItemResult in
    ``results`` so the dispatch adapter can summarize the run."""

    def __init__(
        self,
        *,
        essentiality: BulkUpsertEssentiality,
        organism_id: uuid.UUID | None,
        generation_method: str,
        source_run_id: uuid.UUID,
        dry_run: bool,
        auth: AuthContext,
    ) -> None:
        self._essentiality = essentiality
        self._organism_id = organism_id
        self._generation_method = generation_method
        self._source_run_id = source_run_id
        self._dry_run = dry_run
        self._auth = auth
        self.results: list[ItemResult] = []

    async def upsert(self, record_type: str, records: Sequence[object]) -> list[ItemResult]:
        if record_type == "essentiality":
            if self._organism_id is None:
                raise ValueError("essentiality upsert requires an organism_id")
            cmd = BulkUpsertEssentialityCommand(
                organism_id=self._organism_id,
                records=tuple(records),  # type: ignore[arg-type]  # EssentialityImportRecord
                generation_method=self._generation_method,
                source_run_id=self._source_run_id,
                dry_run=self._dry_run,
            )
            out = (await self._essentiality(cmd, self._auth)).unwrap()
            self.results.extend(out)
            return out
        raise ValueError(f"no sink registered for record_type '{record_type}'")
```

`ponytail:` one record type today. Add the next branch (a dict route) only when the second record type ships — YAGNI until then. The unused `EssentialityImportRecord` import documents the expected element type; keep it.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/infrastructure/plugins/test_in_tree_sink.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/infrastructure/plugins/__init__.py backend/src/protcellar/infrastructure/plugins/in_tree_sink.py backend/tests/unit/infrastructure/plugins
git commit -m "feat(ingestion-plugins): in-tree sink over BulkUpsertEssentiality"
```

---

## Task 4: The DeJesus essentiality plugin

**Files:**
- Create: `backend/src/protcellar/infrastructure/plugins/dejesus_essentiality/__init__.py`, `manifest.py`, `plugin.py`
- Test: `backend/tests/unit/infrastructure/plugins/test_dejesus_plugin.py`

**Interfaces:**
- Consumes: `PluginManifest`/`ParamField`/`ParamType` (Task 2), `PluginRunContext` (Task 2), `EssentialityImportRecord` (Task 1), `parse_dejesus_essentiality` (existing, `infrastructure/ingestion/dejesus_essentiality.py`).
- Produces: module-level `plugin` (a `DejesusEssentialityPlugin`). `manifest().id == "dejesus_essentiality"`, `target_records=("essentiality",)`, `default_generation_method=IMPORTED`, params = `organism_id` (ORGANISM, required) + `upload` (FILE_UPLOAD, required) + `condition` (STRING, optional). `run(ctx)` loads the (already TSV-normalized) upload, parses it to `{locus: call}`, maps to `EssentialityImportRecord`s citing DeJesus 2017 (PMID 28096490), and calls `ctx.sink.upsert("essentiality", records)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/infrastructure/plugins/test_dejesus_plugin.py`:

```python
import uuid

import pytest

from protcellar.application.imports.progress_reporter import NoopProgressReporter
from protcellar.application.plugins.context import PluginRunContext
from protcellar.infrastructure.plugins.dejesus_essentiality import plugin
from tests.fakes.fake_auth import FakeAuth


class _FakeSink:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list]] = []

    async def upsert(self, record_type: str, records):
        self.upserts.append((record_type, list(records)))
        return []


async def _load_upload(_ref: uuid.UUID) -> bytes:
    return b"unused — parser is monkeypatched"


def test_manifest_shape() -> None:
    m = plugin.manifest()
    assert m.id == "dejesus_essentiality"
    assert m.target_records == ("essentiality",)
    assert {p.key for p in m.params} == {"organism_id", "upload", "condition"}


@pytest.mark.asyncio
async def test_run_maps_records_with_dejesus_citation(monkeypatch) -> None:
    monkeypatch.setattr(
        "protcellar.infrastructure.plugins.dejesus_essentiality.plugin.parse_dejesus_essentiality",
        lambda text: {"Rv0667": "essential", "Rv0668": "non-essential"},
    )
    sink = _FakeSink()
    ctx = PluginRunContext(
        params={"upload_ref": str(uuid.uuid4()), "organism_id": str(uuid.uuid4()), "condition": "7H9"},
        organism_id=uuid.uuid4(),
        load_upload=_load_upload,
        sink=sink,
        reporter=NoopProgressReporter(),
        auth=FakeAuth(role="admin"),
    )
    await plugin.run(ctx)
    record_type, records = sink.upserts[0]
    assert record_type == "essentiality"
    assert {r.locus_key for r in records} == {"Rv0667", "Rv0668"}
    assert all(r.pmid == "28096490" for r in records)
    assert all(r.dataset == "DeJesus 2017" for r in records)
    assert all(r.condition == "7H9" for r in records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/infrastructure/plugins/test_dejesus_plugin.py -v`
Expected: FAIL — `ModuleNotFoundError: ...dejesus_essentiality`.

- [ ] **Step 3: Write the plugin**

`backend/src/protcellar/infrastructure/plugins/dejesus_essentiality/__init__.py`:

```python
"""DeJesus 2017 essentiality plugin — the reference vertical."""

from protcellar.infrastructure.plugins.dejesus_essentiality.plugin import plugin

__all__ = ["plugin"]
```

`backend/src/protcellar/infrastructure/plugins/dejesus_essentiality/manifest.py`:

```python
from __future__ import annotations

from protcellar.application.plugins.manifest import ParamField, ParamType, PluginManifest
from protcellar.domain.shared.provenance import GenerationMethod

MANIFEST = PluginManifest(
    id="dejesus_essentiality",
    version="1.0.0",
    name="DeJesus essentiality",
    description="Load gene essentiality calls from a published DeJesus 2017 TnSeq table.",
    target_records=("essentiality",),
    default_generation_method=GenerationMethod.IMPORTED,
    params=(
        ParamField(
            key="organism_id",
            label="Organism",
            type=ParamType.ORGANISM,
            required=True,
            help="Strain the loci belong to (default M. tuberculosis H37Rv, tax 83332).",
        ),
        ParamField(
            key="upload",
            label="DeJesus table",
            type=ParamType.FILE_UPLOAD,
            required=True,
            help="Published essentiality table (XLSX/CSV/TSV; normalized to TSV on upload).",
        ),
        ParamField(
            key="condition",
            label="Condition",
            type=ParamType.STRING,
            required=False,
            help="Optional growth condition tagged on every row (e.g. 'in vitro 7H9').",
        ),
    ),
    requires_secrets=(),
)
```

`backend/src/protcellar/infrastructure/plugins/dejesus_essentiality/plugin.py`:

```python
from __future__ import annotations

import uuid

from protcellar.application.plugins.context import PluginRunContext
from protcellar.application.plugins.manifest import PluginManifest
from protcellar.application.target_biology.bulk_upsert_essentiality import EssentialityImportRecord
from protcellar.infrastructure.ingestion.dejesus_essentiality import parse_dejesus_essentiality
from protcellar.infrastructure.plugins.dejesus_essentiality.manifest import MANIFEST

_DEJESUS_PMID = "28096490"
_DEJESUS_DATASET = "DeJesus 2017"


class DejesusEssentialityPlugin:
    @staticmethod
    def manifest() -> PluginManifest:
        return MANIFEST

    async def run(self, ctx: PluginRunContext) -> None:
        # The upload endpoint already normalized XLSX/CSV -> TSV; load_upload
        # returns that TSV text. utf-8-sig tolerates a BOM from Excel exports.
        upload_ref = uuid.UUID(str(ctx.params["upload_ref"]))
        text = (await ctx.load_upload(upload_ref)).decode("utf-8-sig")
        calls = parse_dejesus_essentiality(text)  # {locus_tag: normalized_call}
        condition = ctx.params.get("condition") or None

        records = [
            EssentialityImportRecord(
                locus_key=locus,
                classification=call,
                condition=condition,
                method="TnSeq",
                pmid=_DEJESUS_PMID,
                dataset=_DEJESUS_DATASET,
            )
            for locus, call in calls.items()
        ]
        await ctx.reporter.advance(0, len(records))
        await ctx.sink.upsert("essentiality", records)
        await ctx.reporter.advance(len(records), len(records))


plugin = DejesusEssentialityPlugin()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/infrastructure/plugins/test_dejesus_plugin.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/infrastructure/plugins/dejesus_essentiality backend/tests/unit/infrastructure/plugins/test_dejesus_plugin.py
git commit -m "feat(ingestion-plugins): DeJesus essentiality reference plugin"
```

---

## Task 5: The registry + loader

**Files:**
- Create: `backend/src/protcellar/infrastructure/plugins/registry.py`
- Test: `backend/tests/unit/infrastructure/plugins/test_registry.py`

**Interfaces:**
- Consumes: `IngestionPlugin` (Task 2), the DeJesus `plugin` (Task 4).
- Produces: `ENABLED_PLUGINS: tuple[str, ...]` (dotted module paths); `get_plugin(plugin_id: str) -> IngestionPlugin` (raises `KeyError` on unknown id); `all_manifests() -> list[PluginManifest]`. Lazy, process-lifetime cache.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/infrastructure/plugins/test_registry.py`:

```python
import pytest

from protcellar.infrastructure.plugins.registry import all_manifests, get_plugin


def test_dejesus_is_registered() -> None:
    assert get_plugin("dejesus_essentiality").manifest().id == "dejesus_essentiality"


def test_unknown_plugin_raises() -> None:
    with pytest.raises(KeyError):
        get_plugin("does_not_exist")


def test_all_manifests_includes_dejesus() -> None:
    ids = {m.id for m in all_manifests()}
    assert "dejesus_essentiality" in ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/infrastructure/plugins/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: ...registry`.

- [ ] **Step 3: Write minimal implementation**

`backend/src/protcellar/infrastructure/plugins/registry.py`:

```python
from __future__ import annotations

import importlib

from protcellar.application.plugins.manifest import PluginManifest
from protcellar.application.plugins.protocol import IngestionPlugin

# Config-driven discovery: each path is a package exporting a module-level `plugin`.
ENABLED_PLUGINS: tuple[str, ...] = ("protcellar.infrastructure.plugins.dejesus_essentiality",)

_REGISTRY: dict[str, IngestionPlugin] | None = None


def _registry() -> dict[str, IngestionPlugin]:
    # ponytail: module-level lazy cache — fine for a process-lifetime registry.
    global _REGISTRY
    if _REGISTRY is None:
        loaded: dict[str, IngestionPlugin] = {}
        for path in ENABLED_PLUGINS:
            plugin: IngestionPlugin = importlib.import_module(path).plugin
            loaded[plugin.manifest().id] = plugin
        _REGISTRY = loaded
    return _REGISTRY


def get_plugin(plugin_id: str) -> IngestionPlugin:
    try:
        return _registry()[plugin_id]
    except KeyError as e:
        raise KeyError(f"unknown plugin '{plugin_id}'") from e


def all_manifests() -> list[PluginManifest]:
    return [p.manifest() for p in _registry().values()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/infrastructure/plugins/test_registry.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/src/protcellar/infrastructure/plugins/registry.py backend/tests/unit/infrastructure/plugins/test_registry.py
git commit -m "feat(ingestion-plugins): config-driven plugin registry + loader"
```

---

## Task 6: Wire plugin execution into the worker via `ImportType.PLUGIN`

**Files:**
- Modify: `backend/src/protcellar/domain/imports/enums.py`
- Modify: `backend/src/protcellar/infrastructure/ingestion/import_adapters.py`
- Modify: `backend/src/protcellar/infrastructure/ingestion/worker.py`
- Modify: `backend/src/protcellar/application/imports/params.py`
- Test: `backend/tests/unit/application/imports/test_plugin_params.py`
- Test: `backend/tests/unit/infrastructure/plugins/test_plugin_dispatch.py`
- Existing invariant test: `backend/tests/unit/infrastructure/test_import_adapters.py` (should still pass unchanged)

**Interfaces:**
- Produces:
  - `ImportType.PLUGIN = "plugin"`.
  - `ImportRuntime` gains `run_id: uuid.UUID` (defaulted so legacy construction/tests need no change; the worker injects the real `run.id`).
  - `PluginDispatchAdapter` (`import_type = ImportType.PLUGIN`); `IMPORT_ADAPTERS[ImportType.PLUGIN] = PluginDispatchAdapter()`.
  - `_summarize(results: list[ItemResult]) -> dict[str, Any]` → `{created, updated, skipped, failed, total}`.
  - `params.py`: `validate_params(PLUGIN, raw)` passes through; `target_key(PLUGIN, params)` = `f"{plugin_id}:{strain}:{dry|run}"`; `upload_ref_of(PLUGIN, params)` reads `params["upload_ref"]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/unit/application/imports/test_plugin_params.py`:

```python
import uuid

from protcellar.application.imports.params import target_key, upload_ref_of, validate_params
from protcellar.domain.imports.enums import ImportType


def test_validate_params_plugin_passthrough() -> None:
    raw = {"plugin_id": "dejesus_essentiality", "organism_id": "x", "junk": 1}
    assert validate_params(ImportType.PLUGIN, raw) == raw


def test_target_key_includes_plugin_and_dry_flag() -> None:
    params = {"plugin_id": "dejesus_essentiality", "organism_id": "org-1", "dry_run": True}
    assert target_key(ImportType.PLUGIN, params) == "dejesus_essentiality:org-1:dry"
    params["dry_run"] = False
    assert target_key(ImportType.PLUGIN, params) == "dejesus_essentiality:org-1:run"


def test_upload_ref_of_reads_upload_ref() -> None:
    ref = uuid.uuid4()
    assert upload_ref_of(ImportType.PLUGIN, {"upload_ref": str(ref)}) == ref
    assert upload_ref_of(ImportType.PLUGIN, {"plugin_id": "x"}) is None
```

Create `backend/tests/unit/infrastructure/plugins/test_plugin_dispatch.py`:

```python
from protcellar.application.target_biology._import_support import ItemResult
from protcellar.infrastructure.ingestion.import_adapters import _summarize


def test_summarize_tallies_statuses() -> None:
    results = [
        ItemResult(index=0, status="created"),
        ItemResult(index=1, status="created"),
        ItemResult(index=2, status="updated"),
        ItemResult(index=3, status="failed", error="x"),
    ]
    assert _summarize(results) == {
        "created": 2,
        "updated": 1,
        "skipped": 0,
        "failed": 1,
        "total": 4,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/unit/application/imports/test_plugin_params.py tests/unit/infrastructure/plugins/test_plugin_dispatch.py -v`
Expected: FAIL — `AttributeError: PLUGIN` / `ImportError: cannot import name '_summarize'`.

- [ ] **Step 3: Add `ImportType.PLUGIN`**

In `backend/src/protcellar/domain/imports/enums.py`, add the member to `ImportType`:

```python
class ImportType(StrEnum):
    PROTEOME = "proteome"
    GENE_ENRICHMENT = "gene_enrichment"
    GO_ONTOLOGY = "go_ontology"
    PLUGIN = "plugin"
```

- [ ] **Step 4: Extend `params.py` with PLUGIN branches**

In `backend/src/protcellar/application/imports/params.py`, add a passthrough at the top of `validate_params` and branches at the top of `target_key` and `upload_ref_of`:

```python
def validate_params(import_type: ImportType, raw: dict[str, Any]) -> dict[str, Any]:
    if import_type is ImportType.PLUGIN:
        # Already validated against the plugin manifest at the route boundary.
        return dict(raw)
    model_cls = _PARAM_MODELS[import_type]
    ...  # unchanged
```

```python
def target_key(import_type: ImportType, params: dict[str, Any]) -> str:
    if import_type is ImportType.PLUGIN:
        strain = params.get("organism_id") or params.get("tax_id") or "global"
        return f"{params['plugin_id']}:{strain}:{'dry' if params.get('dry_run') else 'run'}"
    if import_type is ImportType.PROTEOME:
        ...  # unchanged
```

```python
def upload_ref_of(import_type: ImportType, params: dict[str, Any]) -> uuid.UUID | None:
    if import_type is ImportType.PLUGIN:
        ref = params.get("upload_ref")
        return uuid.UUID(str(ref)) if ref else None
    if import_type is ImportType.GENE_ENRICHMENT:
        ...  # unchanged
```

- [ ] **Step 5: Add `run_id` to `ImportRuntime` + `PluginDispatchAdapter` + `_summarize`**

In `backend/src/protcellar/infrastructure/ingestion/import_adapters.py`, add these imports near the other application/infra imports:

```python
from protcellar.application.plugins.context import PluginRunContext
from protcellar.application.target_biology._import_support import ItemResult
from protcellar.application.target_biology.bulk_upsert_essentiality import BulkUpsertEssentiality
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.plugins.in_tree_sink import InTreeSink
from protcellar.infrastructure.plugins.registry import get_plugin
```

Add `run_id` to `ImportRuntime` (append as the last field, defaulted so existing construction sites and `test_import_adapters.py`'s runtime helper need no change):

```python
@dataclass(frozen=True)
class ImportRuntime:
    """All cross-cutting dependencies the worker hands to an adapter."""

    session_factory: async_sessionmaker[AsyncSession]
    dispatcher: EventDispatcherProtocol
    reporter: ProgressReporter
    params: dict[str, Any]
    auth: AuthContext
    load_upload: Callable[[uuid.UUID], Awaitable[bytes]]
    # ponytail: defaulted so legacy adapters/tests need no change; the worker
    # always injects the real ImportRun id for plugin lineage.
    run_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)
```

Add the dispatch adapter + summarizer (place near the other adapters, above `IMPORT_ADAPTERS`):

```python
def _summarize(results: list[ItemResult]) -> dict[str, Any]:
    summary: dict[str, Any] = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
    for r in results:
        if r.status in summary:
            summary[r.status] += 1
    summary["total"] = len(results)
    return summary


class PluginDispatchAdapter:
    """ImportType.PLUGIN -> resolve rt.params['plugin_id'] from the registry, wire the
    in-tree sink, run the plugin, and summarize. The worker's IMPORT_ADAPTERS lookup
    dispatches here with no plugin-specific branching in worker.py."""

    import_type = ImportType.PLUGIN

    async def run(self, rt: ImportRuntime) -> dict[str, Any]:
        params = rt.params
        plugin = get_plugin(str(params["plugin_id"]))
        manifest = plugin.manifest()
        organism_id = (
            uuid.UUID(str(params["organism_id"])) if params.get("organism_id") else None
        )
        dry_run = bool(params.get("dry_run", False))

        uow = AsyncUnitOfWork(rt.session_factory)
        gene_repo = SQLAlchemyGeneRepository(uow)
        ess_repo = SQLAlchemyEssentialityRepository(uow)
        essentiality = BulkUpsertEssentiality(uow, gene_repo, ess_repo, rt.dispatcher)

        sink = InTreeSink(
            essentiality=essentiality,
            organism_id=organism_id,
            generation_method=manifest.default_generation_method.value,
            source_run_id=rt.run_id,
            dry_run=dry_run,
            auth=rt.auth,
        )
        ctx = PluginRunContext(
            params=params,
            organism_id=organism_id,
            load_upload=rt.load_upload,
            sink=sink,
            reporter=rt.reporter,
            auth=rt.auth,
        )
        await plugin.run(ctx)
        return _summarize(sink.results)
```

Add the registry entry:

```python
IMPORT_ADAPTERS: dict[ImportType, ImportAdapter] = {
    ImportType.PROTEOME: ProteomeAdapter(),
    ImportType.GENE_ENRICHMENT: GeneEnrichmentAdapter(),
    ImportType.GO_ONTOLOGY: GoOntologyAdapter(),
    ImportType.PLUGIN: PluginDispatchAdapter(),
}
```

- [ ] **Step 6: Pass `run_id` from the worker**

In `backend/src/protcellar/infrastructure/ingestion/worker.py`, add `run_id=run.id,` to the `ImportRuntime(...)` construction (in `run_import`, step "Build ImportRuntime"):

```python
    rt = ImportRuntime(
        session_factory=session_factory,
        dispatcher=dispatcher,
        reporter=ImportRunProgressReporter(run.id, session_factory),
        params=run.params,
        auth=ServiceAuth(),
        load_upload=_load_upload,
        run_id=run.id,
    )
```

- [ ] **Step 7: Run the new + invariant tests**

Run:
```bash
cd backend && uv run pytest \
  tests/unit/application/imports/test_plugin_params.py \
  tests/unit/infrastructure/plugins/test_plugin_dispatch.py \
  tests/unit/infrastructure/test_import_adapters.py -v
```
Expected: all PASS — including `test_import_adapters.py`'s `set(IMPORT_ADAPTERS) == set(ImportType)` and `adapter.import_type is key` (now covering `PLUGIN`).

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/domain/imports/enums.py backend/src/protcellar/infrastructure/ingestion/import_adapters.py backend/src/protcellar/infrastructure/ingestion/worker.py backend/src/protcellar/application/imports/params.py backend/tests/unit/application/imports/test_plugin_params.py backend/tests/unit/infrastructure/plugins/test_plugin_dispatch.py
git commit -m "feat(ingestion-plugins): dispatch plugin runs via ImportType.PLUGIN adapter"
```

---

## Task 7: Plugins API — catalog + run starter + `job_timeout`

**Files:**
- Create: `backend/src/protcellar/interface/routes/plugins.py`
- Modify: `backend/src/protcellar/interface/app.py` (register the router)
- Modify: `backend/tests/api/conftest.py` (register the router in the test app `_create_test_app`)
- Modify: `backend/src/protcellar/infrastructure/ingestion/worker.py` (set `job_timeout`)
- Test: `backend/tests/api/test_plugins_api.py`

**Interfaces:**
- Consumes: `all_manifests`/`get_plugin` (Task 5), `validate_against_manifest`/`ParamType` (Task 2), `StartImportCommand`, `ImportRunResponse` (from `interface/routes/imports.py`).
- Produces:
  - `GET /api/v1/plugins` → `list[PluginManifestResponse]`.
  - `POST /api/v1/plugins/{plugin_id}/runs` (body `{params: {...}, dry_run: bool}`) → `202 ImportRunResponse`. Unknown id → 404; bad params → 422.
  - `WorkerSettings.job_timeout` set (stopgap for long runs; arq has no default).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/api/test_plugins_api.py`. The `client` fixture (`tests/api/conftest.py:113`) is an `httpx.AsyncClient` over the test app with admin `FakeAuth` already wired — use it directly:

```python
import pytest

pytestmark = pytest.mark.asyncio


async def test_list_plugins_includes_dejesus(client) -> None:
    resp = await client.get("/api/v1/plugins")
    assert resp.status_code == 200
    manifests = resp.json()
    dejesus = next(m for m in manifests if m["id"] == "dejesus_essentiality")
    assert dejesus["target_records"] == ["essentiality"]
    assert {p["key"] for p in dejesus["params"]} == {"organism_id", "upload", "condition"}


async def test_unknown_plugin_run_is_404(client) -> None:
    resp = await client.post("/api/v1/plugins/nope/runs", json={"params": {}})
    assert resp.status_code == 404


async def test_missing_required_param_is_422(client) -> None:
    # organism_id + upload are required; omit them.
    resp = await client.post("/api/v1/plugins/dejesus_essentiality/runs", json={"params": {}})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/api/test_plugins_api.py -v`
Expected: FAIL — 404 for `GET /api/v1/plugins` (route not registered).

- [ ] **Step 3: Write the plugins route**

`backend/src/protcellar/interface/routes/plugins.py`:

```python
"""Plugin catalog + plugin-run endpoints. A plugin run IS an ImportRun."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from protcellar.application.imports.start_import import StartImportCommand
from protcellar.application.plugins.manifest import ParamField, ParamType, PluginManifest
from protcellar.application.plugins.validation import validate_against_manifest
from protcellar.domain.imports.enums import ImportType
from protcellar.domain.shared.errors import DomainError
from protcellar.infrastructure.plugins.registry import all_manifests, get_plugin
from protcellar.interface.dependencies import AuthDep, StartImportDep
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.routes.imports import ImportRunResponse

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


class ParamFieldResponse(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    default: Any | None = None
    options: list[str] = []
    help: str | None = None

    @classmethod
    def from_domain(cls, p: ParamField) -> ParamFieldResponse:
        return cls(
            key=p.key,
            label=p.label,
            type=p.type.value,
            required=p.required,
            default=p.default,
            options=list(p.options),
            help=p.help,
        )


class PluginManifestResponse(BaseModel):
    id: str
    version: str
    name: str
    description: str
    target_records: list[str]
    default_generation_method: str
    params: list[ParamFieldResponse]
    requires_secrets: list[str]

    @classmethod
    def from_domain(cls, m: PluginManifest) -> PluginManifestResponse:
        return cls(
            id=m.id,
            version=m.version,
            name=m.name,
            description=m.description,
            target_records=list(m.target_records),
            default_generation_method=m.default_generation_method.value,
            params=[ParamFieldResponse.from_domain(p) for p in m.params],
            requires_secrets=list(m.requires_secrets),
        )


class StartPluginRunBody(BaseModel):
    params: dict[str, Any] = {}
    dry_run: bool = False


@router.get("", response_model=list[PluginManifestResponse])
async def list_plugins(auth: AuthDep) -> list[PluginManifestResponse]:
    return [PluginManifestResponse.from_domain(m) for m in all_manifests()]


@router.post("/{plugin_id}/runs", response_model=ImportRunResponse, status_code=202)
async def start_plugin_run(
    plugin_id: str,
    body: StartPluginRunBody,
    auth: AuthDep,
    use_case: StartImportDep,
) -> ImportRunResponse:
    try:
        manifest = get_plugin(plugin_id).manifest()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        validated = validate_against_manifest(manifest, body.params)
    except DomainError as e:
        raise HTTPException(status_code=422, detail=e.message) from e

    params: dict[str, Any] = {**validated, "plugin_id": plugin_id, "dry_run": bool(body.dry_run)}
    file_field = next((p for p in manifest.params if p.type is ParamType.FILE_UPLOAD), None)
    if file_field is not None and file_field.key in params:
        params["upload_ref"] = params[file_field.key]

    command = StartImportCommand(import_type=ImportType.PLUGIN, params=params)
    run = result_to_response(await use_case(command, auth=auth))
    return ImportRunResponse.from_domain(run)
```

- [ ] **Step 4: Register the router (production app + test app)**

In `backend/src/protcellar/interface/app.py`, next to the other `include_router` calls (e.g. after the imports router):

```python
from protcellar.interface.routes.plugins import router as plugins_router

app.include_router(plugins_router)
```

The api test app is built separately by `tests/api/conftest.py:_create_test_app`, which registers routers explicitly — add the plugins router there too (import it alongside the other route routers and `app.include_router(plugins_router)` after `imports_router`), or the api test will 404.

- [ ] **Step 5: Set an explicit `job_timeout` (arq stopgap)**

In `backend/src/protcellar/infrastructure/ingestion/worker.py`, add a `job_timeout` to `WorkerSettings` (arq sets none by default — a long AI-mining plugin run would otherwise be aborted mid-flight):

```python
class WorkerSettings:
    """arq WorkerSettings — mirrors the lifespan wiring in ``interface/app.py``."""

    functions: ClassVar[list[Any]] = [run_import]
    redis_settings = redis_settings_from_env()
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    # ponytail: explicit 30-min ceiling (arq default is unset). Climb to Temporal
    # only when a plugin needs durable multi-hour runs (spec §7).
    job_timeout = 1800
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/api/test_plugins_api.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Regenerate the API client**

Run: `make generate-api`
Expected: a new `frontend/src/shared/lib/api/plugins/plugins.ts` (with `listPluginsApiV1PluginsGet` + `useListPluginsApiV1PluginsGet` + a `startPluginRun…` mutation) and model files `pluginManifestResponse.ts`, `paramFieldResponse.ts`, `startPluginRunBody.ts`. Confirm:

```bash
cd frontend && ls src/shared/lib/api/plugins && grep -l dejesus src/shared/lib/api/model/*.ts || echo "(models are structural; check pluginManifestResponse.ts exists)" && ls src/shared/lib/api/model/pluginManifestResponse.ts
```

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/interface/routes/plugins.py backend/src/protcellar/interface/app.py backend/tests/api/conftest.py backend/src/protcellar/infrastructure/ingestion/worker.py backend/tests/api/test_plugins_api.py frontend/openapi.json frontend/src/shared/lib/api
git commit -m "feat(ingestion-plugins): GET /plugins + POST /plugins/{id}/runs + job_timeout"
```

---

## Task 8: End-to-end plugin run + full gates

**Files:**
- Test: `backend/tests/api/test_plugins_api.py` (extend with a worker-driven run)

**Interfaces:**
- Consumes: everything above. Verifies a plugin run drives `QUEUED → RUNNING → SUCCEEDED`, writes an `Essentiality` record with `generation_method=imported` and `extensions["source_run_id"]`, and reports a created/updated/skipped/failed summary.

- [ ] **Step 1: Write the end-to-end test**

Create `backend/tests/api/test_plugin_run.py`, following the exact worker-driving pattern of `tests/api/test_import_worker.py` (raw engine/factory + `run_import(_ctx(factory), str(run_id))`, no live Redis). It seeds a gene + a stored TSV upload, seeds a PLUGIN `ImportRun`, drives the worker, and asserts the run + the written record:

```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.imports.store_upload import StoreUpload
from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.infrastructure.ingestion import worker as worker_mod
from protcellar.infrastructure.messaging.event_dispatcher import EventDispatcher
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_run_repository import (
    SQLAlchemyImportRunRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.imports.import_upload_repository import (
    SQLAlchemyImportUploadRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from tests.fakes.fake_auth import FakeAuth

pytestmark = pytest.mark.asyncio


def _ctx(factory) -> dict:
    return {"session_factory": factory, "dispatcher": EventDispatcher()}


async def test_dejesus_plugin_run_creates_essentiality(
    database_url: str, _run_migrations: None
) -> None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    admin = FakeAuth(role="admin", workspace_id=uuid.uuid4(), user_id=uuid.uuid4())
    org = uuid.uuid4()
    try:
        # Seed a gene whose locus matches the TSV.
        gene = Gene.create(primary_name="Rv0667", organism_id=org)
        async with AsyncUnitOfWork(factory) as uow:
            await SQLAlchemyGeneRepository(uow).save(gene)
            await uow.commit()

        # Store an already-TSV-normalized upload (StoreUpload manages its own uow).
        uow = AsyncUnitOfWork(factory)
        store = StoreUpload(uow, SQLAlchemyImportUploadRepository(uow))
        upload = (
            await store(
                filename="dejesus.tsv",
                content_type="text/tab-separated-values",
                data=b"Rv0667\tES\n",
                auth=admin,
            )
        ).unwrap()

        # Seed a PLUGIN run and drive the worker.
        run = ImportRun.create(
            import_type=ImportType.PLUGIN,
            params={
                "plugin_id": "dejesus_essentiality",
                "organism_id": str(org),
                "upload": str(upload.id),
                "upload_ref": str(upload.id),
            },
            target_key=f"dejesus_essentiality:{org}:run",
            requested_by=admin.user_id,
            upload_ref=upload.id,
        )
        async with AsyncUnitOfWork(factory) as uow:
            await SQLAlchemyImportRunRepository(uow).save(run)
            await uow.commit()

        await worker_mod.run_import(_ctx(factory), str(run.id))

        async with AsyncUnitOfWork(factory) as uow:
            reloaded = await SQLAlchemyImportRunRepository(uow).get(run.id)
            assert reloaded.status is ImportStatus.SUCCEEDED
            assert reloaded.summary["created"] == 1

            records = await SQLAlchemyEssentialityRepository(uow).find_by_gene(
                GLOBAL_WORKSPACE_ID, gene.id
            )
            assert len(records) == 1
            assert records[0].provenance.generation_method.value == "imported"
            assert records[0].extensions["source_run_id"] == str(run.id)
    finally:
        await engine.dispose()
```

> `parse_dejesus_essentiality` must accept the seeded TSV. `b"Rv0667\tES\n"` is a two-column `locus<TAB>call` line (tab in the first line → the parser's TSV branch). If, on running, the parser requires a header row, inspect `infrastructure/ingestion/dejesus_essentiality.py` and prepend the exact header it expects (a one-line fixture change). Also confirm `StoreUpload.__call__`'s keyword names against `application/imports/store_upload.py:30` and adjust the `store(...)` call if they differ. The four assertions (status, `created` count, `generation_method`, `source_run_id`) are the acceptance criteria — keep them.

- [ ] **Step 2: Run the end-to-end test**

Run: `cd backend && uv run pytest tests/api/test_plugin_run.py -v`
Expected: PASS — the plugin run succeeds and the essentiality record carries the `imported` method + run lineage.

- [ ] **Step 3: Full gates**

Run:
```bash
cd backend && uv run pytest tests/unit -v && uv run lint-imports
make test-api
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src
```
Expected: unit PASS; `lint-imports` reports all contracts kept (crucially: `application.plugins` never imports infrastructure; `application.imports.params` gained no registry import); api PASS (except the two documented pre-existing proteome isolation failures); ruff/mypy clean.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/api/test_plugin_run.py
git commit -m "test(ingestion-plugins): end-to-end DeJesus plugin run + lineage"
```

---

## Self-Review (checked against the spec §3, §4, §6, §7, §10)

- **§3 three concepts** — Plugin (`manifest()` + `run(ctx)`, Task 4) ✓; Envelope (`ctx.sink.upsert(record_type, records)`, Task 3) ✓; Run (reuses `ImportRun`, Task 6) ✓.
- **§4 contract** — framework attaches `generation_method` (manifest default) + `source_run_id` + `organism_id`; plugin writes fetch-and-map only ✓ (Tasks 3–4). In-tree sink resolves record_type → `BulkUpsertEssentiality`; `dry_run` passthrough ✓; per-row `ItemResult`s merge into the summary ✓ (`_summarize`, Task 6).
- **§6 anatomy** — `manifest.py`/`plugin.py`/`__init__.py` (module-level `plugin` attr) ✓; `ParamField` constrained descriptor with the exact 6 types ✓; structural `IngestionPlugin` Protocol ✓; config-driven `importlib` discovery + `GET /plugins` ✓.
- **§7 execution & ladder** — plugin run IS an `ImportRun` on the existing arq worker; no new engine ✓; explicit `job_timeout` stopgap set ✓ (Task 7). Second-worker/Temporal rungs deferred (unchanged).
- **§10 first plugin** — DeJesus wraps the existing normalizer (via the upload endpoint's `essentiality_upload_to_tsv`) + `parse_dejesus_essentiality` + `BulkUpsertEssentiality`; stamps `imported` + lineage ✓; demonstrates the file-upload shape ✓.
- **§8 safety** — trace by `source_run_id` (in `extensions`, v1) ✓; dry-run preview supported via a `dry_run` plugin run (the FE flow is Plan C) ✓; human-edit-flips-to-manual is Plan A ✓. Undo *button* remains v1.1 (deferred).
- **Layers** — contract in `application/plugins`; runnable in `infrastructure/plugins`; routes in `interface`; `params.py` registry-free — all enforced by `lint-imports` in Task 8 ✓.
- **Type consistency** — `generation_method` is a `str` on the command/sink/response and a `GenerationMethod` on the VO (converted at the `_provenance` boundary); `PluginManifest`/`ParamField`/`ParamType` names identical across contract, plugin, registry, and route.
- **Legacy importers** — untouched; catalog coexists with the existing dialog (their migration to manifests is deferred, see Plan C scope note).
