from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from protcellar.application.plugins.sink import Sink
from protcellar.application.target_biology._import_support import ItemResult

# A record-type upserter: takes the plugin's record list, returns per-item results.
# The dispatch adapter builds one per record_type it supports, each closing over the
# wired BulkUpsert<X> command + the run's stamping (generation_method, source_run_id,
# dry_run). Adding a target record is a one-line entry in that map — the sink and the
# worker never change.
Upserter = Callable[[Sequence[object]], Awaitable[list[ItemResult]]]


class InTreeSink(Sink):
    """Routes record_type -> a wired upserter, accumulating every ItemResult in
    ``results`` so the dispatch adapter can summarize the run."""

    def __init__(self, upserters: dict[str, Upserter]) -> None:
        self._upserters = upserters
        self.results: list[ItemResult] = []

    async def upsert(self, record_type: str, records: Sequence[object]) -> list[ItemResult]:
        try:
            upserter = self._upserters[record_type]
        except KeyError as e:
            raise ValueError(f"no sink registered for record_type '{record_type}'") from e
        out = await upserter(records)
        self.results.extend(out)
        return out
