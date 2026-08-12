# Data replication CLI (export / import) — design

2026-08-12

## Problem

Other developers replicate our environment by pulling code from `main`, but the
database contents (organisms, proteomes, proteins, genes, target-biology
records, tags, workspace config …) must be copied with **identical UUIDs** so
that URLs, notebooks, and cross-references keep working. Each developer runs
their **own Sentinel** with their **own service registration** (we use app name
`prot-cellar-dev`; another dev may use `prot-cellar-dev1`) and therefore has
different workspace and user UUIDs.

## Decision

Two plain CLIs in `backend/src/protcellar/scripts/`, generic over
`Base.metadata` (the `metadata.py` aggregator already imports every model, so
new tables are covered automatically):

- `export_data.py` → one `.tar.gz` containing `manifest.json` +
  `tables/<table>.jsonl`
- `import_data.py` → restores that archive into the target database,
  preserving every UUID, remapping only Sentinel-owned identifiers

### Alternatives rejected

- **pg_dump / pg_restore** — preserves UUIDs but still needs a wrapper for the
  Sentinel checks and workspace remapping, requires matching client binaries /
  an empty database, and can't exclude machine-local tables cleanly at restore
  time. The wrapper would be most of the code anyway.
- **Existing CSV bulk-upsert CLIs** — generate new UUIDs and cover only the 8
  target-biology kinds, not the whole catalog.

## Export

- Connects with `DatabaseSettings` (same pattern as every other script CLI).
- Dumps all tables in `Base.metadata.sorted_tables` order **except**
  `audit_entries`, `audit_operations`, `electronic_signatures`,
  `import_runs`, `import_uploads` — machine-local operational/compliance
  history (also the only `LargeBinary` column). No domain table has an FK into
  the excluded set, so exclusion is safe.
- Each table streams (server-side cursor) to a JSONL temp file, then into the
  tar. UUIDs/datetimes serialize as strings; JSONB and `ARRAY(String)` are
  native JSON.
- `manifest.json` records: `schema_rev` (from `alembic_version`), per-table row
  counts, the distinct **non-shared** `workspace_id` values found, the source
  `SENTINEL_SERVICE_NAME` (informational), and the excluded table names.

## Import

Preflight, in order:

1. **Schema**: target `alembic_version` must equal the manifest's
   `schema_rev`; otherwise exit telling the dev to `git pull && alembic
   upgrade head` (`--force` overrides). Missing tables → same message.
2. **Sentinel** (skip with `--skip-sentinel-check`): build the SDK client from
   the dev's *own* `.env` (`SENTINEL_URL`, `SENTINEL_SERVICE_NAME`,
   `SENTINEL_SERVICE_KEY`) and call the existing
   `register_service_actions()`. Success proves their app registration
   (whatever its name) is valid *and* registers the `protcellar:*` RBAC
   actions under it — the only thing prot-cellar ever registers in Sentinel.
   Failure exits with a pointer to the `SENTINEL_*` variables and the admin
   panel.
3. **Workspace remap**: rows owned by `SHARED_WORKSPACE_ID` (a `uuid5`
   constant, identical in every install) import unchanged. Any other
   `workspace_id` is rewritten to the value of `--workspace <uuid>` (the dev's
   workspace UUID from their Sentinel). If the manifest lists non-shared ids
   and `--workspace` is missing, exit and say so. `--user <uuid>` likewise
   rewrites `created_by` / `user_id` columns when given; otherwise the
   original UUIDs are kept (foreign but harmless — nobody in the target
   Sentinel can claim them).

Load:

- Refuses to write into non-empty target tables unless `--truncate`, which
  deletes in reverse FK order first. Re-import is therefore idempotent.
- Inserts in `sorted_tables` order (FK-safe), batches of 1000, coercing values
  by column type (`Uuid` → `uuid.UUID`, `DateTime`/`Date` → `fromisoformat`).
  No sequences exist to bump (all PKs are UUIDs).

## Testing

One integration test on the existing testcontainers Postgres: seed shared +
workspace-scoped rows, export, wipe, import with `--workspace` remap and
Sentinel check skipped, assert identical entity UUIDs, remapped
`workspace_id`, and equal payloads.

## Out of scope (YAGNI)

Incremental/merge imports, cross-schema-version migration of archives, subset
filtering, S3/drive transport, any UI. The archive is a file; devs share it
however they like.
