"""Orchestrates importing a full UniProt proteome into the catalog.

Ties the fetcher (network) + mapper (pure) + repositories (DB) + the
``BulkUpsertProteins`` use case together. This is infrastructure-level glue — it
touches the network and the database at once — so it lives beside the other
ingestion adapters rather than in the application layer.

Transaction strategy: organism + proteome setup, each protein chunk, and each
chunk's membership links run in their own short UoW transactions, so an import
of thousands of entries is resumable/idempotent at chunk granularity (the
underlying upsert keys on ``(source, source_record_id)`` + checksum).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from typing import Any, Protocol

from protcellar.application.auth import AuthContext
from protcellar.application.imports.progress_reporter import NoopProgressReporter, ProgressReporter
from protcellar.application.protein_catalog.bulk_upsert_genes import (
    BulkUpsertGenes,
    BulkUpsertGenesCommand,
    GeneImportRecord,
)
from protcellar.application.protein_catalog.bulk_upsert_proteins import (
    BulkUpsertProteins,
    BulkUpsertProteinsCommand,
    ProteinImportRecord,
)
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import OrganismSource, ProteomeType
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.domain.taxonomy.strain import Strain
from protcellar.infrastructure.ingestion.uniprot_mapper import (
    gene_key_for_entry,
    map_uniprot_entry,
    map_uniprot_genes,
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


def _species_from_lineage(lineage: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The ``rank == "species"`` node in a UniProt ``taxonLineage``, if present.

    UniProt's top-level proteome taxon is often a *strain* (e.g. 83332 = H37Rv);
    the species (e.g. 1773 = M. tuberculosis) lives in the lineage.
    """
    for node in lineage:
        if str(node.get("rank") or "").lower() == "species":
            return node
    return None


class ProteomeFetcher(Protocol):
    async def fetch_proteome(self, proteome_id: str) -> dict[str, Any]: ...

    def iter_entries(self, proteome_id: str) -> AsyncIterator[dict[str, Any]]: ...


@dataclass
class ImportSummary:
    proteome_id: str
    entries: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    genes_created: int = 0
    genes_updated: int = 0
    genes_skipped: int = 0
    members_linked: int = 0
    members_pruned: int = 0
    skipped_unchanged: bool = False


_NOOP_REPORTER: ProgressReporter = NoopProgressReporter()


