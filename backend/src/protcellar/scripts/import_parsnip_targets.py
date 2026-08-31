"""CLI: load the PARSNIP Mtb target list into a workspace.

    python -m protcellar.scripts.import_parsnip_targets \
        --file ~/workspace/parsnip/parsnip-ai/targets.json --workspace-id <uuid>

Input is PARSNIP's ``targets.json``: a list of
``{name, gene, locus, uniprot, chembl_id, chembl_type, protein_name, n_pdbs}``.
``name`` is PARSNIP's curated short form (``PptT``, ``Pks13``) and wins over the
derived default -- but it is normalized to protein case first, because the field is
hand-written and skipping ``default_pref_name`` also skips its casing rule.
Idempotent: an existing target with the same pref_name (case-insensitively) in the
workspace is skipped, never overwritten.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections import Counter
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from protcellar.application.target.create_target import (
    ComponentInput,
    CreateTargetCommand,
)
from protcellar.application.target.default_pref_name import protein_case
from protcellar.application.target.update_target import UpdateTarget, UpdateTargetCommand
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.target_repository import (
    SQLAlchemyTargetRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from protcellar.scripts._target_import import (
    NoopDispatcher,
    WorkspaceAuth,
    create_target,
    sole_workspace_with_targets,
)

# PARSNIP records one accession per target, but several of its names are multi-subunit
# complexes. The missing H37Rv subunit accessions, so those land as real complexes:
EXTRA_SUBUNITS: dict[str, tuple[str, ...]] = {
    "GyrAB": ("P9WG45",),  # + gyrB   Rv0005 (gyrA Rv0006 is PARSNIP's own accession)
    "ClpP1P2": ("P9WPC3",),  # + clpP2  Rv2460c
    "TrpAB": ("P9WFX9",),  # + trpB   Rv1612
    "CydAB": ("O06139",),  # + cydB   Rv1622c
    "PrcBA": ("P9WHU1",),  # + prcA   Rv2109c
    "PheST": ("P9WFU1",),  # + pheT   Rv1650
    "HsaA/B": ("P9WND9",),  # + hsaB   Rv3567c
}


async def _promote_to_complex(
    factory: async_sessionmaker[AsyncSession],
    workspace_id: uuid.UUID,
    target_id: uuid.UUID,
    protein_ids: list[uuid.UUID],
    auth: WorkspaceAuth,
) -> None:
    """Re-point a single_protein target at all of its subunits."""
    uow = AsyncUnitOfWork(factory)
    use_case = UpdateTarget(uow, SQLAlchemyTargetRepository(uow), NoopDispatcher())
    command = UpdateTargetCommand(
        workspace_id=workspace_id,
        target_id=target_id,
        target_type=TargetType.PROTEIN_COMPLEX,
        components=tuple(
            ComponentInput(protein_id=pid, relationship=ComponentRelationship.PROTEIN_SUBUNIT)
            for pid in protein_ids
        ),
    )
    (await use_case(command, auth=auth)).unwrap()


async def run(*, file: Path, workspace_id: uuid.UUID | None, dry_run: bool) -> Counter[str]:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    counts: Counter[str] = Counter()
    entries = json.loads(file.read_text())
    # PARSNIP's `name` is hand-written, and 14 of 82 were left in gene casing (`rho`,
    # `dnaA`) while the other 68 followed the convention — which is how the catalog ended
    # up with lowercase target names. Applying the same rule default_pref_name uses for
    # DERIVED names means an explicit name can no longer skip it. Normalize before pass 1:
    # EXTRA_SUBUNITS and the existing-name lookup are both keyed on this string.
    for entry in entries:
        entry["name"] = protein_case(entry["name"])
    try:
        # --- Pass 1: read-only. Existing names + every accession we might need. ---
        async with AsyncUnitOfWork(factory) as uow:
            if workspace_id is None:
                workspace_id = await sole_workspace_with_targets(uow)
                print(f"workspace: {workspace_id} (auto-detected)")
            targets = SQLAlchemyTargetRepository(uow)
            # Case-insensitive, matching import_daikon_targets: a workspace seeded before
            # names were normalized still holds `rho`, and an exact-match lookup would call
            # that a miss and create a second `Rho` beside it.
            existing = {
                t.pref_name.lower(): t
                for t in await targets.find_by_workspace(workspace_id, limit=100_000)
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
        auth = WorkspaceAuth(workspace_id)
        for entry in entries:
            name = entry["name"]
            accessions = [a for a in (entry["uniprot"], *EXTRA_SUBUNITS.get(name, ())) if a]
            missing = [a for a in accessions if a not in found]
            if not accessions or missing:
                print(f"  unresolved: {name} — {missing or 'no UniProt accession in PARSNIP'}")
                counts["unresolved"] += 1
                continue

            is_complex = len(accessions) > 1
            current = existing.get(name.lower())
            if current is not None:
                # Only ever *promote*: a target curators already built out is left alone.
                if not (is_complex and len(current.components) == 1):
                    counts["skipped (exists)"] += 1
                    continue
                if not dry_run:
                    await _promote_to_complex(
                        factory, workspace_id, current.id, [found[a][0] for a in accessions], auth
                    )
                counts["promoted to complex"] += 1
                continue

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
            await create_target(factory, command, auth)
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
