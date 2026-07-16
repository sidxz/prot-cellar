"""One-off: seed typed Essentiality records from existing essentiality GeneAnnotations.

For each gene carrying a VULNERABILITY/essentiality annotation, create an
``Essentiality`` record. This is **additive** — the annotation is intentionally
KEPT, because it is still the live read source (e.g. the gene-neighborhood view)
until a future slice wires typed-essentiality ingestion and repoints consumers to
``essentiality_records``. Idempotent — a gene that already has an essentiality
record is skipped. Commits per page so a failure loses at most one page.

Usage::

    uv run python -m protcellar.scripts.backfill_essentiality

Requires ``DATABASE_URL`` in the environment (or ``.env``).
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.shared.provenance import Citation, Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

# Stored annotation values are the DeJesus parser's normalized calls (hyphenated);
# map to the typed enum. Unknown -> UNCERTAIN, raw preserved in extensions.
# ponytail: calibration knob — verify against real data if a new source is added.
_CLASSIFICATION = {
    "essential": EssentialityClass.ESSENTIAL,
    "growth-defect": EssentialityClass.GROWTH_DEFECT,
    "non-essential": EssentialityClass.NON_ESSENTIAL,
    "growth-advantage": EssentialityClass.GROWTH_ADVANTAGE,
    "uncertain": EssentialityClass.UNCERTAIN,
}
_DEJESUS_METHOD = "TnSeq"
_PAGE = 1000


def is_essentiality_annotation(a: GeneAnnotation) -> bool:
    return a.axis is GeneAnnotationAxis.VULNERABILITY and a.key == "essentiality"


def _pmid_from_evidence(evidence: str | None) -> str | None:
    if evidence and evidence.upper().startswith("PMID:"):
        return evidence.split(":", 1)[1].strip()
    return None


def build_essentiality(gene_id: uuid.UUID, a: GeneAnnotation) -> Essentiality:
    classification = _CLASSIFICATION.get(a.value.strip().lower(), EssentialityClass.UNCERTAIN)
    citations: tuple[Citation, ...] = ()
    pmid = _pmid_from_evidence(a.evidence)
    if pmid or a.dataset:
        citations = (Citation(pmid=pmid, label=a.dataset),)
    return Essentiality.create(
        workspace_id=GLOBAL_WORKSPACE_ID,
        gene_id=gene_id,
        classification=classification,
        condition=a.condition,
        method=_DEJESUS_METHOD,
        provenance=Provenance(source_type=ProvenanceSourceType.PUBLISHED, citations=citations),
        extensions={"raw_call": a.value},
    )


async def backfill(
    uow: AsyncUnitOfWork,
    gene_repo: SQLAlchemyGeneRepository,
    essentiality_repo: SQLAlchemyEssentialityRepository,
) -> int:
    """Create Essentiality records from existing annotations. Returns records created.

    Additive — annotations are NOT stripped (they remain the live source). Pages
    through every gene by id cursor and commits each page, so a failure loses at
    most one page of progress and the transaction stays bounded.
    """
    created = 0
    cursor: uuid.UUID | None = None
    while True:
        genes = await gene_repo.find_all(cursor_id=cursor, limit=_PAGE)
        if not genes:
            break
        cursor = genes[-1].id
        for gene in genes:
            ess = [a for a in gene.annotations if is_essentiality_annotation(a)]
            if not ess:
                continue
            if await essentiality_repo.find_by_gene(GLOBAL_WORKSPACE_ID, gene.id):
                continue  # idempotent — already seeded
            for annotation in ess:
                await essentiality_repo.save(build_essentiality(gene.id, annotation))
                created += 1
        await uow.commit()
    return created


async def _main() -> None:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    try:
        async with uow:
            n = await backfill(
                uow, SQLAlchemyGeneRepository(uow), SQLAlchemyEssentialityRepository(uow)
            )
        print(f"essentiality records created: {n}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
