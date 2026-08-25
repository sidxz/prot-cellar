"""CLI: load the PARSNIP Mtb target list into a workspace.

    python -m protcellar.scripts.import_parsnip_targets \
        --file ~/workspace/parsnip/parsnip-ai/targets.json --workspace-id <uuid>

Input is PARSNIP's ``targets.json``: a list of
``{name, gene, locus, uniprot, chembl_id, chembl_type, protein_name, n_pdbs}``.
``name`` is PARSNIP's curated short form (``PptT``, ``Pks13``) and wins over the
derived default. Idempotent: an existing target with the same pref_name in the
workspace is skipped, never overwritten.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.target.create_target import (
    ComponentInput,
    CreateTarget,
    CreateTargetCommand,
)
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.gene_repository import (
    SQLAlchemyGeneRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.models import TargetModel
from protcellar.infrastructure.persistence.sqlalchemy.target.target_repository import (
    SQLAlchemyTargetRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from protcellar.scripts.import_proteome import _NoopDispatcher

# PARSNIP records one accession per target. parsnip-data's TBDA reference file gives
# GyrAB two loci (Rv0005 + Rv0006), so it is the one entry we promote to a real complex.
# Other multi-subunit names (ClpP1P2, TrpAB, CydAB, PrcBA) land as single_protein and are
# reported at the end — promote them by editing the target once the subunits are agreed.
EXTRA_SUBUNITS: dict[str, tuple[str, ...]] = {"GyrAB": ("P9WG45",)}


class _WorkspaceAuth:
    """Admin auth pinned to the workspace being seeded."""

    workspace_role = "admin"
    is_admin = True

    def __init__(self, workspace_id: uuid.UUID) -> None:
        self.workspace_id = workspace_id
        self.user_id = workspace_id

    def has_role(self, minimum_role: str) -> bool:
        return True


async def _sole_workspace_with_targets(uow: AsyncUnitOfWork) -> uuid.UUID:
    rows = (await uow.session.execute(select(TargetModel.workspace_id).distinct())).scalars().all()
    if len(rows) != 1:
        raise SystemExit(
            f"--workspace-id is required (found {len(rows)} workspaces owning targets)."
        )
    return rows[0]


async def run(*, file: Path, workspace_id: uuid.UUID | None, dry_run: bool) -> Counter[str]:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    counts: Counter[str] = Counter()
    entries = json.loads(file.read_text())
    try:
        # --- Pass 1: read-only. Existing names + every accession we might need. ---
        async with AsyncUnitOfWork(factory) as uow:
            if workspace_id is None:
                workspace_id = await _sole_workspace_with_targets(uow)
                print(f"workspace: {workspace_id} (auto-detected)")
            targets = SQLAlchemyTargetRepository(uow)
            existing = {
                t.pref_name for t in await targets.find_by_workspace(workspace_id, limit=100_000)
            }
            proteins = SQLAlchemyProteinRepository(uow)
            wanted = {
                a for e in entries for a in (e["uniprot"], *EXTRA_SUBUNITS.get(e["name"], ())) if a
            }
            found = {}
            for accession in sorted(wanted):
                protein = await proteins.find_by_accession(accession, workspace_id=workspace_id)
                if protein is not None:
                    found[accession] = (protein.id, protein.organism_id)

        # --- Pass 2: one transaction per target. ---
        auth = _WorkspaceAuth(workspace_id)
        for entry in entries:
            name = entry["name"]
            if name in existing:
                counts["skipped (exists)"] += 1
                continue
            accessions = [a for a in (entry["uniprot"], *EXTRA_SUBUNITS.get(name, ())) if a]
            missing = [a for a in accessions if a not in found]
            if not accessions or missing:
                print(f"  unresolved: {name} — {missing or 'no UniProt accession in PARSNIP'}")
                counts["unresolved"] += 1
                continue

            is_complex = len(accessions) > 1
            relationship = (
                ComponentRelationship.PROTEIN_SUBUNIT
                if is_complex
                else ComponentRelationship.SINGLE_PROTEIN
            )
            command = CreateTargetCommand(
                workspace_id=workspace_id,
                pref_name=name,  # PARSNIP's curated short form beats the derived default
                target_type=(
                    TargetType.PROTEIN_COMPLEX if is_complex else TargetType.SINGLE_PROTEIN
                ),
                components=tuple(
                    ComponentInput(protein_id=found[a][0], relationship=relationship)
                    for a in accessions
                ),
                organism_id=found[accessions[0]][1],
                chembl_id=entry.get("chembl_id"),
            )
            if dry_run:
                counts["would create"] += 1
                continue
            uow = AsyncUnitOfWork(factory)
            use_case = CreateTarget(
                uow,
                SQLAlchemyTargetRepository(uow),
                SQLAlchemyProteinRepository(uow),
                SQLAlchemyGeneRepository(uow),
                _NoopDispatcher(),
            )
            (await use_case(command, auth=auth)).unwrap()
            counts["created"] += 1
        return counts
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load PARSNIP targets into a workspace.")
    parser.add_argument("--file", type=Path, required=True, help="PARSNIP targets.json")
    parser.add_argument(
        "--workspace-id",
        type=uuid.UUID,
        default=None,
        help="Destination workspace (default: the sole workspace that already owns targets).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Resolve only, do not write.")
    args = parser.parse_args()
    counts = asyncio.run(
        run(file=args.file.expanduser(), workspace_id=args.workspace_id, dry_run=args.dry_run)
    )
    print(" ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "nothing to do")


if __name__ == "__main__":
    main()
