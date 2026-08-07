"""Reads the distinct values already stored for each vocabulary field.

ponytail: N unindexed ``SELECT DISTINCT`` scans per cache miss (one per (kind, field)
pair, 18 today) — ``LIMIT 200`` bounds the result, not the scan. Fronted by a short
in-process TTL cache so the common case (one process serving many form-opens in a row)
pays that cost roughly once a minute rather than on every request. Add indexes on the
scanned columns, or a materialized/curated vocabulary table refreshed on write, if the
cache-miss cost or the staleness window ever becomes a real problem.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from protcellar.application.target_biology.crud import RecordKind
from protcellar.domain.target_biology.repository import SuggestedValuesReader
from protcellar.infrastructure.persistence.sqlalchemy.base import Base
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.models import (
    CrispriStrainModel,
    EssentialityRecordModel,
    HypomorphModel,
    ProteinActivityAssayModel,
    ProteinProductionModel,
    ResistanceMutationModel,
    UnpublishedStructureModel,
    VulnerabilityRecordModel,
)

_LIMIT = 200

# A value written mid-cache-window can wait for the next one; 60s keeps a single busy
# editing session (many form-opens in a row) warm without holding a stale list for long.
_TTL_SECONDS = 60.0

_MODELS: dict[RecordKind, type[Base]] = {
    RecordKind.ESSENTIALITY: EssentialityRecordModel,
    RecordKind.VULNERABILITY: VulnerabilityRecordModel,
    RecordKind.HYPOMORPH: HypomorphModel,
    RecordKind.CRISPRI_STRAIN: CrispriStrainModel,
    RecordKind.RESISTANCE_MUTATION: ResistanceMutationModel,
    RecordKind.PROTEIN_PRODUCTION: ProteinProductionModel,
    RecordKind.PROTEIN_ACTIVITY_ASSAY: ProteinActivityAssayModel,
    RecordKind.UNPUBLISHED_STRUCTURE: UnpublishedStructureModel,
}

# (kind -> field names). `tests/unit/interface/test_target_biology_schema.py` asserts
# this agrees with `_ANNOTATIONS`'s `vocabulary` flags in both directions — keep it that
# way instead of trusting eyes to catch a drift.
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


class SQLAlchemySuggestedValuesReader(SuggestedValuesReader):
    """Reads the distinct values already stored for each vocabulary field.

    Holds no per-request state (unlike the UoW-based repositories) — every call opens
    its own session — so it is safe, and for the cache below to do anything it is
    necessary, to register this as a singleton rather than build one per request.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        ttl_seconds: float = _TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session_factory = session_factory
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._cache: tuple[float, dict[tuple[str, str], list[str]]] | None = None

    async def for_all_kinds(self) -> dict[tuple[str, str], list[str]]:
        now = self._clock()
        if self._cache is not None and now - self._cache[0] < self._ttl_seconds:
            return self._cache[1]
        out = await self._fetch()
        self._cache = (now, out)
        return out

    async def _fetch(self) -> dict[tuple[str, str], list[str]]:
        out: dict[tuple[str, str], list[str]] = {}
        async with self._session_factory() as session:
            for kind, fields in _VOCABULARY_COLUMNS.items():
                model = _MODELS[kind]
                for field in fields:
                    column = getattr(model, field)
                    rows = await session.execute(
                        select(distinct(column))
                        .where(column.is_not(None))
                        .order_by(column)
                        .limit(_LIMIT)
                    )
                    out[(kind.value, field)] = [v for (v,) in rows if v]
        return out
