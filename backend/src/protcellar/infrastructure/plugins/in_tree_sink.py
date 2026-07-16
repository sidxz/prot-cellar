from __future__ import annotations

import uuid
from collections.abc import Sequence

from protcellar.application.auth import AuthContext
from protcellar.application.plugins.sink import Sink
from protcellar.application.target_biology._import_support import ItemResult
from protcellar.application.target_biology.bulk_upsert_essentiality import (
    BulkUpsertEssentiality,
    BulkUpsertEssentialityCommand,
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
                records=tuple(records),  # type: ignore[arg-type]  # elements are EssentialityImportRecord
                generation_method=self._generation_method,
                source_run_id=self._source_run_id,
                dry_run=self._dry_run,
            )
            out = (await self._essentiality(cmd, self._auth)).unwrap()
            self.results.extend(out)
            return out
        raise ValueError(f"no sink registered for record_type '{record_type}'")
