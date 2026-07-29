# Task 4 report: SQLAlchemyTagRepository

## Implementation

Ported chem-cellar's `tag_repository.py` to prot-cellar, adapted to the two
places prot-cellar's conventions differ:

1. **`Tag.create` signature** — prot-cellar's factory takes raw `key`/`value`
   params, not a `TagName` object (chem-cellar's does). The protocol's
   `get_or_create(workspace_id, name: TagName, created_by)` still takes a
   `TagName`, so `get_or_create` unpacks it: `Tag.create(workspace_id=...,
   key=name.key, value=name.value, created_by=...)`.
2. **Base-class reuse** — prot-cellar's `SQLAlchemyRepository` base already
   implements `find_by_id_in_workspace`, `save` (with optimistic
   concurrency), and `delete` (workspace-scoped `DELETE ... WHERE
   workspace_id = ...`), all matching the `TagRepository` protocol exactly.
   Chem-cellar's version re-implements `delete` itself; here it's dropped —
   only `find_by_normalized`, `get_or_create`, `search`, and the three
   mapping methods (`_to_domain`/`_to_model`/`_update_model`) are new code.
3. **LIKE-escape helper** — chem-cellar factors `escape_like` into a shared
   `_sql.py` module (used by several repositories there). Grepped
   prot-cellar: no repository currently escapes LIKE metacharacters, so
   there's no second caller yet. Inlined a private `_escape_like` in
   `tag_repository.py` with a `ponytail:` comment noting the promotion path
   if a second caller shows up, rather than adding a new shared module for
   one call site.
4. **mypy** — `result.rowcount` on the `pg_insert(...).on_conflict_do_nothing()`
   execute result triggers the same `attr-defined` mypy error chem-cellar
   has (unsuppressed there). prot-cellar's own `base_repository.py` already
   suppresses the identical pattern with `# type: ignore[attr-defined]`, so
   the same suppression was added here for consistency with the local
   convention (chem-cellar's copy was left as-is — out of scope for this
   port).

`search`'s usage-count ordering (via the `tag_links_all` cross-type view),
`"key=value"` split-query matching, and case-folded LIKE substring matching
were ported unchanged.

## TDD: RED → GREEN

**Test file:** `backend/tests/integration/workspace_config/test_tag_repository.py`
(mirrors the existing `tests/integration/target_biology/test_repositories.py`
fixture pattern: function-scoped `uow: AsyncUnitOfWork` fixture from
`tests/conftest.py`, session-scoped testcontainer Postgres + Alembic
migrations, `pytest.mark.asyncio(loop_scope="session")` to avoid closing the
asyncpg pool's event loop between tests.)

Three cases per the brief:
1. `test_get_or_create_is_idempotent` — two `get_or_create` calls with the
   same `TagName(key="env", value="prod")` return the same `id`; a raw
   `COUNT(*)` on `tags` for the workspace confirms exactly one row.
2. `test_get_or_create_valueless_dedup` — same, but `TagName(key="priority")`
   (no value) — exercises the `NULLS NOT DISTINCT` unique index.
3. `test_find_by_normalized_round_trips` — creates `TagName(key="Team",
   value="Bio")`, then `find_by_normalized` with the casefolded
   `TagName(key="team", value="bio")` returns the same tag with display
   casing preserved (`key == "Team"`, `value == "Bio"`).

**RED** (module didn't exist yet):

```
$ uv run pytest tests/integration/workspace_config/test_tag_repository.py -v
...
ERROR collecting tests/integration/workspace_config/test_tag_repository.py
ModuleNotFoundError: No module named
'protcellar.infrastructure.persistence.sqlalchemy.tagging.tag_repository'
=========================== short test summary info ============================
ERROR tests/integration/workspace_config/test_tag_repository.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.26s ===============================
```

**GREEN** (after writing `tag_repository.py`):

```
$ uv run pytest tests/integration/workspace_config/test_tag_repository.py -v
tests/integration/workspace_config/test_tag_repository.py::test_get_or_create_is_idempotent PASSED [ 33%]
tests/integration/workspace_config/test_tag_repository.py::test_get_or_create_valueless_dedup PASSED [ 66%]
tests/integration/workspace_config/test_tag_repository.py::test_find_by_normalized_round_trips PASSED [100%]
========================= 3 passed, 1 warning in 6.24s =========================
```

(The one warning is pre-existing — `PytestUnknownMarkWarning` for the
`integration` marker registered in `tests/conftest.py`, unrelated to this
change.)

## Additional verification

- `uv run ruff check` on both new files — clean.
- `uv run mypy src/protcellar/infrastructure/persistence/sqlalchemy/tagging/tag_repository.py`
  — clean (after adding the `type: ignore[attr-defined]` noted above).
- `uv run lint-imports` (import-linter, 337 files / 2031 deps) — all 3
  contracts kept (Clean Architecture layers, domain purity, bounded-context
  independence). No new violations.
- Runtime `isinstance(SQLAlchemyTagRepository(uow), TagRepository)` → `True`
  — confirms structural conformance to the `@runtime_checkable` Protocol.

## Files changed

- `backend/src/protcellar/infrastructure/persistence/sqlalchemy/tagging/tag_repository.py` (new)
- `backend/tests/integration/workspace_config/test_tag_repository.py` (new)
- `backend/tests/integration/workspace_config/__init__.py` (new, empty — matches
  the existing `tests/integration/target_biology/__init__.py` convention)

The unrelated pre-existing modification to
`frontend/src/features/taxonomy/components/strain-form-dialog.tsx` was left
untouched and unstaged, per instructions.

## Self-review

- Matched the brief's explicit interface note (`Tag.create(key=..., value=...)`)
  rather than blindly porting chem-cellar's `Tag.create(name=...)` call —
  verified against `domain/workspace_config/tagging/tag.py` before writing
  the repository.
- Confirmed via `base_repository.py` that `find_by_id_in_workspace`, `save`,
  and `delete` don't need overriding — reusing them (rather than re-porting
  chem-cellar's redundant `delete`) is the smaller, correct diff; behavior is
  identical (workspace-scoped delete matching the protocol signature).
- Verified the `uq_tags_ws_norm` index columns
  (`workspace_id, normalized_key, normalized_value`, `NULLS NOT DISTINCT`) in
  both `models.py` and the `713bff91ff30_tagging.py` migration match the
  `on_conflict_do_nothing(index_elements=[...])` target exactly.
- Did not touch `TagLinkRepository`/`TagLinkRepositoryProvider` — out of
  scope for this task (Task 4 is the Tag aggregate repository only).

## Concerns

- None blocking. Two things worth flagging for whoever does the next task
  that touches `search()`'s LIKE escaping broadly:
  - The `_escape_like` helper is currently private/inlined to this one file.
    If a future task adds substring search to another repository (protein,
    gene, organism dashboards already use unescaped `.ilike()` — a
    pre-existing gap, not introduced here), consider promoting it to a
    shared `sqlalchemy/_sql.py` at that point rather than duplicating it.
  - `get_or_create`'s conflict-loser path calls `tag.clear_events()` then
    re-queries by `find_by_normalized` — this is a second round-trip on the
    (rare) race path, identical to chem-cellar's behavior. No change needed,
    just noting it's inherited, not newly introduced, latency behavior.
- Note: this report overwrites a stale `task-4-report.md` from an earlier,
  unrelated task-numbering round (frontend import-hub column defs, dated
  Jul 16) — filename is reused across the SDD plan sequences, per the
  brief's instruction to write to this exact path.
