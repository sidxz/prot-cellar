"""Dev-only: seed a rich mock target-biology set on ONE gene so the maps render.

REPLACES the target gene's essentiality / vulnerability / resistance-mutation
records with a demo set that exercises every per-gene map:

* essentiality — 4 records across 2 conditions x 2 methods, with a TnSeq/CRISPRi
  disagreement on cholesterol (so the condition x method strip shows a mismatch);
* vulnerability — 6 conditions incl. host-relevant carbon sources, with normalized
  credible bounds in ``extensions`` (so the forest draws whiskers) and one
  AI-predicted / private-communication row (blue in the table);
* resistance — 4 mutations across 2 compounds (so the lollipop and legend render).

Idempotent: clears the gene's existing records for those three record types first,
so re-running yields the same result (and does not duplicate).

Usage::

    uv run python -m protcellar.scripts.seed_mock_target_biology

The target gene is hard-coded below. Requires ``DATABASE_URL`` in the env (or ``.env``).
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.domain.target_biology.vulnerability import Vulnerability
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.resistance_mutation_repository import (  # noqa: E501
    SQLAlchemyResistanceMutationRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.vulnerability_repository import (  # noqa: E501
    SQLAlchemyVulnerabilityRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

GENE_ID = uuid.UUID("7ff43f31-3d12-4be7-a117-9b03b004ad2b")

_DEJESUS = Provenance(
    source_type=ProvenanceSourceType.PUBLISHED,
    citations=(Citation(pmid="28096490", label="DeJesus 2017"),),
)
_BOSCH = Provenance(
    source_type=ProvenanceSourceType.PUBLISHED,
    generation_method=GenerationMethod.IMPORTED,
    citations=(Citation(pmid="34297925", label="Bosch 2021"),),
)
_PRIVATE_AI = Provenance(
    source_type=ProvenanceSourceType.PRIVATE_COMM,
    generation_method=GenerationMethod.AI_PREDICTED,
    note="illustrative AI-predicted value",
)

# INH / EMB compound refs (ids are illustrative; daikon resolves real ones).
_INH = CompoundRef(compound_id=uuid.uuid4(), name="INH")
_EMB = CompoundRef(compound_id=uuid.uuid4(), name="EMB")


def _essentiality() -> list[Essentiality]:
    rows = [
        (EssentialityClass.ESSENTIAL, "7H9", "TnSeq", 0.95, _DEJESUS),
        (EssentialityClass.ESSENTIAL, "7H9", "CRISPRi", 0.90, _BOSCH),
        (EssentialityClass.GROWTH_DEFECT, "cholesterol", "TnSeq", 0.70, _DEJESUS),
        (EssentialityClass.ESSENTIAL, "cholesterol", "CRISPRi", 0.85, _BOSCH),
    ]
    return [
        Essentiality.create(
            workspace_id=GLOBAL_WORKSPACE_ID,
            gene_id=GENE_ID,
            classification=call,
            condition=condition,
            method=method,
            confidence=confidence,
            provenance=prov,
        )
        for call, condition, method, confidence, prov in rows
    ]


def _vulnerability() -> list[Vulnerability]:
    # (condition, score, confidence, lower, upper, provenance)
    rows = [
        ("cholesterol", 0.88, 0.60, 0.80, 0.94, _BOSCH),
        ("7H9", 0.78, 0.90, 0.72, 0.84, _BOSCH),
        ("glycerol", 0.74, 0.50, None, None, _BOSCH),
        ("oleic acid", 0.71, 0.85, 0.63, 0.79, _BOSCH),
        ("dextrose", 0.62, 0.40, None, None, _BOSCH),
        ("propionate", 0.55, 0.70, None, None, _PRIVATE_AI),
    ]
    out: list[Vulnerability] = []
    for condition, score, confidence, lower, upper, prov in rows:
        extensions: dict[str, object] = {"method_note": "CRISPRi-VI"}
        if lower is not None and upper is not None:
            extensions["score_lower"] = lower
            extensions["score_upper"] = upper
        out.append(
            Vulnerability.create(
                workspace_id=GLOBAL_WORKSPACE_ID,
                gene_id=GENE_ID,
                condition=condition,
                method="CRISPRi-VI",
                vulnerability_score=score,
                confidence=confidence,
                provenance=prov,
                extensions=extensions,
            )
        )
    return out


def _resistance() -> list[ResistanceMutation]:
    rows = [
        ("S315T", 200.0, _INH),
        ("D94G", 32.0, _INH),
        ("H270R", 8.0, _INH),
        ("G306V", 64.0, _EMB),
    ]
    return [
        ResistanceMutation.create(
            workspace_id=GLOBAL_WORKSPACE_ID,
            gene_id=GENE_ID,
            mutation=mutation,
            protein_coordinate=mutation,
            mic_shift=mic,
            compound=compound,
            method="selection",
            provenance=_DEJESUS,
        )
        for mutation, mic, compound in rows
    ]


async def _clear(repo, gene_id: uuid.UUID) -> int:  # type: ignore[no-untyped-def]
    existing = await repo.find_by_gene(GLOBAL_WORKSPACE_ID, gene_id)
    for rec in existing:
        await repo.delete(GLOBAL_WORKSPACE_ID, rec.id)
    return len(existing)


async def _main() -> None:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    try:
        async with uow:
            ess = SQLAlchemyEssentialityRepository(uow)
            vuln = SQLAlchemyVulnerabilityRepository(uow)
            res = SQLAlchemyResistanceMutationRepository(uow)

            cleared = 0
            cleared += await _clear(ess, GENE_ID)
            cleared += await _clear(vuln, GENE_ID)
            cleared += await _clear(res, GENE_ID)

            for e in _essentiality():
                await ess.save(e)
            for v in _vulnerability():
                await vuln.save(v)
            for m in _resistance():
                await res.save(m)

            await uow.commit()
        print(
            f"seeded gene {GENE_ID}: cleared {cleared}, "
            f"added 4 essentiality + 6 vulnerability + 4 resistance"
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
