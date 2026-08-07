# Target-Biology API Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the target-biology write surface from destroying provenance, make its updates partial and version-checked, and publish a self-describing write contract.

**Architecture:** All five tasks stay inside the existing layering — the aggregates already accept partial updates and already carry `version`, and `base_repository.save()` already does a compare-and-swap. Nothing new is invented; the interface layer is brought in line with what the domain and persistence layers already support, then the write surface is published as a descriptor derived from the Pydantic bodies that define it.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, SQLAlchemy async, `returns` Result, pytest (`asyncio_mode = "auto"`), Next.js 15 + orval-generated client, biome, vitest.

## Global Constraints

- Commands: `make test` (unit + import-linter) · `make test-api` (API tests) · `make lint` (ruff + mypy) · `make generate-api` (OpenAPI snapshot → orval client) · `make test-fe` · `make lint-fe`.
- mypy is strict. Every new function needs full annotations.
- Test fixtures already available: `client` (admin), `editor_client`, `viewer_client`, `database_url`, `admin_auth`.
- `tests/api/test_target_biology.py` already defines `_save(database_url, repo_cls, aggregate)` and `WS = GLOBAL_WORKSPACE_ID`. Reuse them; do not redefine.
- Domain errors map to HTTP in `interface/error_handlers.py`. `ConcurrencyConflictError` → **409** and adds `"retry": true` to the body. `ValidationError` → 422, `NotFoundError` → 404, `AuthorizationError` → 403. Never hand-roll a status code.
- `ConcurrencyConflictError(entity_type: str, entity_id: str, *, detail: str | None = None)` — positional entity type and id, keyword detail.
- **This service must remain unaware of any particular consumer.** No code, comment, doc or test may name a downstream application. The descriptor in Task 4 is a published contract for any client, and this service's own UI consumes it in Task 5.
- Record kinds are the eight members of `application/target_biology/crud.py:RecordKind`: `essentiality`, `vulnerability`, `hypomorph`, `crispri_strain`, `resistance_mutation`, `protein_production`, `protein_activity_assay`, `unpublished_structure`.
- `EssentialityClass` values use **underscores**: `essential`, `growth_defect`, `non_essential`, `growth_advantage`, `uncertain`.
- Commit after every task. Do not batch commits across tasks.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/src/protcellar/interface/routes/target_biology.py` | *Modify.* Patch bodies, the partial-update helper, `version` on responses and patch bodies, the three new reference fields, and the descriptor route. |
| `backend/src/protcellar/interface/target_biology_schema.py` | *Create.* Descriptor derivation from the write-body models plus the field annotation table. Kept out of `routes/` because it is a pure mapping with no HTTP concerns. |
| `backend/src/protcellar/application/target_biology/suggested_values.py` | *Create.* `SELECT DISTINCT` over each kind's vocabulary columns. |
| `backend/src/protcellar/application/target_biology/crud.py` | *Modify.* `UpdateTargetBiologyRecord` gains an optional expected-version check. |
| `backend/src/protcellar/interface/dependencies/__init__.py` | *Modify.* One new dependency for the suggested-values reader. |
| `backend/tests/api/test_target_biology.py` | *Modify.* Partial-update, version-conflict, reference round-trip and descriptor tests. |
| `backend/tests/unit/interface/test_target_biology_schema.py` | *Create.* Descriptor derivation unit tests (no DB). |
| `frontend/src/features/protein-catalog/components/sections/provenance-dialog.tsx` | *Create.* The full provenance editor, rendered from the descriptor. |
| `frontend/src/features/protein-catalog/hooks/use-target-biology-schema.ts` | *Create.* Descriptor query hook. |
| `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx` | *Modify.* Delete `ProvDraft`/`provToDraft`/`provToBody`; open the dialog from the row. |

---

### Task 1: Partial PATCH — stop clobbering provenance

**Files:**
- Modify: `backend/src/protcellar/interface/routes/target_biology.py`
- Test: `backend/tests/api/test_target_biology.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: eight patch-body classes named `<Kind>PatchBody` (`EssentialityPatchBody`, `VulnerabilityPatchBody`, `HypomorphPatchBody`, `CrispriStrainPatchBody`, `ResistanceMutationPatchBody`, `ProteinProductionPatchBody`, `ProteinActivityAssayPatchBody`, `UnpublishedStructurePatchBody`) and `_patch_updates(body: BaseModel) -> dict[str, Any]`. Tasks 2 and 3 add fields to these same classes.

