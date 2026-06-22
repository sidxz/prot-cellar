"""TDD test: ProgressReporter threading through the three import runners.

Verifies:
1. GeneEnrichmentRunner calls phase("fetch GFF") first and phase("enrich") at all.
2. GoImportRunner calls phase("probe version") first and phase("upsert") at all,
   and reports a source_version.
3. No-op default keeps existing behaviour (regression guard).
4. NoopProgressReporter satisfies the ProgressReporter Protocol.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator, Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.application.imports.progress_reporter import ProgressReporter


# --------------------------------------------------------------------------- #
# Recording reporter                                                            #
# --------------------------------------------------------------------------- #


class _RecordingReporter:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.advances: list[tuple[int, int | None]] = []
        self.versions: list[str | None] = []

    async def phase(self, label: str) -> None:
        self.phases.append(label)

    async def advance(self, processed: int, total: int | None = None) -> None:
        self.advances.append((processed, total))

    async def source_version(self, version: str | None) -> None:
        self.versions.append(version)


# --------------------------------------------------------------------------- #
# GFF / enrichment fakes (adapted from test_gene_enrichment_runner.py)         #
# --------------------------------------------------------------------------- #

_GFF = "##gff-version 3\n#!genome-build ASM19595v2\n" + "\n".join(
    "\t".join(cols)
    for cols in (
        (
            "NC_000962.3",
            "Mycobrowser",
            "CDS",
            "759807",
            "763325",
            ".",
            "+",
            "0",
            "Locus=Rv0667;Name=rpoB;Functional_Category=Information pathways",
        ),
        (
            "NC_000962.3",
            "Mycobrowser",
            "CDS",
            "2153889",
            "2156111",
            ".",
            "-",
            "0",
            "Locus=Rv1908c;Name=katG;Functional_Category=Virulence%2C detoxification%2C adaptation",
        ),
    )
)


class _FakeGffClient:
    def __init__(self, text_by_url: dict[str, str]) -> None:
        self._by_url = text_by_url

    async def fetch_text(self, url: str) -> str:
        return self._by_url[url]


class _CapturingBulkEnrich:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def __call__(
        self,
        organism_id: uuid.UUID,
        records: Sequence[object],
        auth: object | None = None,
    ) -> object:
        from protcellar.application.protein_catalog.bulk_enrich_genes import EnrichSummary
        from returns.result import Success

        self.records = list(records)
        return Success(
            EnrichSummary(
                matched=len(self.records),
                unmatched=0,
                locations_set=len(self.records),
                annotations_written=0,
            )
        )


_GFF_URL = "https://mycobrowser.example/h37rv.gff"


def _build_enrichment_runner(**extra_kwargs: object) -> object:
    from protcellar.infrastructure.ingestion.gene_enrichment_runner import GeneEnrichmentRunner

    client = _FakeGffClient({_GFF_URL: _GFF})
    bulk = _CapturingBulkEnrich()
    return GeneEnrichmentRunner(bulk, client, gff_url=_GFF_URL, **extra_kwargs)  # type: ignore[arg-type]


def _admin() -> object:
    from tests.fakes.fake_auth import FakeAuth

    return FakeAuth(role="admin")


# --------------------------------------------------------------------------- #
# GO runner fixtures (real DB — same pattern as test_go_import_runner.py)      #
# --------------------------------------------------------------------------- #

_OBO_FIXTURE = """format-version: 1.2
data-version: releases/2026-99-01
ontology: go

[Term]
id: GO:0099001
name: alpha
namespace: molecular_function
is_a: GO:0099002 ! beta

[Term]
id: GO:0099002
name: beta
namespace: molecular_function
"""


@pytest.fixture
async def go_runner_uow(database_url: str, _run_migrations: None) -> AsyncIterator[object]:
    from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


def _build_go_runner(uow: object, **extra_kwargs: object) -> object:
    from protcellar.infrastructure.ingestion.go_import_runner import GoImportRunner
    from protcellar.infrastructure.ingestion.go_obo import read_obo

    return GoImportRunner(
        uow,  # type: ignore[arg-type]
        source_url="x",
        read_obo=lambda src: read_obo(io.StringIO(_OBO_FIXTURE)),
        probe_version=lambda src: "releases/2026-99-01",
        **extra_kwargs,
    )


# --------------------------------------------------------------------------- #
# Tests: GeneEnrichmentRunner                                                   #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_gene_enrichment_runner_reports_phases() -> None:
    reporter = _RecordingReporter()
    runner = _build_enrichment_runner(reporter=reporter)
    await runner.run(uuid.uuid4(), auth=_admin())  # type: ignore[attr-defined]

    assert reporter.phases[0] == "fetch GFF", (
        f"Expected 'fetch GFF' as first phase, got: {reporter.phases}"
    )
    assert "enrich" in reporter.phases, (
        f"Expected 'enrich' in phases, got: {reporter.phases}"
    )
    # parse should come before enrich
    assert reporter.phases.index("parse") < reporter.phases.index("enrich")


@pytest.mark.asyncio
async def test_gene_enrichment_runner_noop_default_keeps_existing_behavior() -> None:
    """Regression guard: runner without reporter still returns valid summary."""
    runner = _build_enrichment_runner()  # no reporter= kwarg
    summary = await runner.run(uuid.uuid4(), auth=_admin())  # type: ignore[attr-defined]
    assert summary.matched >= 0  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Tests: GoImportRunner                                                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_go_import_runner_reports_phases(go_runner_uow: object) -> None:
    reporter = _RecordingReporter()
    runner = _build_go_runner(go_runner_uow, reporter=reporter)
    await runner.run(force=True)  # type: ignore[attr-defined]

    assert reporter.phases[0] == "probe version", (
        f"Expected 'probe version' as first phase, got: {reporter.phases}"
    )
    assert "upsert" in reporter.phases, (
        f"Expected 'upsert' in phases, got: {reporter.phases}"
    )
    # source_version should have been reported
    assert any(v is not None and "2026-99-01" in v for v in reporter.versions), (
        f"Expected a version containing '2026-99-01', got: {reporter.versions}"
    )


@pytest.mark.asyncio
async def test_go_import_runner_noop_default_keeps_existing_behavior(
    go_runner_uow: object,
) -> None:
    """Regression guard: runner without reporter still returns valid summary."""
    runner = _build_go_runner(go_runner_uow)  # no reporter= kwarg
    result = await runner.run(force=True)  # type: ignore[attr-defined]
    assert result.terms_upserted >= 0  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Tests: NoopProgressReporter satisfies the Protocol                            #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_noop_progress_reporter_satisfies_protocol() -> None:
    from protcellar.application.imports.progress_reporter import NoopProgressReporter

    noop = NoopProgressReporter()
    assert isinstance(noop, ProgressReporter)
    # All methods are no-ops — calling them must not raise
    await noop.phase("any")
    await noop.advance(1, 100)
    await noop.source_version("v1")
