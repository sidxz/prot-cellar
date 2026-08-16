# Replicating a prot-cellar environment

Copy a teammate's database into your own environment, keeping every UUID
identical. Code comes from `main`; data comes from an archive.

## 0. Prerequisites

- Repo cloned, `make install` done, stack running (`make up`).
- `backend/.env` filled in with **your own** Duar app registration
  (`DUAR_URL`, `DUAR_SERVICE_NAME`, `DUAR_SERVICE_KEY`). Your app
  name does not need to match the exporter's.

## 1. Exporter: create the archive

```bash
cd backend
uv run python -m protcellar.scripts.export_data -o protcellar-data.tar.gz
```

Send the `.tar.gz` to the other developer (any way you like).

## 2. Importer: sync code and schema

```bash
git pull origin main
make migrate
```

## 3. Importer: load the archive

```bash
cd backend
uv run python -m protcellar.scripts.import_data protcellar-data.tar.gz --truncate
```

That's it. `--truncate` replaces whatever is in your tables; without it the
import refuses to touch a non-empty database.

## Flags

| Flag | When to use |
|------|-------------|
| `--truncate` | Your DB already has data you want replaced. |
| `--workspace <uuid>` | Only if your Duar is a **different install** than the exporter's: adopts their private-workspace rows into a workspace of yours. Same shared Duar → omit. |
| `--user <uuid>` | With `--workspace`, also take ownership of tag/user columns. |
| `--skip-duar-check` | Import without contacting Duar at all. |
| `--force` | Import despite a schema-revision mismatch (know what you're doing). |

## Troubleshooting

- **"Target database has no schema"** → run `make migrate` first.
- **"Schema mismatch"** → `git pull` + `make migrate` on whichever side is
  behind, then re-export/re-import.
- **"Target tables not empty"** → add `--truncate`.
- **"Duar check failed" (403/401)** → your `DUAR_*` values in
  `backend/.env` don't match a service app registered in your Duar; check
  the admin panel that the key belongs to that app name. To proceed without
  Duar, add `--skip-duar-check`.

The import is atomic — if anything fails, nothing is written.
