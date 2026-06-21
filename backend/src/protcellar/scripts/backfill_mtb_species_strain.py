"""One-off backfill: split the M. tuberculosis "organism" into species + strain.

Older imports created a single Organism from the proteome's top-level taxon
(83332 = M. tuberculosis H37Rv) mislabelled ``rank="species"``, left the
``strains`` table empty, and never set ``protein.strain_id``. The importer is
now fixed (see ``infrastructure.ingestion.import_runner._resolve_taxa``), but
that only affects future imports — already-loaded rows need this correction.

This script is idempotent and non-destructive (it preserves all UUIDs):

  1. find-or-create the species Organism (1773, "Mycobacterium tuberculosis");
  2. relabel the 83332 node to ``rank="strain"`` with ``parent_id`` = species;
  3. find-or-create a global-workspace Strain (H37Rv) anchored to the species;
  4. repoint every gene/protein from the 83332 node to the species, and set
     ``protein.strain_id`` to the new strain.

Usage::

    python -m protcellar.scripts.backfill_mtb_species_strain [--dry-run]

The taxonomy constants below were verified against the live UniProt proteome
record for ``UP000001584`` (``rest.uniprot.org/proteomes/UP000001584``).
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import OrganismSource
from protcellar.domain.taxonomy.organism import Organism
from protcellar.domain.taxonomy.strain import Strain
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import (
    GeneModel,
    ProteinModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.strain_repository import (
    SQLAlchemyStrainRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

# ── Verified UniProt UP000001584 taxonomy ────────────────────────────────────
SPECIES_TAX = 1773
SPECIES_NAME = "Mycobacterium tuberculosis"
STRAIN_TAX = 83332
STRAIN_NAME = "ATCC 25618 / H37Rv"
ASSEMBLY_ACC = "GCA_000195955.2"


async def backfill(*, dry_run: bool = False) -> None:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    try:
        # 1. Locate the mislabelled strain-as-species node.
        async with uow:
            org_repo = SQLAlchemyOrganismRepository(uow)
            node = await org_repo.find_by_tax_id(STRAIN_TAX)
            if node is None:
                print(f"No organism with tax id {STRAIN_TAX} — nothing to backfill.")
                return
            old_node_id = node.id

        # 2. Species organism (find-or-create).
        async with uow:
            org_repo = SQLAlchemyOrganismRepository(uow)
            species = await org_repo.find_by_tax_id(SPECIES_TAX)
            if species is None:
                species = Organism.create(
                    ncbi_tax_id=SPECIES_TAX,
                    rank="species",
                    scientific_name=SPECIES_NAME,
                    source=OrganismSource.LOCAL,
                )
                if not dry_run:
                    await org_repo.save(species)
                    await uow.commit()
                print(f"Created species organism {SPECIES_NAME} ({SPECIES_TAX}).")
            else:
                print(f"Species organism {SPECIES_NAME} ({SPECIES_TAX}) already exists.")
            species_id = species.id

        # 3. Relabel the 83332 node → rank "strain", parent = species.
        async with uow:
            org_repo = SQLAlchemyOrganismRepository(uow)
            node = await org_repo.find_by_tax_id(STRAIN_TAX)
            assert node is not None
            if node.rank != "strain" or node.parent_id != species_id:
                node.update(rank="strain", parent_id=species_id)
                if not dry_run:
                    await org_repo.save(node)
                    await uow.commit()
                print(f"Relabelled organism {STRAIN_TAX} to rank 'strain' (parent={SPECIES_TAX}).")
            else:
                print(f"Organism {STRAIN_TAX} already rank 'strain'.")
            strain_org_id = node.id

        # 4. Strain (H37Rv) under the global workspace (find-or-create).
        async with uow:
            strain_repo = SQLAlchemyStrainRepository(uow)
            existing = [
                s
                for s in await strain_repo.find_by_species(GLOBAL_WORKSPACE_ID, species_id)
                if s.strain_organism_id == strain_org_id
            ]
            if existing:
                strain_id = existing[0].id
                print(f"Strain '{STRAIN_NAME}' already exists.")
            else:
                strain = Strain.create(
                    workspace_id=GLOBAL_WORKSPACE_ID,
                    species_organism_id=species_id,
                    strain_organism_id=strain_org_id,
                    name=STRAIN_NAME,
                    isolate=STRAIN_NAME,
                    assembly_acc=ASSEMBLY_ACC,
                )
                if not dry_run:
                    await strain_repo.save(strain)
                    await uow.commit()
                strain_id = strain.id
                print(f"Created strain '{STRAIN_NAME}' (assembly {ASSEMBLY_ACC}).")

        # 5. Repoint genes + proteins from the old node to the species.
        async with uow:
            if dry_run:
                # Can't UPDATE to a species row we never committed — just count.
                genes_moved = (
                    await uow.session.execute(
                        select(func.count())
                        .select_from(GeneModel)
                        .where(GeneModel.organism_id == old_node_id)
                    )
                ).scalar_one()
                proteins_moved = (
                    await uow.session.execute(
                        select(func.count())
                        .select_from(ProteinModel)
                        .where(ProteinModel.organism_id == old_node_id)
                    )
                ).scalar_one()
                print(
                    f"Would repoint {genes_moved} genes and {proteins_moved} proteins "
                    f"to species {SPECIES_TAX}, setting strain_id on those proteins."
                )
            else:
                genes_moved = (
                    await uow.session.execute(
                        update(GeneModel)
                        .where(GeneModel.organism_id == old_node_id)
                        .values(organism_id=species_id)
                    )
                ).rowcount
                proteins_moved = (
                    await uow.session.execute(
                        update(ProteinModel)
                        .where(ProteinModel.organism_id == old_node_id)
                        .values(organism_id=species_id, strain_id=strain_id)
                    )
                ).rowcount
                await uow.commit()
                print(
                    f"Repointed {genes_moved} genes and {proteins_moved} proteins "
                    f"to species {SPECIES_TAX}; set strain_id on those proteins."
                )

        print("Dry run — no changes committed." if dry_run else "Backfill complete.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill M. tuberculosis species/strain split.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report what would change, persist nothing"
    )
    args = parser.parse_args()
    asyncio.run(backfill(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