class ProteomeImportRunner:
    def __init__(
        self,
        uow: AsyncUnitOfWork,
        client: ProteomeFetcher,
        bulk_upsert: BulkUpsertProteins,
        *,
        gene_bulk: BulkUpsertGenes | None = None,
        chunk_size: int = 500,
        reporter: ProgressReporter = _NOOP_REPORTER,
    ) -> None:
        self._uow = uow
        self._client = client
        self._bulk = bulk_upsert
        self._gene_bulk = gene_bulk
        self._chunk_size = chunk_size
        self._reporter = reporter

    async def run(
        self,
        proteome_id: str,
        *,
        dry_run: bool = False,
        limit: int | None = None,
        force: bool = False,
        auth: AuthContext | None = None,
    ) -> ImportSummary:
        meta = await self._client.fetch_proteome(proteome_id)
        source_release = str(meta.get("modified") or "")
        await self._reporter.source_version(source_release or None)
        if not force and not dry_run and await self._is_unchanged(proteome_id, meta):
            return ImportSummary(proteome_id=proteome_id, skipped_unchanged=True)
        organism_id, strain_id = await self._resolve_taxa(meta, dry_run=dry_run, auth=auth)
        proteome_db_id = await self._ensure_proteome(
            proteome_id, organism_id, strain_id, meta, dry_run=dry_run
        )

        tax_id = (meta.get("taxonomy") or {}).get("taxonId")

        await self._reporter.phase("streaming entries")
        total: int | None = meta.get("proteinCount") or None
        if total is not None:
            await self._reporter.advance(0, total)

        summary = ImportSummary(proteome_id=proteome_id)
        seen: set[str] = set()
        chunk: list[dict[str, Any]] = []
        async for entry in self._client.iter_entries(proteome_id):
            chunk.append(entry)
            seen.add(entry["primaryAccession"])
            summary.entries += 1
            if len(chunk) >= self._chunk_size:
                await self._load_chunk(
                    chunk,
                    proteome_db_id,
                    organism_id,
                    strain_id,
                    tax_id,
                    source_release,
                    summary,
                    dry_run=dry_run,
                    auth=auth,
                )
                chunk = []
                await self._reporter.advance(summary.entries, total)
            if limit is not None and summary.entries >= limit:
                break
        if chunk:
            await self._load_chunk(
                chunk,
                proteome_db_id,
                organism_id,
                strain_id,
                tax_id,
                source_release,
                summary,
                dry_run=dry_run,
                auth=auth,
            )
            await self._reporter.advance(summary.entries, total)
        if not dry_run and limit is None:
            await self._reporter.phase("linking membership")
            await self._reconcile_membership(proteome_db_id, seen, summary)
        return summary

    async def _resolve_taxa(
        self, meta: dict[str, Any], *, dry_run: bool, auth: AuthContext | None
    ) -> tuple[uuid.UUID, uuid.UUID | None]:
        """Resolve the organism (a *species* Organism) and, for strain-level
        proteomes, a Strain anchored to it.

        UniProt's top-level proteome ``taxonomy`` is frequently a *strain* taxon
        (e.g. 83332 = M. tuberculosis H37Rv); the species (e.g. 1773) is the
        ``rank == "species"`` node in ``taxonLineage``. Genes and proteins anchor
        to the species (``organism_id``); strain-specificity is carried on the
        protein via ``strain_id``.

        Returns ``(organism_id, strain_id)``. ``strain_id`` is ``None`` when the
        proteome taxon is itself a species, the lineage lacks a species node, or
        there is no workspace (auth) to scope the workspace-owned Strain under.
        """
        tax = meta.get("taxonomy") or {}
        top_tax_id = tax.get("taxonId")
        species = _species_from_lineage(meta.get("taxonLineage") or [])

        if species is None:
            # No species ancestor in the lineage — treat the proteome taxon as the
            # organism (legacy behaviour); create no strain.
            organism_id = await self._find_or_create_organism(
                tax_id=top_tax_id,
                rank="species",
                scientific_name=tax.get("scientificName"),
                dry_run=dry_run,
            )
            return organism_id, None

        species_id = await self._find_or_create_organism(
            tax_id=species.get("taxonId"),
            rank="species",
            scientific_name=species.get("scientificName"),
            dry_run=dry_run,
        )

        if top_tax_id is None or top_tax_id == species.get("taxonId") or auth is None:
            return species_id, None

        # Strain-level: register a workspace-owned Strain anchored to the species,
        # carrying the strain's NCBI taxon id as provenance. The strain is the sole
        # representation of the strain — we do NOT create a separate Organism node
        # for the strain taxon (the species Organism is the only taxonomy anchor).
        strain_id = await self._ensure_strain(
            meta,
            species_id=species_id,
            ncbi_taxon_id=top_tax_id,
            workspace_id=auth.workspace_id,
            dry_run=dry_run,
        )
        return species_id, strain_id

    async def _find_or_create_organism(
        self,
        *,
        tax_id: int | None,
        rank: str,
        scientific_name: str | None,
        parent_id: uuid.UUID | None = None,
        dry_run: bool,
    ) -> uuid.UUID:
        async with self._uow:
            repo = SQLAlchemyOrganismRepository(self._uow)
            if tax_id is not None:
                existing = await repo.find_by_tax_id(tax_id)
                if existing is not None:
                    # Correct a previously mis-ranked node — e.g. a strain taxon an
                    # older import created as rank "species".
                    changes: dict[str, Any] = {}
                    if existing.rank != rank:
                        changes["rank"] = rank
                    if parent_id is not None and existing.parent_id != parent_id:
                        changes["parent_id"] = parent_id
                    if changes and not dry_run:
                        existing.update(**changes)
                        await repo.save(existing)
                        await self._uow.commit()
                    return existing.id
            # Ingestion always writes the shared catalog — never the triggering
            # caller's own workspace, regardless of who started the import.
            organism = Organism.create(
                workspace_id=SHARED_WORKSPACE_ID,
                ncbi_tax_id=tax_id,
                rank=rank,
                scientific_name=scientific_name or (f"taxon {tax_id}" if tax_id else "unknown"),
                source=OrganismSource.LOCAL,
                parent_id=parent_id,
            )
            if not dry_run:
                await repo.save(organism)
                await self._uow.commit()
            return organism.id

    async def _ensure_strain(
        self,
        meta: dict[str, Any],
        *,
        species_id: uuid.UUID,
        ncbi_taxon_id: int | None,
        workspace_id: uuid.UUID,
        dry_run: bool,
    ) -> uuid.UUID:
        tax = meta.get("taxonomy") or {}
        label = meta.get("strain") or tax.get("scientificName") or "unknown strain"
        assembly = (meta.get("genomeAssembly") or {}).get("assemblyId")
        async with self._uow:
            repo = SQLAlchemyStrainRepository(self._uow)
            for existing in await repo.find_by_species(workspace_id, species_id):
                if (ncbi_taxon_id is not None and existing.ncbi_taxon_id == ncbi_taxon_id) or (
                    assembly is not None and existing.assembly_acc == assembly
                ):
                    return existing.id
            strain = Strain.create(
                workspace_id=workspace_id,
                species_organism_id=species_id,
                ncbi_taxon_id=ncbi_taxon_id,
                name=label,
                isolate=meta.get("strain"),
                assembly_acc=assembly,
            )
            if not dry_run:
                await repo.save(strain)
                await self._uow.commit()
            return strain.id

    async def _ensure_proteome(
        self,
        proteome_id: str,
        organism_id: uuid.UUID,
        strain_id: uuid.UUID | None,
        meta: dict[str, Any],
        *,
        dry_run: bool,
    ) -> uuid.UUID:
        is_reference = "reference" in str(meta.get("proteomeType") or "reference").lower()
        async with self._uow:
            repo = SQLAlchemyProteomeRepository(self._uow)
            existing = await repo.find_by_proteome_id(proteome_id)
            if existing is not None:
                fields: dict[str, Any] = {}
                if existing.source_version != meta.get("modified"):
                    fields["source_version"] = meta.get("modified")
                if existing.strain_id is None and strain_id is not None:
                    fields["strain_id"] = strain_id  # backfill rows imported before strain linkage
                if not dry_run and fields:
                    existing.update(**fields)
                    await repo.save(existing)
                    await self._uow.commit()
                return existing.id
            # Same ingestion-tier rule as _find_or_create_organism above.
            proteome = Proteome.create(
                workspace_id=SHARED_WORKSPACE_ID,
                uniprot_proteome_id=proteome_id,
                organism_id=organism_id,
                strain_id=strain_id,
                proteome_type=ProteomeType.REFERENCE if is_reference else ProteomeType.REDUNDANT,
                is_reference=is_reference,
                source_version=meta.get("modified"),
            )
            if not dry_run:
                await repo.save(proteome)
                await self._uow.commit()
            return proteome.id

    async def _is_unchanged(self, proteome_id: str, meta: dict[str, Any]) -> bool:
        async with self._uow:
            existing = await SQLAlchemyProteomeRepository(self._uow).find_by_proteome_id(
                proteome_id
            )
            return existing is not None and existing.source_version == meta.get("modified")

    async def _reconcile_membership(
        self, proteome_db_id: uuid.UUID, seen: set[str], summary: ImportSummary
    ) -> None:
        async with self._uow:
            repo = SQLAlchemyProteomeRepository(self._uow)
            for protein_id, accession in await repo.list_members(proteome_db_id):
                if accession not in seen:
                    await repo.remove_protein(proteome_db_id, protein_id)
                    summary.members_pruned += 1
            await self._uow.commit()

    async def _load_chunk(
        self,
        entries: list[dict[str, Any]],
        proteome_db_id: uuid.UUID,
        organism_id: uuid.UUID,
        strain_id: uuid.UUID | None,
        tax_id: Any,
        source_release: str,
        summary: ImportSummary,
        *,
        dry_run: bool,
        auth: AuthContext | None,
    ) -> None:
        gene_id_by_key = await self._upsert_genes(
            entries,
            organism_id,
            strain_id,
            tax_id,
            source_release,
            summary,
            dry_run=dry_run,
            auth=auth,
        )

        records: list[ProteinImportRecord] = []
        for entry in entries:
            rec = map_uniprot_entry(
                entry, organism_id=organism_id, source="uniprot", source_release=source_release
            )
            if strain_id is not None:
                rec = replace(rec, strain_id=strain_id)
            if self._gene_bulk is not None:
                key = gene_key_for_entry(entry, tax_id=tax_id)
                gid = gene_id_by_key.get(key) if key else None
                if gid is not None:
                    rec = replace(rec, gene_id=gid)
            records.append(rec)

        command = BulkUpsertProteinsCommand(records=tuple(records), dry_run=dry_run)
        items = (await self._bulk(command, auth=auth)).unwrap()
        for item in items:
            if item.status == "created":
                summary.created += 1
            elif item.status == "updated":
                summary.updated += 1
            elif item.status == "skipped":
                summary.skipped += 1
            else:
                summary.failed += 1
        if dry_run:
            return
        async with self._uow:
            proteome_repo = SQLAlchemyProteomeRepository(self._uow)
            for item in items:
                if item.id and item.status in ("created", "updated", "skipped"):
                    await proteome_repo.add_protein(proteome_db_id, uuid.UUID(item.id))
                    summary.members_linked += 1
            await self._uow.commit()

    async def _upsert_genes(
        self,
        entries: list[dict[str, Any]],
        organism_id: uuid.UUID,
        strain_id: uuid.UUID | None,
        tax_id: Any,
        source_release: str,
        summary: ImportSummary,
        *,
        dry_run: bool,
        auth: AuthContext | None,
    ) -> dict[str, uuid.UUID]:
        """Upsert all genes in the chunk (deduped by key); return {source_record_id: gene_id}."""
        if self._gene_bulk is None:
            return {}
        by_key: dict[str, GeneImportRecord] = {}
        for entry in entries:
            for rec in map_uniprot_genes(
                entry,
                organism_id=organism_id,
                tax_id=tax_id,
                source="uniprot",
                source_release=source_release,
            ):
                by_key.setdefault(rec.source_record_id, rec)
        if not by_key:
            return {}
        gene_records = list(by_key.values())
        if strain_id is not None:
            gene_records = [replace(r, strain_id=strain_id) for r in gene_records]
        command = BulkUpsertGenesCommand(records=tuple(gene_records), dry_run=dry_run)
        items = (await self._gene_bulk(command, auth=auth)).unwrap()
        # Correlate results to input records by ItemResult.index (not positional zip),
        # so this stays correct even if BulkUpsertGenes ever reorders its results.
        items_by_index = {item.index: item for item in items}
        gene_id_by_key: dict[str, uuid.UUID] = {}
        for idx, rec in enumerate(gene_records):
            item = items_by_index[idx]
            if item.id:
                gene_id_by_key[rec.source_record_id] = uuid.UUID(item.id)
            if item.status == "created":
                summary.genes_created += 1
            elif item.status == "updated":
                summary.genes_updated += 1
            elif item.status == "skipped":
                summary.genes_skipped += 1
        return gene_id_by_key
