"""Orchestrates importing the GO ontology into the gene_ontology context.

Mirrors the UniProt runner: a cheap version probe → `read_obo` → `parse_obo` →
version-gated idempotent upsert. `read_obo` + `probe_version` are injected so the
runner is testable without network, and are run in a worker thread so the (sync,
obonet/httpx) download doesn't block the event loop.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from protcellar.application.imports.progress_reporter import NoopProgressReporter, ProgressReporter
from protcellar.infrastructure.ingestion.go_obo import parse_obo
from protcellar.infrastructure.ingestion.go_obo import read_obo as _default_read_obo
from protcellar.infrastructure.persistence.sqlalchemy.gene_ontology.go_ontology_repository import (
    SQLAlchemyGoOntologyRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

GO_BASIC_OBO_URL = "http://purl.obolibrary.org/obo/go/go-basic.obo"
_VERSION_RE = re.compile(r"^data-version:\s*(\S+)", re.MULTILINE)


@dataclass
class GoImportSummary:
    source_version: str
    terms_upserted: int = 0
    edges: int = 0
    skipped_unchanged: bool = False


def _probe_version(url: str) -> str:
    """Cheaply read `data-version` from the OBO header (first ~2 KB) without a full download."""
    resp = httpx.get(url, headers={"Range": "bytes=0-2047"}, follow_redirects=True, timeout=30.0)
    match = _VERSION_RE.search(resp.text)
    return match.group(1) if match else ""


class GoImportRunner:
    def __init__(
        self,
        uow: AsyncUnitOfWork,
        *,
        source_url: str = GO_BASIC_OBO_URL,
        read_obo: Callable[[Any], Any] = _default_read_obo,
        probe_version: Callable[[str], str] = _probe_version,
        reporter: ProgressReporter = NoopProgressReporter(),
    ) -> None:
        self._uow = uow
        self._source_url = source_url
        self._read_obo = read_obo
        self._probe_version = probe_version
        self._reporter = reporter

    async def run(self, *, force: bool = False) -> GoImportSummary:
        await self._reporter.phase("probe version")
        version = await asyncio.to_thread(self._probe_version, self._source_url)
        await self._reporter.source_version(version or None)
        if not force:
            async with self._uow:
                latest = await SQLAlchemyGoOntologyRepository(self._uow).latest_source_version()
            if version and version == latest:
                return GoImportSummary(source_version=version, skipped_unchanged=True)

        await self._reporter.phase("download")
        graph = await asyncio.to_thread(self._read_obo, self._source_url)

        await self._reporter.phase("parse")
        terms, edges, data_version = parse_obo(graph)
        version = data_version or version
        await self._reporter.source_version(version or None)

        await self._reporter.phase("upsert")
        async with self._uow:
            repo = SQLAlchemyGoOntologyRepository(self._uow)
            await repo.upsert_terms(terms, source_version=version)
            await repo.replace_edges(edges)
            await self._uow.commit()
        return GoImportSummary(source_version=version, terms_upserted=len(terms), edges=len(edges))
