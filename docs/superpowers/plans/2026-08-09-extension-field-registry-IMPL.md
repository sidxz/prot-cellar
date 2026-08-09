# Extension Field Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a workspace admin declare what extra fields each target-biology record kind carries, publish those declarations through the existing descriptor, and render and edit their values.

**Architecture:** One workspace-scoped registry table in `workspace_config`, alongside organizations and tags. Its declarations flow into `GET /target-biology/schema` as a `extension_fields` array per kind — separate from `fields`, so a client that predates the feature keeps working. `extensions` becomes writable, validated in the application layer against the registry.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, `returns` Result, pytest (`asyncio_mode = "auto"`), Next.js 15 + orval, biome, vitest.

**Spec:** `docs/superpowers/specs/2026-08-09-extension-field-registry-design.md`. Read §2 (field types), §3 (why the array is separate) and §5 (merge semantics) before starting.

## Global Constraints

- **Branch `feat/workspace-scoping`.** Add commits; never amend a reviewed one.
- **⚠️ `interface/routes/target_biology.py` carries commit `10735a1` from a different session.** `_patch_updates`'s null branch keeps `compound` (a null **clears** the reference) while `provenance` and `ligands` keep null-means-leave-alone; the eight patch bodies and the descriptor also come from there. **Open the file, add only what you own, reproduce nothing.** Tasks 4-10 of the tenancy work all edited it safely by surgical addition — one had a 17-insertion/0-deletion diff. Match that.
- **Field types are `string`, `text`, `number`, `integer`, `boolean`, `date`, `enum`.** This is the descriptor's existing vocabulary. `list`, `reference` and `object` are excluded. A sibling application models `enum` as "string + allowed_values"; **do not copy that** — this service's descriptor already emits `"type": "enum"` with `"options"` for core fields such as `classification`.
- **`name` is immutable after creation.** `label`, `field_type`, `options`, `position` and `show_in_table` stay editable.
- **Deleting a definition never deletes stored values.** They render as *unmapped*.
- **Reads use `readable_by`; every mutation uses `owned_by`.** Predicates live in `infrastructure/persistence/sqlalchemy/workspace_scope.py`. Collapsing them lets one tenant edit another's data.
- `SHARED_WORKSPACE_ID` is `a577f0f9-b1fb-53b6-be5d-49bcb500adeb`, in `domain/shared/global_workspace.py`.
- Admin surfaces use the existing `require_admin`, a per-workspace role check.
- mypy strict; `ruff format` line-length 99; `alembic/` is outside the lint path and its migrations use the `typing.Sequence`/`Union` template style — match it, don't modernise.
- Verify with `make test`, `make test-api`, `make lint`, `make test-fe`, `make lint-fe`, `cd frontend && pnpm exec tsc --noEmit`. Run `make generate-api` whenever a response shape changes.
- **Baseline, never yours:** `make lint` stops at a pre-existing `app.py:45` E501; `mypy src` 52 errors/12 files (all the lagom `Container.define()` pattern); `make test-api` 2 pre-existing order-dependent failures (`test_organisms.py`, `test_plugin_run.py`); `make test` clean; a pre-existing `lint-fe` import-order warning.
- **This service must remain unaware of any consumer.** In-repo context names (`target_biology`, `workspace_config`) are fine; naming a downstream application is not.
- Docker is required for API tests. If unavailable, report BLOCKED rather than skipping.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/src/protcellar/domain/workspace_config/extension_fields/field_def.py` | *Create.* The `ExtensionFieldDef` aggregate and `ExtensionFieldType` enum. Owns the immutability rule. |
| `.../domain/workspace_config/extension_fields/repository.py` | *Create.* `ExtensionFieldDefRepository` Protocol. |
| `.../domain/workspace_config/extension_fields/events.py` | *Create.* Created/Updated/Deleted domain events. |
| `.../infrastructure/persistence/sqlalchemy/workspace_config/models.py` | *Modify.* Add `ExtensionFieldDefModel`. |
| `.../infrastructure/persistence/sqlalchemy/workspace_config/extension_field_def_repository.py` | *Create.* The adapter. |
| `backend/alembic/versions/*_extension_field_defs.py` | *Create.* The table. |
| `.../application/workspace_config/extension_fields/{list,create,update,delete}_field_def.py` | *Create.* One use case per file, matching the tagging layout. |
| `.../application/target_biology/extension_validator.py` | *Create.* Validates and merges a submitted `extensions` bag. Nothing else. |
| `.../interface/routes/extension_fields.py` | *Create.* Admin CRUD routes. |
| `.../interface/target_biology_schema.py` | *Modify.* Emit `extension_fields`; empty `_READ_ONLY`. |
| `.../interface/routes/target_biology.py` | *Modify.* `extensions` on write bodies. **Concurrent history.** |
| `frontend/src/features/extension-fields/**` | *Create.* Kind list, kind editor, field rows. |
| `frontend/src/app/(dashboard)/admin/extension-fields/**` | *Create.* Thin route pages. |
| `frontend/.../sections/extension-values-dialog.tsx` | *Create.* The edit surface. |
| `frontend/.../sections/editable-record-table.tsx` | *Modify.* Columns + unmapped detail. |

---

### Task 1: The aggregate, the table, and the repository

**Files:**
- Create: `backend/src/protcellar/domain/workspace_config/extension_fields/{__init__.py,field_def.py,repository.py,events.py}`
- Modify: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/workspace_config/models.py`
- Create: `backend/src/protcellar/infrastructure/persistence/sqlalchemy/workspace_config/extension_field_def_repository.py`
- Create: `backend/alembic/versions/e3c9a1f7b508_extension_field_defs.py`
- Test: `backend/tests/unit/domain/workspace_config/test_extension_field_def.py`

**Interfaces:**
- Produces: `ExtensionFieldType` (StrEnum), `ExtensionFieldDef` aggregate with `rename_label_and_shape(...)`, `ExtensionFieldDefRepository` Protocol with `list_for_kind`, `find_owned`, `save`, `delete`.
- Consumes: `AggregateRoot` (`domain/shared/entity.py`), the mixins in `infrastructure/persistence/sqlalchemy/base.py`, `readable_by`/`owned_by`.

**Model this on the tagging capability** (`domain/workspace_config/tagging/`) — same directory shape, same Protocol style, same `AggregateRoot` base.

- [ ] **Step 1: Write the failing domain test**

```python
"""The two rules that are not obvious: name is immutable, options belong to enums."""

from __future__ import annotations

import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)

WS = uuid.uuid4()


def _def(**kw: object) -> ExtensionFieldDef:
    base = dict(
        workspace_id=WS, kind="vulnerability", name="vi_lower_bound",
        label="VI lower bound", field_type=ExtensionFieldType.NUMBER,
        options=None, position=0, show_in_table=False,
    )
    base.update(kw)
    return ExtensionFieldDef.create(**base)  # type: ignore[arg-type]


def test_name_is_immutable_after_creation() -> None:
    d = _def()
    with pytest.raises(AttributeError):
        d.name = "something_else"  # type: ignore[misc]


def test_update_changes_label_and_shape_but_not_name() -> None:
    d = _def()
    d.update(label="Lower bound", field_type=ExtensionFieldType.STRING,
             options=None, position=3, show_in_table=True)
    assert (d.name, d.label, d.position, d.show_in_table) == (
        "vi_lower_bound", "Lower bound", 3, True)


def test_enum_requires_options() -> None:
    with pytest.raises(ValidationError):
        _def(field_type=ExtensionFieldType.ENUM, options=None)
    with pytest.raises(ValidationError):
        _def(field_type=ExtensionFieldType.ENUM, options=[])


def test_non_enum_rejects_options() -> None:
    with pytest.raises(ValidationError):
        _def(field_type=ExtensionFieldType.NUMBER, options=["a"])


@pytest.mark.parametrize("bad", ["", "  ", "has space", "Has-Dash", "1leading"])
def test_name_must_be_a_snake_case_identifier(bad: str) -> None:
    with pytest.raises(ValidationError):
        _def(name=bad)
```

The `name` rule matters because the value is a JSON object key and ends up in URLs and column
headers. Enforce `^[a-z][a-z0-9_]*$`.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/unit/domain/workspace_config/test_extension_field_def.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the aggregate**

`field_def.py` defines `ExtensionFieldType` (`STRING`, `TEXT`, `NUMBER`, `INTEGER`, `BOOLEAN`,
`DATE`, `ENUM`) and `ExtensionFieldDef(AggregateRoot)`.

Make `name` a read-only property backed by a private attribute so assignment raises `AttributeError`
— the test asserts that, and a mutable `name` orphans stored values. `create()` and `update()` both
validate: enum ⇒ non-empty `options`; non-enum ⇒ `options is None`; `name` matches
`^[a-z][a-z0-9_]*$`. `update()` never touches `name`. Register `ExtensionFieldDefCreated` /
`Updated` / `Deleted` events, mirroring `tagging/events.py`.

- [ ] **Step 4: Write the repository Protocol**

```python
@runtime_checkable
class ExtensionFieldDefRepository(Protocol):
    async def list_for_kind(
        self, workspace_id: uuid.UUID, kind: str
    ) -> list[ExtensionFieldDef]:
        """Definitions this workspace declared for one kind, ordered by position.

        `readable_by`: a workspace sees its own declarations. Shared reference data
        carries no declarations of its own — see the spec's §1 on unmapped values.
        """
        ...

    async def list_all(self, workspace_id: uuid.UUID) -> list[ExtensionFieldDef]: ...

    async def find_owned(
        self, workspace_id: uuid.UUID, id: uuid.UUID
    ) -> ExtensionFieldDef | None: ...

    async def find_by_name(
        self, workspace_id: uuid.UUID, kind: str, name: str
    ) -> ExtensionFieldDef | None: ...

    async def save(self, aggregate: ExtensionFieldDef) -> None: ...

    async def delete(self, workspace_id: uuid.UUID, id: uuid.UUID) -> None: ...
```

- [ ] **Step 5: Add the ORM model and the migration**

In `workspace_config/models.py`:

```python
class ExtensionFieldDefModel(Base, EntityModelMixin, WorkspaceIdMixin, VersionMixin):
    """A workspace's declaration of one extra field on one target-biology record kind.

    `name` is the key inside that kind's `extensions` JSONB bag. It is immutable in the
    domain: renaming it would orphan every stored value.
    """

    __tablename__ = "extension_field_defs"
    __table_args__ = (
        Index("uq_extension_field_defs_ws_kind_name", "workspace_id", "kind", "name", unique=True),
        Index("ix_extension_field_defs_ws_kind", "workspace_id", "kind"),
    )

    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    options: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    show_in_table: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

`JSONB`, not `JSON` — commit `117f290` converted this schema and a new `JSON` column would
reintroduce a type that cannot be indexed or compared.

Write the migration with `down_revision = 'd2b5f9c8e314'` (confirm with `uv run alembic heads`),
matching the existing `typing.Sequence`/`Union` template style. Apply it with `make migrate`.

- [ ] **Step 6: Write the SQLAlchemy adapter**

`extension_field_def_repository.py`, subclassing the same base the tagging repositories use.
`list_for_kind` and `list_all` filter with `readable_by`; `find_owned` and `delete` use `owned_by`.
Order by `position`, then `name` as a stable tiebreak.

- [ ] **Step 7: Verify**

Run: `cd backend && uv run pytest tests/unit/domain/workspace_config/ -v && cd .. && make test && make lint`
Expected: new tests pass; `make test` clean including import-linter; lint at the known baseline.

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/domain/workspace_config/extension_fields \
        backend/src/protcellar/infrastructure/persistence/sqlalchemy/workspace_config \
        backend/alembic/versions/e3c9a1f7b508_extension_field_defs.py backend/tests
git commit -m "feat(extension-fields): the registry aggregate, table and repository

A workspace declares what extra fields a target-biology record kind carries.
name is immutable in the domain because the value is a key inside the
extensions JSONB bag — renaming it would orphan every stored value."
```

---

### Task 2: CRUD use cases and admin routes

**Files:**
- Create: `backend/src/protcellar/application/workspace_config/extension_fields/{__init__.py,list_field_defs.py,create_field_def.py,update_field_def.py,delete_field_def.py}`
- Create: `backend/src/protcellar/interface/routes/extension_fields.py`
- Modify: `backend/src/protcellar/infrastructure/di/_workspace_config.py`, `backend/src/protcellar/interface/dependencies/__init__.py`, `backend/src/protcellar/interface/app.py`
- Test: `backend/tests/api/test_extension_fields.py`

**Interfaces:**
- Consumes: everything Task 1 produced.
- Produces: `GET|POST /api/v1/extension-fields`, `PATCH|DELETE /api/v1/extension-fields/{id}`, and `ExtensionFieldDefResponse` carrying `id, kind, name, label, field_type, options, position, show_in_table, version`.

Follow `interface/routes/tags.py` for route shape and `application/workspace_config/tagging/` for the
one-use-case-per-file layout.

- [ ] **Step 1: Write the failing API test**

```python
async def test_admin_can_declare_a_field(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/extension-fields", json={
        "kind": "vulnerability", "name": "vi_lower_bound", "label": "VI lower bound",
        "field_type": "number", "options": None, "position": 0, "show_in_table": True,
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "vi_lower_bound"


async def test_duplicate_name_for_a_kind_conflicts(client: AsyncClient) -> None:
    body = {"kind": "hypomorph", "name": "phenotype", "label": "Phenotype",
            "field_type": "string", "options": None, "position": 0, "show_in_table": False}
    assert (await client.post("/api/v1/extension-fields", json=body)).status_code == 201
    assert (await client.post("/api/v1/extension-fields", json=body)).status_code == 409


async def test_same_name_on_a_different_kind_is_fine(client: AsyncClient) -> None:
    for kind in ("essentiality", "vulnerability"):
        r = await client.post("/api/v1/extension-fields", json={
            "kind": kind, "name": "note_code", "label": "Note code",
            "field_type": "string", "options": None, "position": 0, "show_in_table": False})
        assert r.status_code == 201, r.text


async def test_name_cannot_be_changed(client: AsyncClient) -> None:
    created = await client.post("/api/v1/extension-fields", json={
        "kind": "vulnerability", "name": "bin", "label": "Bin",
        "field_type": "string", "options": None, "position": 0, "show_in_table": False})
    fid = created.json()["id"]
    resp = await client.patch(f"/api/v1/extension-fields/{fid}", json={"name": "bin_v2"})
    assert resp.status_code == 422, resp.text


async def test_unknown_kind_is_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/extension-fields", json={
        "kind": "nonsense", "name": "x", "label": "X",
        "field_type": "string", "options": None, "position": 0, "show_in_table": False})
    assert resp.status_code == 422


async def test_a_second_workspace_sees_none_of_it(
    client: AsyncClient, other_workspace_client: AsyncClient
) -> None:
    await client.post("/api/v1/extension-fields", json={
        "kind": "vulnerability", "name": "isolation_probe", "label": "Probe",
        "field_type": "string", "options": None, "position": 0, "show_in_table": False})
    theirs = await other_workspace_client.get("/api/v1/extension-fields?kind=vulnerability")
    assert theirs.status_code == 200
    assert [f["name"] for f in theirs.json()] == []
```

`other_workspace_client` lives in `tests/api/conftest.py`.

- [ ] **Step 2: Run it to verify it fails** — 404, the routes do not exist.

- [ ] **Step 3: Write the four use cases**

One per file. `require_admin(auth)` in each mutation; `require_authenticated` for the list. Create
and update take `workspace_id` from `auth.workspace_id`. Create returns `ConflictError` when
`find_by_name` already returns a row — that maps to 409 via `interface/error_handlers.py`.

The update body **omits `name` entirely**, so sending it is a Pydantic `extra="forbid"` rejection
rather than a hand-rolled check. Give the body `model_config = {"extra": "forbid"}`, matching
`UpdateGeneBody`.

- [ ] **Step 4: Add the routes, wire DI, mount the router**

`kind` validates against `RecordKind` (`application/target_biology/crud.py`) — declare it as that
enum on the body so FastAPI rejects an unknown kind before any query, the same mechanism the bulk
target-biology route uses. Mount in `interface/app.py` beside the tags router.

- [ ] **Step 5: Verify and commit**

Run: `make test && make test-api && make lint && make generate-api`

```bash
git commit -m "feat(extension-fields): admin CRUD for field declarations

Per workspace, per record kind. name is rejected on update by omitting it
from the body entirely rather than by a hand-rolled guard."
```

---

### Task 3: Publish declarations through the descriptor

**Files:**
- Modify: `backend/src/protcellar/interface/target_biology_schema.py`
- Modify: `backend/src/protcellar/interface/routes/target_biology.py` — **concurrent history**
- Test: `backend/tests/unit/interface/test_target_biology_schema.py`, `backend/tests/api/test_target_biology.py`

**Interfaces:**
- Consumes: `ExtensionFieldDefRepository.list_all` from Task 1.
- Produces: `extension_fields` on every kind in the descriptor; `read_only` becomes empty.

- [ ] **Step 1: Write the failing tests**

```python
def test_every_kind_carries_an_extension_fields_array() -> None:
    schema = describe_write_surface({}, {})
    for kind in RecordKind:
        assert schema["kinds"][kind.value]["extension_fields"] == []


def test_extensions_is_no_longer_read_only() -> None:
    schema = describe_write_surface({}, {})
    assert schema["kinds"]["vulnerability"]["read_only"] == []


def test_declared_fields_appear_in_position_order() -> None:
    declared = {"vulnerability": [
        {"name": "rank", "label": "Rank", "type": "number",
         "options": None, "position": 1, "show_in_table": False},
        {"name": "bin", "label": "Bin", "type": "string",
         "options": None, "position": 0, "show_in_table": True},
    ]}
    fields = describe_write_surface({}, declared)["kinds"]["vulnerability"]["extension_fields"]
    assert [f["name"] for f in fields] == ["bin", "rank"]
    assert fields[0]["show_in_table"] is True


def test_declarations_never_leak_into_the_core_field_list() -> None:
    declared = {"vulnerability": [
        {"name": "bin", "label": "Bin", "type": "string",
         "options": None, "position": 0, "show_in_table": True}]}
    core = describe_write_surface({}, declared)["kinds"]["vulnerability"]["fields"]
    assert "bin" not in [f["name"] for f in core]
```

Plus an API test proving declarations are **not** served from the suggested-values cache:

```python
async def test_a_new_declaration_appears_in_the_descriptor_immediately(
    client: AsyncClient,
) -> None:
    """Field defs must not ride the suggested-values TTL cache — an admin who adds a
    field and cannot see it would reasonably read that as a bug."""
    before = await client.get("/api/v1/target-biology/schema")
    assert "cache_probe" not in [
        f["name"] for f in before.json()["kinds"]["hypomorph"]["extension_fields"]]

    await client.post("/api/v1/extension-fields", json={
        "kind": "hypomorph", "name": "cache_probe", "label": "Cache probe",
        "field_type": "string", "options": None, "position": 0, "show_in_table": False})

    after = await client.get("/api/v1/target-biology/schema")
    assert "cache_probe" in [
        f["name"] for f in after.json()["kinds"]["hypomorph"]["extension_fields"]]
```

- [ ] **Step 2: Run to verify they fail** — `describe_write_surface` takes one argument.

- [ ] **Step 3: Extend the descriptor**

`describe_write_surface(suggested, declared)` gains a second parameter: `dict[str, list[dict]]`
keyed by kind value. Each kind's entry becomes an `extension_fields` list of ordinary
`FieldDescriptor` dicts plus `show_in_table`. Set `_READ_ONLY = ()`.

Build each descriptor from the declaration rather than through `_describe_field`, which reflects
over Pydantic models and has nothing to reflect here:

```python
def _describe_declared(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": d["name"],
        "label": d["label"],
        "type": d["type"],
        "required": False,          # spec: `required` is deliberately out of scope
        "show_in_table": bool(d["show_in_table"]),
    }
    if d.get("options"):
        out["options"] = list(d["options"])
    return out
```

- [ ] **Step 4: Thread the repository into the route**

The schema route already resolves `auth.workspace_id` for suggested values. Add the field-def
repository, call `list_all(auth.workspace_id)`, group by kind, and pass it as `declared`.

**Do not put this behind the suggested-values cache.** That cache exists for a `SELECT DISTINCT`
sweep; this is one indexed lookup, and staleness here reads as a bug. Change **only** the schema
handler in this file.

- [ ] **Step 5: Verify and commit**

Run: `make test && make test-api && make generate-api`

```bash
git commit -m "feat(extension-fields): publish declarations in the write contract

extension_fields sits beside fields rather than merged into it: core fields
go at the top level of a write body, declared ones inside extensions, and a
client that predates this keeps working by ignoring an unknown key.

Not cached — the suggested-values TTL exists for a SELECT DISTINCT sweep,
and an admin who adds a field must see it at once."
```

---

### Task 4: Make `extensions` writable, validated

**Files:**
- Create: `backend/src/protcellar/application/target_biology/extension_validator.py`
- Modify: `backend/src/protcellar/application/target_biology/crud.py`
- Modify: `backend/src/protcellar/interface/routes/target_biology.py` — **concurrent history**
- Test: `backend/tests/unit/application/target_biology/test_extension_validator.py`, `backend/tests/api/test_target_biology.py`

**Interfaces:**
- Consumes: `ExtensionFieldDefRepository`, `RecordKind`.
- Produces: `ExtensionValidator.validate_and_merge(workspace_id, kind, submitted, existing) -> Result[dict, DomainError]`.

**The merge semantics are the subtle part.** The aggregates do
`self.extensions = dict(fields["extensions"] or {})` — a wholesale replace. If a PATCH submitting one
declared field reached that directly, it would delete every imported value the workspace has not
declared. So the use case merges before the aggregate sees anything.

- [ ] **Step 1: Write the failing validator tests**

```python
async def test_unknown_key_is_rejected() -> None:
    r = await _validator([_num("bin")]).validate_and_merge(WS, "vulnerability", {"nope": 1}, {})
    assert isinstance(r, Failure) and "nope" in str(r.failure().message)


async def test_wrong_type_is_rejected() -> None:
    r = await _validator([_num("bin")]).validate_and_merge(
        WS, "vulnerability", {"bin": "not a number"}, {})
    assert isinstance(r, Failure)


async def test_enum_value_outside_options_is_rejected() -> None:
    r = await _validator([_enum("call", ["yes", "no"])]).validate_and_merge(
        WS, "vulnerability", {"call": "maybe"}, {})
    assert isinstance(r, Failure)


async def test_undeclared_stored_values_survive_a_write() -> None:
    """Imported keys nobody declared must not be collateral damage of editing a declared one."""
    r = await _validator([_num("bin")]).validate_and_merge(
        WS, "vulnerability", {"bin": 5}, {"rank": "2398.0", "pct_of_max": "7%"})
    assert r.unwrap() == {"rank": "2398.0", "pct_of_max": "7%", "bin": 5}


async def test_explicit_null_removes_a_declared_key() -> None:
    r = await _validator([_num("bin")]).validate_and_merge(
        WS, "vulnerability", {"bin": None}, {"bin": 5, "rank": "2398.0"})
    assert r.unwrap() == {"rank": "2398.0"}
```

Clearing by explicit `null` matches the precedent `10735a1` set for `compound`, so the write surface
has one rule for "remove this" rather than two.

- [ ] **Step 2: Run to verify they fail** — module missing.

- [ ] **Step 3: Write the validator**

One class, one public method, no other responsibility. Loads `list_for_kind`, indexes by name, then
per submitted key: unknown → `ValidationError` naming it; `None` → drop from the merged result; else
coerce and type-check against `field_type` (`integer` rejects a float with a fractional part;
`number` accepts int or float; `date` parses ISO-8601; `enum` must be in `options`). Returns
`{**existing, **accepted}` minus the explicitly-nulled keys.

- [ ] **Step 4: Wire it into create and update**

Inject into `CreateTargetBiologyRecord` and `UpdateTargetBiologyRecord`. Create validates against
`{}`; update validates against `record.extensions`. On `Failure`, return it — `result_to_response`
maps `ValidationError` to 422.

- [ ] **Step 5: Add `extensions` to the write bodies**

Add `extensions: dict[str, Any] | None = None` to the eight `*WriteBody` and eight `*PatchBody`
classes. **Nothing else in that file changes** — `_patch_updates` needs no edit, because
`extensions` is a plain dict and passes through `model_dump(exclude_unset=True)` untouched; it is
not a value object and must **not** be added to `_VALUE_OBJECT_FIELDS`.

- [ ] **Step 6: Add API tests, verify, commit**

Cover: declared field round-trips; undeclared key 422s; a PATCH of a core field leaves `extensions`
untouched; a shared record rejects an extensions write with 404 (ownership, not validation).

Run: `make test && make test-api && make lint && make generate-api`

---

### Task 5: Admin UI — kind list and editor

**Files:**
- Create: `frontend/src/features/extension-fields/{api.ts,hooks.ts,types.ts,index.ts}`
- Create: `frontend/src/features/extension-fields/components/{extension-field-kinds.tsx,extension-field-editor.tsx,field-rows.tsx}`
- Create: `frontend/src/app/(dashboard)/admin/extension-fields/page.tsx` and `[kind]/page.tsx`
- Test: `frontend/src/features/extension-fields/components/field-rows.test.tsx`

Route pages stay thin — five lines, one component import — matching `admin/tags/page.tsx`.

**Two screens.** The kind list shows the eight kinds with a count each; kinds are a fixed set, so no
create or delete of kinds. The editor is an inline list of field rows.

**Per-row controls:** `name` (read-only once saved — §1), `label`, `field_type` select, `options`
(shown only for `enum`, comma-separated, trimmed, blanks dropped, order preserved),
`show_in_table` checkbox, move-up / move-down, delete.

**`position` is the row index on save.** No drag-and-drop — it needs a dependency and a keyboard
story for a screen holding single-digit row counts.

**Delete confirms with the surprising half stated plainly:** stored values are kept and will show as
unmapped. Use `ConfirmDialog`; the menu item ends in `…`.

Explicit Save and Cancel; Esc is an accelerator only.

Tests: a saved row renders `name` read-only and a new row does not; changing type to `enum` reveals
the options input and away from it hides it; move-up reorders; the delete confirm mentions that
values are kept.

Verify with `make test-fe`, `make lint-fe`, `pnpm exec tsc --noEmit`.

---

### Task 6: Show the values

**Files:**
- Modify: `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx`
- Modify: `gene-record-tables.tsx`, `protein-record-tables.tsx`
- Test: `editable-record-table.test.tsx`

**⚠️** `editable-record-table.tsx` was **not** touched by `10735a1` (that commit changed
`provenance-dialog.tsx` among the frontend files) — but Task 8 of the tenancy work added the
`is_shared` gating there. Read the file; add, don't rewrite.

Columns for declarations with `show_in_table`, in `position` order, after the core columns and
before the provenance ones. Undeclared stored keys render in a per-row detail popover, labelled as
unmapped, read-only.

Tests: a `show_in_table` declaration renders a column and one without it does not; an unmapped value
appears in the detail and not as a column; a shared row shows values with no edit affordance.

---

### Task 7: Edit the values

**Files:**
- Create: `frontend/src/features/protein-catalog/components/sections/extension-values-dialog.tsx`
- Modify: `editable-record-table.tsx`
- Test: `extension-values-dialog.test.tsx`

An "Extra fields…" row action opening a dialog built from that kind's `extension_fields`, mirroring
`provenance-dialog.tsx` — same structure, same explicit Save/Cancel, different field source. Map
each `type` to the control `field-input`-style logic already uses: `enum` → Select over `options`,
`boolean` → Checkbox, `date` → native `<input type="date">`, `text` → Textarea, numerics → numeric
Input, else Input.

Hidden for `is_shared` rows, like the other mutate affordances.

Submit only changed keys. Clearing a field sends explicit `null`, which the Task 4 validator treats
as removal.

Tests: renders one control per declared field with the right type; an untouched save is a no-op
(matching the provenance dialog's behaviour from `10735a1`); clearing a field sends `null`; the
action is absent on a shared row.

Verify with `make test-fe`, `make lint-fe`, `pnpm exec tsc --noEmit`, then live-QA the whole loop:
declare a field in admin, see the column, set a value, reload.

---

## Self-Review

**Spec coverage.** §1 registry → Task 1 (incl. both non-obvious rules). §2 field types → Task 1's
enum plus the Global Constraints note. §3 descriptor → Task 3, including the not-cached requirement
as its own test. §4 display → Tasks 6 and 7. §5 write validation and merge semantics → Task 4. §6
admin surface → Task 5, with order/options/delete resolved. §7 testing → distributed, with workspace
isolation in Task 2 and the cache check in Task 3. §8 build order → tasks 1-7 in the same sequence.

**Type consistency.** `ExtensionFieldType` is defined in Task 1 and used in Tasks 2-4.
`ExtensionFieldDefRepository.list_for_kind` / `list_all` are declared in Task 1 and consumed in Tasks
3 and 4. `describe_write_surface(suggested, declared)` gains its second parameter in Task 3 and is
called with two arguments in every Task 3 test. `validate_and_merge(workspace_id, kind, submitted,
existing)` is defined and used only within Task 4.

**Two places to check the code rather than trust this plan:** the current alembic head for Task 1's
`down_revision` (`d2b5f9c8e314` at time of writing), and the exact base class the tagging
repositories subclass, for Task 1 Step 6.

**Known style deviation.** Tasks 5-7 specify frontend behaviour and tests rather than complete
component code. The exact shadcn props are better read from the neighbouring components than guessed
here, and each task names the file it should mirror.
