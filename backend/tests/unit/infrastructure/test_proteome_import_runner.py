"""Integration test for the proteome import runner — fake fetcher, real DB.

Exercises the whole pipeline (fetch → ensure organism + proteome → stream/map →
chunked BulkUpsertProteins → link membership) without touching the network, using
a function-scoped engine/UoW like ``test_proteome_membership``.

Each test uses distinct accessions / proteome id / tax id because the
function-scoped engine commits to the session-scoped container (no rollback),
so data persists across tests in the same run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.application.protein_catalog.bulk_upsert_genes import BulkUpsertGenes
from protcellar.application.protein_catalog.bulk_upsert_proteins import BulkUpsertProteins
from protcellar.infrastructure.ingestion.import_runner import ProteomeImportRunner
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.proteome_repository import (
    SQLAlchemyProteomeRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.strain_repository import (
    SQLAlchemyStrainRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from tests.fakes.fake_auth import FakeAuth


def _meta(proteome_id: str, tax_id: int, modified: str = "2026-01-01") -> dict[str, Any]:
    return {
        "id": proteome_id,
        "taxonomy": {"taxonId": tax_id, "scientificName": "Importus testus"},
        "proteomeType": "Reference proteome",
        "modified": modified,
    }


def _simple_entries(*accs: str) -> list[dict[str, Any]]:
    return [
        {
            "primaryAccession": a,
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "sequence": {"value": "MKTAYIAKQR"},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
        }
        for a in accs
    ]


def _entries(acc1: str, acc2: str) -> list[dict[str, Any]]:
    return [
        {
            "primaryAccession": acc1,
            "uniProtkbId": "T1_TEST",
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "sequence": {"value": "MKTAYIAKQR", "molWeight": 1200, "crc64": "AAAA"},
            "organism": {"taxonId": 99970},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
            "features": [
                {"type": "Chain", "location": {"start": {"value": 1}, "end": {"value": 10}}}
            ],
        },
        {
            "primaryAccession": acc2,
            "uniProtkbId": "T2_TEST",
            "entryType": "UniProtKB unreviewed (TrEMBL)",
            "sequence": {"value": "MKTAYIAKQS", "molWeight": 1201, "crc64": "BBBB"},
            "organism": {"taxonId": 99970},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
        },
    ]


class _FakeClient:
    def __init__(self, meta: dict[str, Any], entries: list[dict[str, Any]]) -> None:
        self._meta = meta
        self._entries = entries

    async def fetch_proteome(self, proteome_id: str) -> dict[str, Any]:
        return self._meta

    async def iter_entries(self, proteome_id: str) -> AsyncIterator[dict[str, Any]]:
        for entry in self._entries:
            yield entry


class _NoopDispatcher:
    async def dispatch_all(self, events: Any) -> None:
        return None


@pytest.fixture
async def import_uow(database_url: str, _run_migrations: None) -> AsyncIterator[AsyncUnitOfWork]:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield AsyncUnitOfWork(factory)
    finally:
        await engine.dispose()


def _runner(
    uow: AsyncUnitOfWork,
    meta: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    with_genes: bool = False,
):
    protein_repo = SQLAlchemyProteinRepository(uow)
    bulk = BulkUpsertProteins(uow, protein_repo, _NoopDispatcher())  # type: ignore[arg-type]
    gene_bulk = None
    if with_genes:
        gene_bulk = BulkUpsertGenes(uow, SQLAlchemyGeneRepository(uow), _NoopDispatcher())  # type: ignore[arg-type]
    runner = ProteomeImportRunner(
        uow, _FakeClient(meta, entries), bulk, gene_bulk=gene_bulk, chunk_size=500
    )
    return runner, protein_repo


@pytest.mark.asyncio
async def test_import_creates_organism_proteome_proteins_and_membership(
    import_uow: AsyncUnitOfWork,
) -> None:
    runner, protein_repo = _runner(
        import_uow, _meta("UP000000099", 99970), _entries("P0DK01", "P0DK02")
    )

    summary = await runner.run("UP000000099", auth=FakeAuth(role="admin"))

    assert summary.entries == 2
    assert summary.created == 2
    assert summary.members_linked == 2

    async with import_uow:
        prepo = SQLAlchemyProteomeRepository(import_uow)
        proteome = await prepo.find_by_proteome_id("UP000000099")
        assert proteome is not None
        member_ids = await prepo.list_protein_ids(proteome.id)
        assert len(member_ids) == 2

        got = await protein_repo.find_by_accession("P0DK01")
        assert got is not None
        assert got.entry_name == "T1_TEST"
        assert len(got.features) == 1


@pytest.mark.asyncio
async def test_import_dry_run_persists_nothing(import_uow: AsyncUnitOfWork) -> None:
    runner, _ = _runner(import_uow, _meta("UP000000098", 99971), _entries("P0DK03", "P0DK04"))

    summary = await runner.run("UP000000098", dry_run=True, auth=FakeAuth(role="admin"))
    assert summary.entries == 2
    assert summary.created == 2
    assert summary.members_linked == 0

    async with import_uow:
        repo = SQLAlchemyProteinRepository(import_uow)
        assert await repo.find_by_accession("P0DK03") is None


@pytest.mark.asyncio
async def test_version_gate_skips_unchanged(import_uow: AsyncUnitOfWork) -> None:
    runner, _ = _runner(import_uow, _meta("UP000000088", 99975), _entries("P0DW01", "P0DW02"))
    first = await runner.run("UP000000088", auth=FakeAuth(role="admin"))
    assert first.created == 2

    runner2, _ = _runner(import_uow, _meta("UP000000088", 99975), _entries("P0DW01", "P0DW02"))
    second = await runner2.run("UP000000088", auth=FakeAuth(role="admin"))
    assert second.skipped_unchanged is True
    assert second.entries == 0

    third = await runner2.run("UP000000088", auth=FakeAuth(role="admin"), force=True)
    assert third.skipped_unchanged is False
    assert third.entries == 2


@pytest.mark.asyncio
async def test_reconcile_prunes_departed_members(import_uow: AsyncUnitOfWork) -> None:
    runner, _ = _runner(
        import_uow, _meta("UP000000077", 99976), _simple_entries("P0DW10", "P0DW11", "P0DW12")
    )
    first = await runner.run("UP000000077", auth=FakeAuth(role="admin"))
    assert first.members_linked == 3

    runner2, _ = _runner(
        import_uow,
        _meta("UP000000077", 99976, modified="2026-02-02"),
        _simple_entries("P0DW10", "P0DW11"),
    )
    second = await runner2.run("UP000000077", auth=FakeAuth(role="admin"))
    assert second.members_pruned == 1

    async with import_uow:
        prepo = SQLAlchemyProteomeRepository(import_uow)
        proteome = await prepo.find_by_proteome_id("UP000000077")
        assert proteome is not None
        assert len(await prepo.list_protein_ids(proteome.id)) == 2


def _gene_entries(acc1: str, acc2: str, tax_id: int) -> list[dict[str, Any]]:
    gene_block = {"geneName": {"value": "katG"}, "orderedLocusNames": [{"value": "Rv1908c"}]}
    return [
        {
            "primaryAccession": acc1,
            "uniProtkbId": "G1_TEST",
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "sequence": {"value": "MKTAYIAKQR"},
            "organism": {"taxonId": tax_id},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
            "genes": [gene_block],
        },
        {
            "primaryAccession": acc2,
            "uniProtkbId": "G2_TEST",
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "sequence": {"value": "MKTAYIAKQS"},
            "organism": {"taxonId": tax_id},
            "entryAudit": {"entryVersion": 1, "sequenceVersion": 1},
            "genes": [gene_block],
        },
    ]


@pytest.mark.asyncio
async def test_import_creates_and_links_genes(import_uow: AsyncUnitOfWork) -> None:
    runner, protein_repo = _runner(
        import_uow,
        _meta("UP000000066", 99980),
        _gene_entries("P0DG01", "P0DG02", 99980),
        with_genes=True,
    )

    summary = await runner.run("UP000000066", auth=FakeAuth(role="admin"))

    assert summary.created == 2
    assert summary.genes_created == 1  # the shared gene is deduped within the chunk

    async with import_uow:
        grepo = SQLAlchemyGeneRepository(import_uow)
        gene = await grepo.find_by_source_record_id("uniprot", "99980:Rv1908c")
        assert gene is not None
        assert gene.primary_name == "katG"

        p1 = await protein_repo.find_by_accession("P0DG01")
        p2 = await protein_repo.find_by_accession("P0DG02")
        assert p1 is not None and p1.gene_id == gene.id
        assert p2 is not None and p2.gene_id == gene.id


def _meta_strain(
    proteome_id: str, species_tax: int, strain_tax: int, modified: str = "2026-01-01"
) -> dict[str, Any]:
    """UniProt proteome metadata for a *strain-level* proteome — the top-level
    taxon is the strain, and the species is the ``rank == "species"`` lineage node."""
    return {
        "id": proteome_id,
        "taxonomy": {"taxonId": strain_tax, "scientificName": "Testus microbus (strain XYZ)"},
        "strain": "ATCC 111 / XYZ",
        "genomeAssembly": {"assemblyId": "GCA_TEST.1"},
        "taxonLineage": [
            {"taxonId": 2, "scientificName": "Bacteria", "rank": "domain"},
            {"taxonId": species_tax, "scientificName": "Testus microbus", "rank": "species"},
        ],
        "proteomeType": "Reference proteome",
        "modified": modified,
    }


@pytest.mark.asyncio
async def test_import_resolves_species_and_strain(import_uow: AsyncUnitOfWork) -> None:
    auth = FakeAuth(role="admin")
    runner, protein_repo = _runner(
        import_uow,
        _meta_strain("UP000007710", 771000, 771001),
        _gene_entries("P0DX01", "P0DX02", 771001),
        with_genes=True,
    )

    summary = await runner.run("UP000007710", auth=auth)
    assert summary.created == 2

    async with import_uow:
        org_repo = SQLAlchemyOrganismRepository(import_uow)
        species = await org_repo.find_by_tax_id(771000)
        assert species is not None
        assert species.rank == "species"  # the species, correctly ranked
        # No separate Organism node is created for the strain taxon — the Strain
        # entity is the sole representation, carrying the taxon id as a scalar.
        assert await org_repo.find_by_tax_id(771001) is None

        strain_repo = SQLAlchemyStrainRepository(import_uow)
        strains = await strain_repo.find_by_species(auth.workspace_id, species.id)
        assert len(strains) == 1
        strain = strains[0]
        assert strain.assembly_acc == "GCA_TEST.1"
        assert strain.ncbi_taxon_id == 771001

        # The proteome itself links to the strain (regression: the importer used to
        # leave proteomes.strain_id NULL, so proteome filters over-fetched every strain).
        proteome_repo = SQLAlchemyProteomeRepository(import_uow)
        proteome = await proteome_repo.find_by_proteome_id("UP000007710")
        assert proteome is not None
        assert proteome.strain_id == strain.id
        assert proteome.organism_id == species.id

        # Proteins anchor to the SPECIES and carry the strain on strain_id.
        p1 = await protein_repo.find_by_accession("P0DX01")
        assert p1 is not None
        assert p1.organism_id == species.id
        assert p1.strain_id == strain.id

        # Genes anchor to the species too.
        grepo = SQLAlchemyGeneRepository(import_uow)
        gene = await grepo.find_by_source_record_id("uniprot", "771001:Rv1908c")
        assert gene is not None
        assert gene.organism_id == species.id


@pytest.mark.asyncio
async def test_import_species_level_proteome_creates_no_strain(
    import_uow: AsyncUnitOfWork,
) -> None:
    """A proteome whose taxon has no species ancestor in the lineage falls back to
    treating that taxon as the organism, and creates no strain."""
    auth = FakeAuth(role="admin")
    runner, protein_repo = _runner(
        import_uow, _meta("UP000007720", 772000), _entries("P0DX10", "P0DX11")
    )

    await runner.run("UP000007720", auth=auth)

    async with import_uow:
        org_repo = SQLAlchemyOrganismRepository(import_uow)
        org = await org_repo.find_by_tax_id(772000)
        assert org is not None
        strain_repo = SQLAlchemyStrainRepository(import_uow)
        assert await strain_repo.find_by_species(auth.workspace_id, org.id) == []
        p = await protein_repo.find_by_accession("P0DX10")
        assert p is not None and p.strain_id is None

        # No strain resolved → the proteome's strain_id stays NULL (e.g. human).
        proteome_repo = SQLAlchemyProteomeRepository(import_uow)
        proteome = await proteome_repo.find_by_proteome_id("UP000007720")
        assert proteome is not None and proteome.strain_id is None
