"""Distinct stored values for the free-text vocabulary fields.

ponytail: distinct-over-stored-values, so a typo becomes a suggestion. It is still
strictly better than an empty combobox — it is what stops a second spelling of an
existing condition being invented. Swap for a curated vocabulary registry when
someone owns curation; the descriptor shape does not change.
"""

from __future__ import annotations

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
