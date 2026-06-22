# prot-cellar backend

FastAPI + SQLAlchemy (async) backend for the prot-cellar protein-target database.

## Quick start

```bash
# From repo root
make install    # install dependencies (uv + pnpm)
make up         # start Postgres :5433 + Valkey :6380 and run migrations
make dev        # start backend :8001 + frontend :3000
```

## Running imports

### Infra (Postgres + Valkey)

```bash
make up
```

### ARQ worker (required — imports stay `queued` without it)

The background worker processes import jobs enqueued via the API.
**`make up` does NOT start the worker** — it only starts Postgres + Valkey and
runs migrations.  If the worker is not running, every import you submit will sit
in `queued` state indefinitely and never transition to `running`.

Run the worker in a **separate terminal**, after `make up` and alongside `make dev`:

```bash
uv run --directory backend arq protcellar.infrastructure.ingestion.worker.WorkerSettings
```

The worker reads `DATABASE_URL` and `REDIS_URL` from `backend/.env`.
Keep it running for as long as you want imports to be processed.

### API flow

**Start an import** (`POST /api/v1/imports`):

```bash
# GO ontology (smallest — good smoke test)
curl -s -XPOST localhost:8001/api/v1/imports \
  -H 'content-type: application/json' \
  -d '{"import_type":"go_ontology","params":{"force":false}}'

# UniProt proteome
curl -s -XPOST localhost:8001/api/v1/imports \
  -H 'content-type: application/json' \
  -d '{"import_type":"proteome","params":{"proteome_id":"UP000001584"}}'

# Gene enrichment (with essentiality upload)
curl -s -XPOST localhost:8001/api/v1/imports/uploads \
  -F 'file=@path/to/dejesus_table_s3.xlsx'
# capture upload_ref from response, then:
curl -s -XPOST localhost:8001/api/v1/imports \
  -H 'content-type: application/json' \
  -d '{"import_type":"gene_enrichment","params":{"tax_id":83332,"essentiality_upload_ref":"<upload_ref>"}}'
```

**Poll status** (`GET /api/v1/imports/{id}`):

```bash
curl -s localhost:8001/api/v1/imports/<id>
```

Runs transition `queued → running → succeeded` (or `failed`). The final
`summary` field contains counts from the adapter (e.g. `terms_upserted`,
`entries`, `annotations_written`).

**List runs** (`GET /api/v1/imports`):

```bash
curl -s localhost:8001/api/v1/imports
```

### Import types

| `import_type`      | Required params                                   | Optional                              |
|--------------------|---------------------------------------------------|---------------------------------------|
| `go_ontology`      | —                                                 | `force: bool`                         |
| `proteome`         | `proteome_id: str` (e.g. `"UP000001584"`)         | `force`, `dry_run`, `limit`           |
| `gene_enrichment`  | `organism_id: UUID` or `tax_id: int`              | `gff_url`, `essentiality_upload_ref`  |

## Development

```bash
make test        # unit tests + import-linter
make test-api    # API tests (needs running Postgres + Valkey)
make lint        # ruff + mypy
make migrate     # run pending Alembic migrations
```

## Environment

Copy `.env.example` → `backend/.env` and fill in `SENTINEL_SERVICE_KEY`:

```
DATABASE_URL=postgresql+asyncpg://protcellar:protcellar@localhost:5433/protcellar
REDIS_URL=redis://localhost:6380
SENTINEL_URL=https://sentinel.orca-03.biobio.tamu.edu
SENTINEL_SERVICE_KEY=sk_...
```