**Context for the implementer:** the aggregates already do the right thing with a partial dict — `Essentiality.update(**fields)` guards every assignment with `if "condition" in fields`. The bug is that the route builds a dict containing *every* key unconditionally, so `provenance` is always present, and `ProvenanceBody.to_domain()` defaults `generation_method` to MANUAL. Fixing this is purely a route-layer change.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/api/test_target_biology.py`:

```python
async def test_patch_one_field_preserves_provenance_and_other_fields(
    client: AsyncClient, database_url: str
) -> None:
    """Editing `condition` must not touch provenance, generation_method, or siblings."""
    gene_id = uuid.uuid4()
    record = Essentiality(
        workspace_id=WS,
        gene_id=gene_id,
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(
            source_type=ProvenanceSourceType.PUBLISHED,
            generation_method=GenerationMethod.AI_EXTRACTED,
            citations=(Citation(pmid="28096490"), Citation(doi="10.1016/j.cell.2021.02.001")),
            contributor_researcher="A. Curator",
            observed_on=date(2021, 3, 1),
        ),
        condition="7H9",
        method="TnSeq",
        confidence=0.91,
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    resp = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"condition": "cholesterol"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["condition"] == "cholesterol"
    # Untouched scalars survive.
    assert body["classification"] == "essential"
    assert body["method"] == "TnSeq"
    assert body["confidence"] == 0.91
    # Provenance survives in full — this is the regression this task exists for.
    prov = body["provenance"]
    assert prov["generation_method"] == "ai_extracted"
    assert len(prov["citations"]) == 2
    assert prov["citations"][1]["doi"] == "10.1016/j.cell.2021.02.001"
    assert prov["contributor_researcher"] == "A. Curator"
    assert prov["observed_on"] == "2021-03-01"


async def test_patch_with_provenance_reattributes_to_manual(
    client: AsyncClient, database_url: str
) -> None:
    """Submitting provenance is what re-attributes a record — and only that."""
    gene_id = uuid.uuid4()
    record = Essentiality(
        workspace_id=WS,
        gene_id=gene_id,
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(
            source_type=ProvenanceSourceType.PUBLISHED,
            generation_method=GenerationMethod.AI_EXTRACTED,
        ),
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    resp = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"provenance": {"source_type": "internal", "citations": []}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["provenance"]["generation_method"] == "manual"
    assert resp.json()["provenance"]["source_type"] == "internal"


async def test_patch_rejects_unknown_field(client: AsyncClient, database_url: str) -> None:
    gene_id = uuid.uuid4()
    record = Essentiality(
        workspace_id=WS,
        gene_id=gene_id,
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    resp = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"nonsense": 1},
    )
    assert resp.status_code == 422
```

Add these imports to the test module's existing import block:

```python
from datetime import date

from protcellar.domain.shared.provenance import GenerationMethod
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_target_biology.py -k "patch" -v`

Expected: FAIL. The first test fails on `generation_method == "manual"` (clobbered) and on the citation count (untouched fields are fine today because the route resends them, but provenance is destroyed). The third fails because `EssentialityWriteBody` does not forbid extra keys and requires `classification`, so the request is a 422 for the wrong reason or a 200 — either way not the assertion.

- [ ] **Step 3: Add the shared partial-update helper**

In `backend/src/protcellar/interface/routes/target_biology.py`, after the write-body classes and before the endpoints:

```python
# Value-object fields whose patch bodies must be converted to domain objects.
# model_dump() would leave them as plain dicts, which the aggregates would store verbatim.
_VALUE_OBJECT_FIELDS = frozenset({"provenance", "compound", "ligands"})


def _patch_updates(body: BaseModel) -> dict[str, Any]:
    """Build the partial-update dict from only the fields the caller actually sent.

    The aggregates already guard every assignment with ``if "x" in fields``, so an
    absent key means "leave it alone". This is what keeps an edit to one field from
    re-stamping ``generation_method`` — provenance is only re-attributed when the
    caller submits it.
    """
    updates: dict[str, Any] = body.model_dump(exclude_unset=True)
    for name in _VALUE_OBJECT_FIELDS & set(updates):
        value = getattr(body, name)
        if value is None:
            updates.pop(name)
        elif isinstance(value, list):
            updates[name] = [item.to_domain() for item in value]
        else:
            updates[name] = value.to_domain()
    return updates
```

- [ ] **Step 4: Add the eight patch bodies**

Immediately after the corresponding `*WriteBody` class in the same file. Every field is optional; `extra="forbid"` matches `UpdateGeneBody` in `routes/genes.py`.

```python
class EssentialityPatchBody(BaseModel):
    classification: EssentialityClass | None = None
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceBody | None = None

    model_config = {"extra": "forbid"}


class VulnerabilityPatchBody(BaseModel):
    vulnerability_score: float | None = None
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceBody | None = None

    model_config = {"extra": "forbid"}


class HypomorphPatchBody(BaseModel):
    growth_defect: bool | None = None
    growth_defect_severity: str | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody | None = None

    model_config = {"extra": "forbid"}


class CrispriStrainPatchBody(BaseModel):
    name: str | None = None
    provenance: ProvenanceBody | None = None

    model_config = {"extra": "forbid"}


class ResistanceMutationPatchBody(BaseModel):
    mutation: str | None = None
    mic_shift: float | None = None
    parent_strain: str | None = None
    protein_coordinate: str | None = None
    method: str | None = None
    provenance: ProvenanceBody | None = None

    model_config = {"extra": "forbid"}


class ProteinProductionPatchBody(BaseModel):
    status: str | None = None
    expression_host: str | None = None
    purity: float | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody | None = None

    model_config = {"extra": "forbid"}


class ProteinActivityAssayPatchBody(BaseModel):
    activity_measured: str | None = None
    readout: str | None = None
    throughput: str | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody | None = None

    model_config = {"extra": "forbid"}


class UnpublishedStructurePatchBody(BaseModel):
    method: str | None = None
    resolution: float | None = None
    is_published: bool | None = None
    is_experimental: bool | None = None
    provenance: ProvenanceBody | None = None

    model_config = {"extra": "forbid"}
```

- [ ] **Step 5: Rewire the eight PATCH routes**

Each update route changes its body type to the patch twin and replaces the hand-built `updates` dict with the helper. Essentiality shown in full; apply the identical shape to the other seven, changing only the body class, the `RecordKind` member, and the response class.

```python
@router.patch("/target-biology/essentiality/{record_id}", response_model=EssentialityResponse)
async def update_essentiality(
    record_id: uuid.UUID,
    body: EssentialityPatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> EssentialityResponse:
    result = result_to_response(
        await use_case(RecordKind.ESSENTIALITY, record_id, _patch_updates(body), auth=auth)
    )
    return EssentialityResponse.from_domain(result)
```

The remaining seven, for reference — same body, same one-line `updates` replacement:

| Route | Body class | `RecordKind` | Response |
|---|---|---|---|
| `/target-biology/vulnerability/{record_id}` | `VulnerabilityPatchBody` | `VULNERABILITY` | `VulnerabilityResponse` |
| `/target-biology/hypomorph/{record_id}` | `HypomorphPatchBody` | `HYPOMORPH` | `HypomorphResponse` |
| `/target-biology/crispri_strain/{record_id}` | `CrispriStrainPatchBody` | `CRISPRI_STRAIN` | `CrispriStrainResponse` |
| `/target-biology/resistance_mutation/{record_id}` | `ResistanceMutationPatchBody` | `RESISTANCE_MUTATION` | `ResistanceMutationResponse` |
| `/target-biology/protein_production/{record_id}` | `ProteinProductionPatchBody` | `PROTEIN_PRODUCTION` | `ProteinProductionResponse` |
| `/target-biology/protein_activity_assay/{record_id}` | `ProteinActivityAssayPatchBody` | `PROTEIN_ACTIVITY_ASSAY` | `ProteinActivityAssayResponse` |
| `/target-biology/unpublished_structure/{record_id}` | `UnpublishedStructurePatchBody` | `UNPUBLISHED_STRUCTURE` | `UnpublishedStructureResponse` |

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/api/test_target_biology.py -v`
Expected: PASS, including the pre-existing bundle tests.

- [ ] **Step 7: Run lint and the full backend suite**

Run: `make lint && make test && make test-api`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/interface/routes/target_biology.py backend/tests/api/test_target_biology.py
git commit -m "fix(target-biology): make PATCH partial so an edit stops clobbering provenance

The aggregates already accept a partial dict — every update() guards its
assignments with `if \"x\" in fields`. The route was building a dict with
every key present, so provenance was resubmitted on every edit and
ProvenanceBody.to_domain() re-stamped generation_method to MANUAL.

Correcting a typo in `condition` no longer re-attributes an AI-extracted
record to a human. Follows the separate Create/Update body pattern the
gene, protein, target, strain, organism and organization routers use."
```

---

### Task 2: Optimistic locking reaches the wire

**Files:**
- Modify: `backend/src/protcellar/application/target_biology/crud.py`
- Modify: `backend/src/protcellar/interface/routes/target_biology.py`
- Test: `backend/tests/api/test_target_biology.py`

**Interfaces:**
- Consumes: the eight `*PatchBody` classes from Task 1.
- Produces: `UpdateTargetBiologyRecord.__call__(kind, record_id, updates, auth=None, expected_version=None)`; `version: int` on all eight `*Response` classes; `version: int | None` on all eight `*PatchBody` classes.

**Context:** `base_repository.save()` already does `UPDATE … WHERE version = loaded_version` and bumps. It never fires because the use case re-reads the record immediately before saving, so the loaded version is always current. The client's expectation has to travel to the server for the check to mean anything. Keep it **optional** — the CSV importers and any script must keep working unchanged.

- [ ] **Step 1: Write the failing test**

```python
async def test_patch_with_stale_version_conflicts(
    client: AsyncClient, database_url: str
) -> None:
    record = Essentiality(
        workspace_id=WS,
        gene_id=uuid.uuid4(),
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
        condition="7H9",
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    first = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"condition": "cholesterol", "version": 1},
    )
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 2

    # Someone else's browser still holds version 1.
    stale = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"condition": "glycerol", "version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["retry"] is True
    # The losing write must not have landed.
    assert first.json()["condition"] == "cholesterol"


async def test_patch_without_version_still_succeeds(
    client: AsyncClient, database_url: str
) -> None:
    """Version is opt-in — importers and scripts keep working."""
    record = Essentiality(
        workspace_id=WS,
        gene_id=uuid.uuid4(),
        classification=EssentialityClass.ESSENTIAL,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
    )
    await _save(database_url, SQLAlchemyEssentialityRepository, record)

    resp = await client.patch(
        f"/api/v1/target-biology/essentiality/{record.id}",
        json={"condition": "7H9"},
    )
    assert resp.status_code == 200, resp.text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_target_biology.py -k version -v`
Expected: FAIL — `version` is rejected by `extra="forbid"` (422), and `*Response` has no `version` key.

- [ ] **Step 3: Add the version check to the use case**

In `backend/src/protcellar/application/target_biology/crud.py`, add `ConcurrencyConflictError` to the existing `domain.shared.errors` import, then:

```python
class UpdateTargetBiologyRecord:
    def __init__(
        self, uow: UnitOfWork, repos: Repos, dispatcher: EventDispatcherProtocol
    ) -> None:
        self._uow, self._repos, self._dispatcher = uow, repos, dispatcher

    async def __call__(
        self,
        kind: RecordKind,
        record_id: uuid.UUID,
        updates: dict[str, Any],
        auth: AuthContext | None = None,
        expected_version: int | None = None,
    ) -> Result[AggregateRoot, DomainError]:
        require_admin(auth)
        async with self._uow:
            record = await self._repos[kind].find_by_id_in_workspace(
                GLOBAL_WORKSPACE_ID, record_id
            )
            if record is None:
                return Failure(NotFoundError(kind.value, str(record_id)))
            # Opt-in: a caller that supplies no version keeps last-write-wins, so
            # importers and scripts are unaffected. The repository CAS stays as the
            # backstop for the race between this read and the save below.
            if expected_version is not None and record.version != expected_version:
                return Failure(
                    ConcurrencyConflictError(
                        kind.value,
                        str(record_id),
                        detail=(
                            f"Expected version {expected_version}, "
                            f"found {record.version}"
                        ),
                    )
                )
            record.update(**updates)
            await self._repos[kind].save(record)
            events = await self._uow.commit()
        await self._dispatcher.dispatch_all(events)
        return Success(record)
```

- [ ] **Step 4: Add `version` to the eight responses**

Add the field and the mapping to each `*Response`. Essentiality shown; repeat for the other seven — the field name is `version` on every aggregate.

```python
class EssentialityResponse(BaseModel):
    id: uuid.UUID
    gene_id: uuid.UUID
    classification: str
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int

    @classmethod
    def from_domain(cls, e: Essentiality) -> EssentialityResponse:
        return cls(
            id=e.id,
            gene_id=e.gene_id,
            classification=e.classification.value,
            condition=e.condition,
            method=e.method,
            confidence=e.confidence,
            provenance=ProvenanceResponse.from_domain(e.provenance),
            extensions=e.extensions,
            version=e.version,
        )
```

- [ ] **Step 5: Add `version` to the eight patch bodies and pass it through**

Add to each `*PatchBody`:

```python
    version: int | None = None
```

`version` is a concurrency token, not a record field, so it must never reach `record.update()`. Pop it in the helper — update `_patch_updates` from Task 1:

```python
def _patch_updates(body: BaseModel) -> dict[str, Any]:
    """Build the partial-update dict from only the fields the caller actually sent.

    The aggregates already guard every assignment with ``if "x" in fields``, so an
    absent key means "leave it alone". This is what keeps an edit to one field from
    re-stamping ``generation_method`` — provenance is only re-attributed when the
    caller submits it.

    ``version`` is stripped: it is the caller's concurrency expectation, not a field.
    """
    updates: dict[str, Any] = body.model_dump(exclude_unset=True)
    updates.pop("version", None)
    for name in _VALUE_OBJECT_FIELDS & set(updates):
        value = getattr(body, name)
        if value is None:
            updates.pop(name)
        elif isinstance(value, list):
            updates[name] = [item.to_domain() for item in value]
        else:
            updates[name] = value.to_domain()
    return updates
```

Then each PATCH route forwards it:

```python
    result = result_to_response(
        await use_case(
            RecordKind.ESSENTIALITY,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/api/test_target_biology.py -v`
Expected: PASS.

- [ ] **Step 7: Run lint and the full backend suite**

Run: `make lint && make test && make test-api`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/application/target_biology/crud.py backend/src/protcellar/interface/routes/target_biology.py backend/tests/api/test_target_biology.py
git commit -m "feat(target-biology): let optimistic locking reach the wire

base_repository.save() already did a CAS on version and bumped it, but the
check could never fail: the use case re-read the record immediately before
saving, so the loaded version was always current. Responses now carry
version and PATCH accepts it, so a caller's expectation is what gets
compared. Concurrent edits return 409 instead of silently losing one.

Opt-in by design — omitting version keeps last-write-wins, so the CSV
importers and any scripts are unaffected."
```

---

### Task 3: Make `compound`, `ligands` and `knockdown_strain_id` writable

**Files:**
- Modify: `backend/src/protcellar/interface/routes/target_biology.py`
- Test: `backend/tests/api/test_target_biology.py`

**Interfaces:**
- Consumes: the patch bodies from Tasks 1–2 and `_patch_updates`'s `_VALUE_OBJECT_FIELDS` handling.
- Produces: `CompoundRefBody` with `to_domain() -> CompoundRef`.

**Context:** all three fields are already stored on the aggregates, already returned in responses, and every aggregate's `update()` already handles them (`ResistanceMutation.update` has `if "compound" in fields`, `UnpublishedStructure.update` has `if "ligands" in fields`, `Hypomorph.update` has `if "knockdown_strain_id" in fields`). Only the write bodies and the create-route constructors are missing them, so an importer is the sole way to set them. `_patch_updates` already converts `compound` and `ligands` — this task supplies the bodies it converts from.

- [ ] **Step 1: Write the failing test**

```python
async def test_resistance_mutation_compound_round_trips(
    client: AsyncClient, database_url: str
) -> None:
    gene_id = uuid.uuid4()
    compound_id = uuid.uuid4()

    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/resistance_mutation",
        json={
            "mutation": "S315T",
            "compound": {"compound_id": str(compound_id), "name": "isoniazid"},
            "mic_shift": 200,
            "provenance": {"source_type": "published", "citations": []},
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["compound"]["name"] == "isoniazid"
    assert created.json()["compound"]["compound_id"] == str(compound_id)

    record_id = created.json()["id"]
    other = uuid.uuid4()
    patched = await client.patch(
        f"/api/v1/target-biology/resistance_mutation/{record_id}",
        json={"compound": {"compound_id": str(other), "name": "rifampicin"}},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["compound"]["name"] == "rifampicin"
    # An untouched compound survives a patch of something else.
    again = await client.patch(
        f"/api/v1/target-biology/resistance_mutation/{record_id}",
        json={"mic_shift": 64},
    )
    assert again.status_code == 200, again.text
    assert again.json()["compound"]["name"] == "rifampicin"


async def test_unpublished_structure_ligands_round_trip(
    client: AsyncClient, database_url: str
) -> None:
    protein_id = uuid.uuid4()
    created = await client.post(
        f"/api/v1/proteins/{protein_id}/target-biology/unpublished_structure",
        json={
            "method": "X-ray",
            "resolution": 1.9,
            "ligands": [{"compound_id": str(uuid.uuid4()), "name": "ATP"}],
            "provenance": {"source_type": "internal", "citations": []},
        },
    )
    assert created.status_code == 201, created.text
    assert [lig["name"] for lig in created.json()["ligands"]] == ["ATP"]


async def test_hypomorph_knockdown_strain_round_trips(
    client: AsyncClient, database_url: str
) -> None:
    gene_id = uuid.uuid4()
    strain_id = uuid.uuid4()
    created = await client.post(
        f"/api/v1/genes/{gene_id}/target-biology/hypomorph",
        json={
            "growth_defect": True,
            "growth_defect_severity": "severe",
            "knockdown_strain_id": str(strain_id),
            "provenance": {"source_type": "internal", "citations": []},
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["knockdown_strain_id"] == str(strain_id)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_target_biology.py -k "compound or ligand or knockdown" -v`
Expected: FAIL — the create bodies ignore the extra keys, so `compound` / `ligands` / `knockdown_strain_id` come back null or empty.

- [ ] **Step 3: Add the inbound compound-reference body**

In `target_biology.py`, next to `ProvenanceBody`:

```python
class CompoundRefBody(BaseModel):
    """Inbound reference to a compound held in a chemistry catalog.

    This service does not resolve the id — it stores the caller's pair verbatim, the
    same self-contained reference `CompoundRef` already models. `name` is a
    denormalized label for display; `compound_id` is the identity.
    """

    compound_id: uuid.UUID
    name: str | None = None

    def to_domain(self) -> CompoundRef:
        return CompoundRef(compound_id=self.compound_id, name=self.name or None)
```

- [ ] **Step 4: Add the fields to the three create bodies and the three patch bodies**

```python
class ResistanceMutationWriteBody(BaseModel):
    mutation: str
    compound: CompoundRefBody | None = None
    mic_shift: float | None = None
    parent_strain: str | None = None
    protein_coordinate: str | None = None
    method: str | None = None
    provenance: ProvenanceBody


class UnpublishedStructureWriteBody(BaseModel):
    method: str | None = None
    resolution: float | None = None
    ligands: list[CompoundRefBody] = []
    is_published: bool = False
    is_experimental: bool = True
    provenance: ProvenanceBody


class HypomorphWriteBody(BaseModel):
    growth_defect: bool
    growth_defect_severity: str | None = None
    knockdown_strain_id: uuid.UUID | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody
```

And on the patch twins:

```python
# HypomorphPatchBody
    knockdown_strain_id: uuid.UUID | None = None

# ResistanceMutationPatchBody
    compound: CompoundRefBody | None = None

# UnpublishedStructurePatchBody
    ligands: list[CompoundRefBody] | None = None
```

- [ ] **Step 5: Pass them through the three create routes**

```python
    record = ResistanceMutation.create(
        workspace_id=GLOBAL_WORKSPACE_ID,
        gene_id=gene_id,
        mutation=body.mutation,
        provenance=body.provenance.to_domain(),
        compound=body.compound.to_domain() if body.compound else None,
        mic_shift=body.mic_shift,
        parent_strain=body.parent_strain,
        protein_coordinate=body.protein_coordinate,
        method=body.method,
    )
```

```python
    record = UnpublishedStructure.create(
        workspace_id=GLOBAL_WORKSPACE_ID,
        protein_id=protein_id,
        provenance=body.provenance.to_domain(),
        method=body.method,
        resolution=body.resolution,
        ligands=tuple(lig.to_domain() for lig in body.ligands),
        is_published=body.is_published,
        is_experimental=body.is_experimental,
    )
```

```python
    record = Hypomorph.create(
        workspace_id=GLOBAL_WORKSPACE_ID,
        gene_id=gene_id,
        growth_defect=body.growth_defect,
        provenance=body.provenance.to_domain(),
        growth_defect_severity=body.growth_defect_severity,
        knockdown_strain_id=body.knockdown_strain_id,
        condition=body.condition,
        method=body.method,
    )
```

Before writing these, open each aggregate's `create()` classmethod and confirm the keyword names match — `ResistanceMutation.create`, `UnpublishedStructure.create`, `Hypomorph.create`. If a keyword differs, follow the aggregate, not this plan.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/api/test_target_biology.py -v`
Expected: PASS.

- [ ] **Step 7: Run lint and the full backend suite**

Run: `make lint && make test && make test-api`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add backend/src/protcellar/interface/routes/target_biology.py backend/tests/api/test_target_biology.py
git commit -m "feat(target-biology): allow compound, ligands and knockdown strain to be written

All three were already stored on the aggregates, already returned in
responses, and already handled by every update() — but absent from every
write body, so an importer was the only way to set them. A resistance
mutation whose compound cannot be named through the API is missing the
fact that makes it a resistance mutation."
```

---

### Task 4: Publish the write contract — `GET /api/v1/target-biology/schema`

**Files:**
- Create: `backend/src/protcellar/interface/target_biology_schema.py`
- Create: `backend/src/protcellar/application/target_biology/suggested_values.py`
- Modify: `backend/src/protcellar/interface/routes/target_biology.py`
- Modify: `backend/src/protcellar/interface/dependencies/__init__.py`
- Test: `backend/tests/unit/interface/test_target_biology_schema.py`
- Test: `backend/tests/api/test_target_biology.py`

**Interfaces:**
- Consumes: the eight `*WriteBody` classes as they stand after Task 3.
- Produces: `GET /api/v1/target-biology/schema` returning `TargetBiologySchemaResponse`; `describe_write_surface(suggested: dict[tuple[str, str], list[str]]) -> dict[str, Any]`; `SuggestedValuesReader.for_all_kinds() -> dict[tuple[str, str], list[str]]`.

**Context:** the descriptor is *derived*, never hand-written — that is the whole point. `EssentialityWriteBody.model_fields` already carries the name, annotation, required-ness and enum type of every writable field. A small annotation table supplies only what the models cannot know: the human label, numeric bounds, and which fields have a vocabulary worth suggesting.

- [ ] **Step 1: Write the failing unit test**

Create `backend/tests/unit/interface/test_target_biology_schema.py`:

```python
"""The published write contract is derived from the write-body models, never restated."""

from __future__ import annotations

from protcellar.application.target_biology.crud import RecordKind
from protcellar.interface.target_biology_schema import describe_write_surface


def test_describes_every_record_kind() -> None:
    schema = describe_write_surface({})
    assert set(schema["kinds"]) == {k.value for k in RecordKind}


def test_essentiality_classification_is_an_enum_with_domain_values() -> None:
    field = _field(describe_write_surface({}), "essentiality", "classification")
    assert field["type"] == "enum"
    assert field["required"] is True
    assert set(field["options"]) == {
        "essential",
        "growth_defect",
        "non_essential",
        "growth_advantage",
        "uncertain",
    }


def test_optional_fields_are_not_required() -> None:
    field = _field(describe_write_surface({}), "essentiality", "condition")
    assert field["type"] == "string"
    assert field["required"] is False


def test_confidence_carries_its_domain_bounds() -> None:
    field = _field(describe_write_surface({}), "essentiality", "confidence")
    assert field["type"] == "number"
    assert field["min"] == 0.0
    assert field["max"] == 1.0


def test_kinds_declare_which_parent_they_attach_to() -> None:
    schema = describe_write_surface({})
    assert schema["kinds"]["essentiality"]["attaches_to"] == "gene"
    assert schema["kinds"]["protein_production"]["attaches_to"] == "protein"


def test_reference_fields_name_their_target() -> None:
    compound = _field(describe_write_surface({}), "resistance_mutation", "compound")
    assert compound["type"] == "reference"
    assert compound["target"] == "compound"

    ligands = _field(describe_write_surface({}), "unpublished_structure", "ligands")
    assert ligands["type"] == "list"
    assert ligands["item_type"] == "reference"
    assert ligands["target"] == "compound"

    strain = _field(describe_write_surface({}), "hypomorph", "knockdown_strain_id")
    assert strain["type"] == "reference"
    assert strain["target"] == "strain"


def test_provenance_exposes_every_field_including_repeatable_citations() -> None:
    prov = describe_write_surface({})["provenance"]
    names = [f["name"] for f in prov["fields"]]
    assert names == [
        "source_type",
        "citations",
        "contributor_researcher",
        "observed_on",
        "note",
    ]
    citations = next(f for f in prov["fields"] if f["name"] == "citations")
    assert citations["type"] == "list"
    assert [f["name"] for f in citations["item_fields"]] == ["pmid", "doi", "url", "label"]
    # generation_method is deliberately absent: an edit re-attributes to a human.
    assert "generation_method" not in names


def test_suggested_values_are_attached_to_their_field() -> None:
    schema = describe_write_surface({("essentiality", "condition"): ["7H9", "cholesterol"]})
    field = _field(schema, "essentiality", "condition")
    assert field["suggested_values"] == ["7H9", "cholesterol"]


def test_extensions_is_reported_read_only_on_every_kind() -> None:
    schema = describe_write_surface({})
    for kind in RecordKind:
        assert "extensions" in schema["kinds"][kind.value]["read_only"]


def _field(schema: dict, kind: str, name: str) -> dict:
    return next(f for f in schema["kinds"][kind]["fields"] if f["name"] == name)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/unit/interface/test_target_biology_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: protcellar.interface.target_biology_schema`.

- [ ] **Step 3: Write the descriptor derivation**

Create `backend/src/protcellar/interface/target_biology_schema.py`:

```python
"""The published, self-describing write contract for target-biology records.

Derived from the ``*WriteBody`` models that the routes already validate against, so
the contract cannot drift from what the API accepts. The annotation table below
supplies only what a Pydantic model cannot know on its own: a human label, numeric
bounds, and which free-text fields carry a vocabulary worth suggesting.

Any client can build a correct form from this. Restating a field list anywhere else —
in this service or in a client — is what this endpoint exists to prevent.
"""

from __future__ import annotations

import datetime
import enum
import types
import typing
import uuid
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from protcellar.application.target_biology.crud import RecordKind
from protcellar.interface.routes.target_biology import (
    CrispriStrainWriteBody,
    EssentialityWriteBody,
    HypomorphWriteBody,
    ProteinActivityAssayWriteBody,
    ProteinProductionWriteBody,
    ProvenanceBody,
    ProvenanceCitationBody,
    ResistanceMutationWriteBody,
    UnpublishedStructureWriteBody,
    VulnerabilityWriteBody,
)

# The write body and parent resource for each kind. `attaches_to` tells a client which
# path a record is created under, so it does not have to hard-code the split.
_KINDS: dict[RecordKind, tuple[type[BaseModel], str, str]] = {
    RecordKind.ESSENTIALITY: (EssentialityWriteBody, "gene", "Essentiality"),
    RecordKind.VULNERABILITY: (VulnerabilityWriteBody, "gene", "Vulnerability"),
    RecordKind.HYPOMORPH: (HypomorphWriteBody, "gene", "Hypomorph"),
    RecordKind.CRISPRI_STRAIN: (CrispriStrainWriteBody, "gene", "CRISPRi strain"),
    RecordKind.RESISTANCE_MUTATION: (
        ResistanceMutationWriteBody,
        "gene",
        "Resistance mutation",
    ),
    RecordKind.PROTEIN_PRODUCTION: (ProteinProductionWriteBody, "protein", "Protein production"),
    RecordKind.PROTEIN_ACTIVITY_ASSAY: (
        ProteinActivityAssayWriteBody,
        "protein",
        "Protein activity assay",
    ),
    RecordKind.UNPUBLISHED_STRUCTURE: (
        UnpublishedStructureWriteBody,
        "protein",
        "Unpublished structure",
    ),
}

# Stored on the records but writable only through ingestion.
_READ_ONLY: tuple[str, ...] = ("extensions",)

# What the models cannot express. Keys are field names; values merge into the descriptor.
# `suggested_values` is filled in at request time from the stored data.
_ANNOTATIONS: dict[str, dict[str, Any]] = {
    "classification": {"label": "Classification"},
    "condition": {"label": "Condition", "vocabulary": True},
    "method": {"label": "Method", "vocabulary": True},
    "confidence": {"label": "Confidence", "min": 0.0, "max": 1.0},
    "vulnerability_score": {"label": "Vulnerability score"},
    "growth_defect": {"label": "Growth defect"},
    "growth_defect_severity": {"label": "Growth-defect severity", "vocabulary": True},
    "knockdown_strain_id": {"label": "Knockdown strain", "target": "strain"},
    "name": {"label": "Name"},
    "mutation": {"label": "Mutation"},
    "compound": {"label": "Compound", "target": "compound"},
    "mic_shift": {"label": "MIC fold-shift"},
    "parent_strain": {"label": "Parent strain"},
    "protein_coordinate": {"label": "Protein coordinate"},
    "status": {"label": "Status", "vocabulary": True},
    "expression_host": {"label": "Expression host", "vocabulary": True},
    "purity": {"label": "Purity"},
    "activity_measured": {"label": "Activity measured", "vocabulary": True},
    "readout": {"label": "Readout", "vocabulary": True},
    "throughput": {"label": "Throughput", "vocabulary": True},
    "resolution": {"label": "Resolution (Å)"},
    "is_published": {"label": "Published"},
    "is_experimental": {"label": "Experimental"},
    "ligands": {"label": "Ligands", "target": "compound"},
    "source_type": {"label": "Source type"},
    "citations": {"label": "Citations"},
    "contributor_researcher": {"label": "Contributor"},
    "observed_on": {"label": "Observed on"},
    "note": {"label": "Note"},
    "pmid": {"label": "PMID"},
    "doi": {"label": "DOI"},
    "url": {"label": "URL"},
    "label": {"label": "Label"},
}

# Field names whose value is a reference to something this service does not resolve.
_REFERENCE_FIELDS = frozenset({"compound", "ligands", "knockdown_strain_id"})


def describe_write_surface(
    suggested: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    """Build the descriptor. ``suggested`` is keyed by ``(kind, field)``."""
    return {
        "provenance": {"fields": _describe_model(ProvenanceBody, kind=None, suggested={})},
        "kinds": {
            kind.value: {
                "label": label,
                "attaches_to": parent,
                "fields": _describe_model(body, kind=kind.value, suggested=suggested),
                "read_only": list(_READ_ONLY),
            }
            for kind, (body, parent, label) in _KINDS.items()
        },
    }


def _describe_model(
    model: type[BaseModel],
    *,
    kind: str | None,
    suggested: dict[tuple[str, str], list[str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, field in model.model_fields.items():
        # Provenance is described once at the top level, not repeated inside every kind.
        if name == "provenance":
            continue
        out.append(_describe_field(name, field, kind=kind, suggested=suggested))
    return out


def _describe_field(
    name: str,
    field: FieldInfo,
    *,
    kind: str | None,
    suggested: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    annotation = _ANNOTATIONS.get(name, {})
    inner, is_list = _unwrap(field.annotation)
    descriptor: dict[str, Any] = {
        "name": name,
        "label": annotation.get("label", name.replace("_", " ").capitalize()),
        "type": "list" if is_list else _scalar_type(name, inner),
        "required": field.is_required(),
    }
    if is_list:
        if name in _REFERENCE_FIELDS:
            descriptor["item_type"] = "reference"
        elif isinstance(inner, type) and issubclass(inner, BaseModel):
            descriptor["item_type"] = "object"
            descriptor["item_fields"] = _describe_model(inner, kind=kind, suggested={})
        else:
            descriptor["item_type"] = _scalar_type(name, inner)
    if isinstance(inner, type) and issubclass(inner, enum.Enum):
        descriptor["options"] = [member.value for member in inner]
    if "target" in annotation:
        descriptor["target"] = annotation["target"]
    for bound in ("min", "max"):
        if bound in annotation:
            descriptor[bound] = annotation[bound]
    if annotation.get("vocabulary") and kind is not None:
        descriptor["suggested_values"] = suggested.get((kind, name), [])
    return descriptor


def _unwrap(annotation: Any) -> tuple[Any, bool]:
    """Strip Optional and detect a list, returning (inner type, is_list)."""
    args = [a for a in typing.get_args(annotation) if a is not type(None)]
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType) and args:
        annotation = args[0]
        origin = typing.get_origin(annotation)
        args = list(typing.get_args(annotation))
    if origin is list:
        return (args[0] if args else str), True
    return annotation, False


def _scalar_type(name: str, annotation: Any) -> str:
    if name in _REFERENCE_FIELDS:
        return "reference"
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            return "enum"
        if issubclass(annotation, bool):
            return "boolean"
        if issubclass(annotation, int):
            return "integer"
        if issubclass(annotation, float):
            return "number"
        if issubclass(annotation, datetime.date):
            return "date"
        if issubclass(annotation, uuid.UUID):
            return "string"
        if issubclass(annotation, BaseModel):
            return "object"
    if name == "note":
        return "text"
    return "string"
```

Note the ordering trap: `bool` is a subclass of `int`, so the `bool` check must come first. `ProvenanceCitationBody` is imported for the citations `item_fields` walk — if ruff flags it as unused, the walk is going through `field.annotation` instead and the import should be dropped.

- [ ] **Step 4: Run the unit test to verify it passes**

Run: `cd backend && uv run pytest tests/unit/interface/test_target_biology_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Write the suggested-values reader**

Create `backend/src/protcellar/application/target_biology/suggested_values.py`:

```python
"""Distinct stored values for the free-text vocabulary fields.

ponytail: distinct-over-stored-values, so a typo becomes a suggestion. It is still
strictly better than an empty combobox — it is what stops a second spelling of an
existing condition being invented. Swap for a curated vocabulary registry when
someone owns curation; the descriptor shape does not change.
"""

from __future__ import annotations

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from protcellar.application.target_biology.crud import RecordKind

_LIMIT = 200

# (kind, field) -> the ORM column holding it. Populated from the mapped models.
_VOCABULARY_COLUMNS: dict[RecordKind, tuple[str, ...]] = {
    RecordKind.ESSENTIALITY: ("condition", "method"),
    RecordKind.VULNERABILITY: ("condition", "method"),
    RecordKind.HYPOMORPH: ("condition", "method", "growth_defect_severity"),
    RecordKind.CRISPRI_STRAIN: (),
    RecordKind.RESISTANCE_MUTATION: ("method",),
    RecordKind.PROTEIN_PRODUCTION: ("condition", "method", "status", "expression_host"),
    RecordKind.PROTEIN_ACTIVITY_ASSAY: (
        "condition",
        "method",
        "activity_measured",
        "readout",
        "throughput",
    ),
    RecordKind.UNPUBLISHED_STRUCTURE: ("method",),
}


class SuggestedValuesReader:
    """Reads the distinct values already stored for each vocabulary field."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        models: dict[RecordKind, type],
    ) -> None:
        self._session_factory = session_factory
        self._models = models

    async def for_all_kinds(self) -> dict[tuple[str, str], list[str]]:
        out: dict[tuple[str, str], list[str]] = {}
        async with self._session_factory() as session:
            for kind, fields in _VOCABULARY_COLUMNS.items():
                model = self._models.get(kind)
                if model is None:
                    continue
                for field in fields:
                    column = getattr(model, field, None)
                    if column is None:
                        continue
                    rows = await session.execute(
                        select(distinct(column))
                        .where(column.is_not(None))
                        .order_by(column)
                        .limit(_LIMIT)
                    )
                    out[(kind.value, field)] = [v for (v,) in rows if v]
        return out
```

Wire it in `interface/dependencies/`. Follow the existing pattern in that package for how a use case reaches a session factory and the ORM model registry — the target-biology repositories already resolve their model classes, so reuse that mapping rather than building a second one. Name the dependency `SuggestedValuesReaderDep`.

- [ ] **Step 6: Add the route and its API test**

In `routes/target_biology.py`, register this **before** any parameterized `/target-biology/{kind}/...` route so the literal path is not shadowed:

```python
@router.get("/target-biology/schema")
async def get_target_biology_schema(
    auth: AuthDep,
    reader: SuggestedValuesReaderDep,
) -> dict[str, Any]:
    """The published write contract: what each record kind accepts, and the values
    already in use for its vocabulary fields. Requires a caller, so the write surface
    is not enumerable anonymously."""
    return describe_write_surface(await reader.for_all_kinds())
```

Add to `backend/tests/api/test_target_biology.py`:

```python
async def test_schema_lists_every_kind_and_seeds_vocabulary(
    client: AsyncClient, database_url: str
) -> None:
    await _save(
        database_url,
        SQLAlchemyEssentialityRepository,
        Essentiality(
            workspace_id=WS,
            gene_id=uuid.uuid4(),
            classification=EssentialityClass.ESSENTIAL,
            provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED),
            condition="cholesterol",
        ),
    )

    resp = await client.get("/api/v1/target-biology/schema")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert len(body["kinds"]) == 8
    condition = next(
        f for f in body["kinds"]["essentiality"]["fields"] if f["name"] == "condition"
    )
    assert "cholesterol" in condition["suggested_values"]
    assert [f["name"] for f in body["provenance"]["fields"]][0] == "source_type"
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/unit/interface/test_target_biology_schema.py tests/api/test_target_biology.py -v`
Expected: PASS.

- [ ] **Step 8: Run lint and the full backend suite**

Run: `make lint && make test && make test-api`
Expected: clean. `make test` also runs import-linter — if it objects to `interface/target_biology_schema.py` importing from `interface/routes/`, move the write bodies into the schema module's own import list per whatever the contract allows, and re-run.

- [ ] **Step 9: Regenerate the API client and commit**

```bash
make generate-api
git add backend/src/protcellar/interface/target_biology_schema.py \
        backend/src/protcellar/application/target_biology/suggested_values.py \
        backend/src/protcellar/interface/routes/target_biology.py \
        backend/src/protcellar/interface/dependencies/ \
        backend/tests/unit/interface/test_target_biology_schema.py \
        backend/tests/api/test_target_biology.py \
        frontend/openapi.json frontend/src/shared/lib/api/
git commit -m "feat(target-biology): publish a self-describing write contract

GET /api/v1/target-biology/schema derives the writable fields, types,
enum options, bounds and parent resource of all eight record kinds from
the write-body models the routes already validate against — so the
contract cannot drift from what the API accepts.

Free-text vocabulary fields carry the values already stored, which is what
stops a second spelling of an existing condition being invented. The field
list was previously stated twice, in the routes and again as frontend
column definitions; a client can now build a correct form without
restating it at all."
```

---

### Task 5: Render provenance from the descriptor, and stop dropping it

**Files:**
- Create: `frontend/src/features/protein-catalog/hooks/use-target-biology-schema.ts`
- Create: `frontend/src/features/protein-catalog/components/sections/provenance-dialog.tsx`
- Modify: `frontend/src/features/protein-catalog/components/sections/editable-record-table.tsx`
- Modify: `frontend/src/features/protein-catalog/components/sections/gene-record-tables.tsx`
- Modify: `frontend/src/features/protein-catalog/components/sections/protein-record-tables.tsx`
- Test: `frontend/src/features/protein-catalog/components/sections/provenance-dialog.test.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/target-biology/schema` from Task 4, via the orval-generated hook.
- Produces: `ProvenanceDialog` and `useTargetBiologySchema()`. Removes the exports `ProvDraft`, `EMPTY_PROV`, `provToDraft`, `provToBody` and `provColumns`'s editable behaviour.

**Context — the bug being fixed.** `editable-record-table.tsx` currently round-trips provenance through:

```ts
export type ProvDraft = { source_type: string; pmid: string; note: string };
provToBody(d) => ({ source_type, citations: d.pmid ? [{ pmid }] : [], note })
```

`Provenance` carries `citations[]{pmid, doi, url, label}`, `contributor_researcher` and `observed_on`. Every edit through the table drops all of it. A record whose only citation is a DOI loses that citation entirely, because `d.pmid` is empty and `citations` becomes `[]`.

The record-field columns keep their inline editing — that part works and is presentation. Only provenance moves, because a *table* showing a subset of fields is cosmetic while a *form* omitting one is silent data loss.

- [ ] **Step 1: Write the failing test**

Create `provenance-dialog.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProvenanceDialog } from "./provenance-dialog";

const SCHEMA_FIELDS = [
  { name: "source_type", label: "Source type", type: "enum", required: true,
    options: ["published", "preprint", "internal"] },
  { name: "citations", label: "Citations", type: "list", required: false,
    item_type: "object",
    item_fields: [
      { name: "pmid", label: "PMID", type: "string", required: false },
      { name: "doi", label: "DOI", type: "string", required: false },
      { name: "url", label: "URL", type: "string", required: false },
      { name: "label", label: "Label", type: "string", required: false },
    ] },
  { name: "contributor_researcher", label: "Contributor", type: "string", required: false },
  { name: "observed_on", label: "Observed on", type: "date", required: false },
  { name: "note", label: "Note", type: "text", required: false },
];

const EXISTING = {
  source_type: "published",
  generation_method: "ai_extracted",
  citations: [
    { pmid: "28096490", doi: null, url: null, label: null },
    { pmid: null, doi: "10.1016/j.cell.2021.02.001", url: null, label: "Bosch 2021" },
  ],
  contributor_researcher: "A. Curator",
  observed_on: "2021-03-01",
  note: "from the supplementary table",
};

describe("ProvenanceDialog", () => {
  it("renders every descriptor field", () => {
    render(
      <ProvenanceDialog open fields={SCHEMA_FIELDS} value={EXISTING}
        onSave={vi.fn()} onClose={vi.fn()} />,
    );
    for (const label of ["Source type", "Contributor", "Observed on", "Note"]) {
      expect(screen.getByLabelText(new RegExp(label, "i"))).toBeInTheDocument();
    }
  });

  it("keeps every citation, including DOI-only ones", async () => {
    const onSave = vi.fn();
    render(
      <ProvenanceDialog open fields={SCHEMA_FIELDS} value={EXISTING}
        onSave={onSave} onClose={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    const saved = onSave.mock.calls[0][0];
    expect(saved.citations).toHaveLength(2);
    expect(saved.citations[1].doi).toBe("10.1016/j.cell.2021.02.001");
    expect(saved.citations[1].label).toBe("Bosch 2021");
    expect(saved.contributor_researcher).toBe("A. Curator");
    expect(saved.observed_on).toBe("2021-03-01");
  });

  it("never submits generation_method — the server re-attributes on write", async () => {
    const onSave = vi.fn();
    render(
      <ProvenanceDialog open fields={SCHEMA_FIELDS} value={EXISTING}
        onSave={onSave} onClose={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave.mock.calls[0][0]).not.toHaveProperty("generation_method");
  });

  it("adds and removes citation rows", async () => {
    const onSave = vi.fn();
    render(
      <ProvenanceDialog open fields={SCHEMA_FIELDS} value={EXISTING}
        onSave={onSave} onClose={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /add citation/i }));
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave.mock.calls[0][0].citations).toHaveLength(3);
  });

  it("has an explicit cancel alongside save", () => {
    render(
      <ProvenanceDialog open fields={SCHEMA_FIELDS} value={EXISTING}
        onSave={vi.fn()} onClose={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && pnpm vitest run src/features/protein-catalog/components/sections/provenance-dialog.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the descriptor hook**

Create `use-target-biology-schema.ts`. Use the orval-generated hook for `GET /api/v1/target-biology/schema` — after `make generate-api` in Task 4 it exists under `@/shared/lib/api/target-biology/target-biology` with a generated name following the same convention as `useGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGet`. Open that file and use the actual exported name.

```ts
/** The published write contract. It changes only on a deploy, so it never goes stale
 *  within a session — refetching it on focus would be pure noise. */
export function useTargetBiologySchema() {
  return useGetTargetBiologySchemaApiV1TargetBiologySchemaGet({
    query: { staleTime: Number.POSITIVE_INFINITY },
  });
}
```

- [ ] **Step 4: Write the dialog**

Create `provenance-dialog.tsx`. Build on the existing shadcn `Dialog`, `Select`, `Input`, `Textarea`, `Button` in `@/shared/components/ui/`. Requirements the test encodes:

- One control per descriptor field, in descriptor order; label bound with `htmlFor`/`id` so `getByLabelText` finds it.
- `enum` → `Select` over `options`. `date` → `<input type="date">`. `text` → `Textarea`. `string` → `Input`.
- `citations` (`type: "list"`, `item_type: "object"`) → a repeatable group of its `item_fields`, with an **Add citation** button and a Remove per row. Rows carry every sub-field, so a DOI-only citation survives.
- Initialise state from `value` by deep-copying its citations array — never by projecting onto a narrower shape.
- `onSave` receives the provenance body: every descriptor field, `citations` filtered to rows with at least one non-empty sub-field, and **no** `generation_method`.
- Explicit **Save** and **Cancel** buttons; Esc closes but is an accelerator only.

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && pnpm vitest run src/features/protein-catalog/components/sections/provenance-dialog.test.tsx`
Expected: PASS.

- [ ] **Step 6: Delete the lossy path and wire the dialog in**

In `editable-record-table.tsx`:
- Delete `ProvDraft`, `EMPTY_PROV`, `provToDraft`, `provToBody`, and the `PmidCell` editing behaviour.
- `provColumns()` keeps its three **read-only** render functions (Source badge, Reference, Note) and loses its `field`/`type`/`options` entries, so provenance is no longer inline-editable.
- Add a per-row **Provenance…** action that opens `ProvenanceDialog` with that record's provenance and, on save, calls `onUpdate(record.id, { provenance, version: record.version })`.
- Record-field saves now send only the record fields plus `version` — no provenance — so a field edit no longer re-attributes the record.

In `gene-record-tables.tsx` and `protein-record-tables.tsx`: remove `...provColumns()`'s draft fields from each `emptyDraft` and `toDraft`/`toBody`, since provenance no longer travels in the row draft. Each kind's `toBody` keeps its own record fields and adds `version: record.version`.

- [ ] **Step 7: Verify the whole frontend**

Run: `cd frontend && pnpm vitest run && pnpm exec tsc --noEmit && pnpm lint`
Expected: all clean. Fix any test that asserted the old three-field provenance behaviour — that behaviour was the bug.

- [ ] **Step 8: Live check**

Run `make dev`, open a gene with target-biology records, and confirm by hand:
1. A record with two citations still has two after editing an unrelated field.
2. The Source badge still shows the original generation method after that edit — not "Manual".
3. Saving the provenance dialog changes it to "Manual", which is correct: the evidence was re-attributed.
4. Both light and dark themes render the dialog correctly.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/protein-catalog/
git commit -m "fix(target-biology): stop the record form destroying provenance

The table round-tripped provenance through a three-field draft
{source_type, pmid, note}, so every edit dropped DOI and URL citations,
citations beyond the first, the contributor and the observed date. A
record whose only citation was a DOI lost it outright.

Provenance now has its own dialog rendered from the published descriptor,
so the form cannot omit a field the API accepts. Record-field edits no
longer submit provenance at all, which — with PATCH now partial — means
they no longer re-attribute the record to a human."
```

---

## Self-Review

**Spec coverage.** Every section of `2026-08-07-target-biology-api-hardening.md` maps to a task: §B → Task 1, §C → Task 2, §D → Task 3, §A → Task 4, §E → Task 5. The spec's build order (B, C, D, A, E) is preserved. The spec's explicit non-goals — descriptor-driven record-field forms, and collapsing the sixteen create/patch handlers — appear in no task, correctly.

**Type consistency.** `_patch_updates` is introduced in Task 1 Step 3 and revised once in Task 2 Step 5 (adding the `version` pop); both versions are shown in full rather than described. `_VALUE_OBJECT_FIELDS` includes `compound` and `ligands` from Task 1 even though their bodies arrive in Task 3 — harmless, since the set is intersected with keys actually present, and it means Task 3 needs no edit to the helper. `CompoundRefBody.to_domain()` is defined in Task 3 Step 3 and consumed by Task 3 Step 5 and by `_patch_updates`. `describe_write_surface(suggested)` and `SuggestedValuesReader.for_all_kinds()` are defined in Task 4 with matching `dict[tuple[str, str], list[str]]` types.

**Two places the implementer must verify against the code rather than trust this plan**, both flagged inline: the `create()` keyword names on `ResistanceMutation` / `UnpublishedStructure` / `Hypomorph` (Task 3 Step 5), and the orval-generated hook name for the schema endpoint (Task 5 Step 3). Both are cheap to check and expensive to guess wrong.
