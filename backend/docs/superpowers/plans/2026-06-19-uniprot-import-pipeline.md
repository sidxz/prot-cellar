# UniProt Proteome Import Pipeline — Plan

> Follow-on to the schema plan (now complete). Goal: actually load `UP000001584`
> (*M. tuberculosis* H37Rv, 3,997 entries) into the schema. Three pieces:
> **mapper** (pure, done) → **fetcher** (httpx I/O) → **runner** (orchestration).

**Source URLs (verified):**
- Proteome metadata: `https://rest.uniprot.org/proteomes/UP000001584`
- Entries (lossless JSON, gzipped): `https://rest.uniprot.org/uniprotkb/stream?query=proteome:UP000001584&format=json&compressed=true`
- Paginated alt: `/uniprotkb/search?query=proteome:UP000001584&format=json&size=500` + follow `Link: rel="next"` cursor.

---

## Task A: Mapper — `infrastructure/ingestion/uniprot_mapper.py`  ✅ DONE

> `map_uniprot_entry(entry, *, organism_id, source, source_release) -> ProteinImportRecord`.
> Pure function; maps identity/provenance, sequence+scalars, names (incl short/EC),
> features, comments (+structured payload), isoforms (ALTERNATIVE PRODUCTS), keywords,
> citations (PubMed/DOI), cross-references (incl GO). 7 unit tests green; ruff/mypy clean.
> `source_record_checksum` = `e{entryVersion}s{sequenceVersion}` for idempotent re-sync.

## Task B: Fetcher — `infrastructure/ingestion/uniprot_client.py`  ✅ DONE

> Status: GREEN. `UniProtClient(httpx.AsyncClient)` with `fetch_proteome` + `iter_entries` (cursor-paginated via the `Link: rel="next"` header; client injected for testability). 2 unit tests with `httpx.MockTransport` — no real network; ruff/mypy clean.

- `class UniProtClient` wrapping `httpx.AsyncClient`.
- `async def fetch_proteome(proteome_id) -> dict` → GET `/proteomes/{id}` JSON.
- `async def iter_entries(proteome_id) -> AsyncIterator[dict]` → page `/uniprotkb/search?...&size=500`, follow the `Link` cursor header, yield each entry dict.
- Test with a mocked transport (httpx `MockTransport`) returning a 2-entry page + a no-next page — no real network in tests. Assert it yields both entries and stops.
- Keep ret/timeout simple; this is I/O glue, the mapper holds the logic.

## Task C: Runner — `application/protein_catalog/import_proteome.py` (+ a thin CLI script)  ⬜ TODO

Orchestrate (the only piece that needs DB + network together):
1. Fetch proteome metadata; resolve-or-create the `Organism` from `taxonId` + `scientificName`; create-or-update the `Proteome` row (idempotent on `uniprot_proteome_id`).
2. Stream entries; for each, resolve `organism_id`, `map_uniprot_entry(...)`, accumulate into chunks of ~500.
3. Feed each chunk to `BulkUpsertProteins` (already idempotent, dry-run capable, emits BULK_IMPORT audit).
4. After each protein upserts, `ProteomeRepository.add_protein(proteome_id, protein_id)` for membership.
5. Return a summary (created/updated/skipped/failed counts).
- Expose as a CLI: `python -m protcellar.scripts.import_proteome UP000001584 [--dry-run] [--limit N]`.
- Test the orchestration with a fake fetcher (in-memory entries) + real repos/uow (function-scoped engine, as in `test_proteome_membership.py`); assert proteins + membership land. `--limit` keeps a smoke test cheap.

**Open decision (deferred):** durable workflow (Temporal) vs. a plain async script. Start with the script; Temporal can wrap the runner later if resumability across crashes is needed (3,997 entries / ~6 MB gz is small enough that a script with chunked idempotent upserts is fine).
