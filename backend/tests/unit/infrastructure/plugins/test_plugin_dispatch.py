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
