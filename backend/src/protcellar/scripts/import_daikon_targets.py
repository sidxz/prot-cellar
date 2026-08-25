"""CLI: load DAIKON's legacy target list into a workspace.

    python -m protcellar.scripts.import_daikon_targets --file daikon-targets.json \
        --workspace-id <uuid>

Input is a JSON array flattened from DAIKON's ``Target.Targets`` collection
(mongodump archive of the Azure prod cluster)::

    [{"name": "MenG", "target_type": "protein", "associated_genes": ["Rv0558"],
      "bucket": "2b", "is_deleted": false, "is_archived": false}]

Components resolve by H37Rv locus tag (``Rv0558``) against the gene catalog, then
to that gene's protein. DAIKON's own ``target_type`` is NOT trusted — it is
derived there as ``len(associated_genes) > 1``, so it calls a two-protein dual
target a complex and a single-gene domain a protein. We re-derive it (see
``_derive_type``) and report the entries a human should look at.

DAIKON's buckets and 14 scorecard axes are not imported: Target has no field for
them. Idempotent: an existing target with the same pref_name is skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.application.target.create_target import ComponentInput, CreateTargetCommand
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models import (
    GeneModel,
    ProteinModel,
)
from protcellar.infrastructure.persistence.sqlalchemy.target.target_repository import (
    SQLAlchemyTargetRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from protcellar.scripts._target_import import (
    WorkspaceAuth,
    create_target,
    sole_workspace_with_targets,
)

_DOMAIN_NAME = re.compile(r"\bdomain\b", re.IGNORECASE)


def _derive_type(name: str, n_components: int) -> TargetType:
    """DAIKON stores `len(genes) > 1`, which is not biology. Re-derive.

    A name saying "domain" (``Pks13TE Domain``) is a domain when it resolved to a
    single protein. Everything else falls back to the component count — which
    still mislabels a multi-protein dual target as a complex, so those are
    reported for a human rather than guessed at.
    """
    if n_components == 1 and _DOMAIN_NAME.search(name):
        return TargetType.DOMAIN
    return TargetType.SINGLE_PROTEIN if n_components == 1 else TargetType.PROTEIN_COMPLEX


async def _resolve_loci(uow: AsyncUnitOfWork, loci: set[str]) -> dict[str, tuple[uuid.UUID, Any]]:
    """Map each H37Rv locus tag to (protein_id, organism_id).

    Reviewed entries win when a gene carries more than one protein; ties break on
    the accession so a re-run resolves identically.
    """
    rows = (
        await uow.session.execute(
            select(
                GeneModel.ordered_locus_names,
                ProteinModel.id,
                ProteinModel.organism_id,
                ProteinModel.is_reviewed,
                ProteinModel.primary_accession,
            )
            .join(ProteinModel, ProteinModel.gene_id == GeneModel.id)
            .where(GeneModel.ordered_locus_names.overlap(list(loci)))
        )
    ).all()
    best: dict[str, tuple[bool, str, uuid.UUID, Any]] = {}
    for locus_names, protein_id, organism_id, is_reviewed, accession in rows:
        for locus in locus_names or []:
            if locus not in loci:
                continue
            candidate = (bool(is_reviewed), accession, protein_id, organism_id)
            current = best.get(locus)
            # (reviewed desc, accession asc) — deterministic across runs.
            if (
                current is None
                or (not current[0] and candidate[0])
                or (current[0] == candidate[0] and candidate[1] < current[1])
            ):
                best[locus] = candidate
    return {locus: (v[2], v[3]) for locus, v in best.items()}


async def run(*, file: Path, workspace_id: uuid.UUID | None, dry_run: bool) -> Counter[str]:
    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    counts: Counter[str] = Counter()
    entries = json.loads(file.read_text())
    review: list[str] = []
    try:
        async with AsyncUnitOfWork(factory) as uow:
            if workspace_id is None:
                workspace_id = await sole_workspace_with_targets(uow)
                print(f"workspace: {workspace_id} (auto-detected)")
            targets = SQLAlchemyTargetRepository(uow)
            stored = await targets.find_by_workspace(workspace_id, limit=100_000)
            # Case-insensitive: PARSNIP names by lowercase gene (`rho`, `fum`), DAIKON
            # capitalises the same target (`Rho`, `Fum`). Same target, not two.
            existing = {t.pref_name.lower() for t in stored}
            # Same proteins under a different trade name = a duplicate worth reporting.
            # DAIKON carries its own twins (ATP-Synthase/ATP-Synthesis, PheRS/PheST) and
            # renames PARSNIP entries (HsaAB vs HsaA/B), so this is reported, not merged:
            # dropping a record the import was asked to load is the curator's call.
            by_components: dict[frozenset[uuid.UUID], list[str]] = {}
            for t in stored:
                by_components.setdefault(frozenset(c.protein_id for c in t.components), []).append(
                    t.pref_name
                )
            wanted = {locus for e in entries for locus in e["associated_genes"]}
            resolved = await _resolve_loci(uow, wanted)
        print(f"loci: {len(resolved)}/{len(wanted)} resolved to proteins")

        auth = WorkspaceAuth(workspace_id)
        for entry in entries:
            name = entry["name"]
            if entry.get("is_deleted"):
                counts["skipped (deleted in DAIKON)"] += 1
                continue
            if name.lower() in existing:
                counts["skipped (exists)"] += 1
                continue
            existing.add(name.lower())
            loci = entry["associated_genes"]
            components = [resolved[locus] for locus in loci if locus in resolved]
            missing = [locus for locus in loci if locus not in resolved]
            if not components:
                print(f"  unresolved: {name} — {loci or 'no associated genes'}")
                counts["unresolved"] += 1
                continue
            if missing:
                print(f"  partial: {name} — {len(components)}/{len(loci)} loci, missing {missing}")
                counts["created (partial)"] += 1

            target_type = _derive_type(name, len(components))
            if target_type is not TargetType.DOMAIN:
                # A domain shares its parent's protein by design — not a duplicate.
                by_components.setdefault(frozenset(pid for pid, _ in components), []).append(name)
            if target_type is TargetType.PROTEIN_COMPLEX:
                review.append(f"{name} ({len(components)} proteins)")
            relationship = (
                ComponentRelationship.PROTEIN_SUBUNIT
                if target_type is TargetType.PROTEIN_COMPLEX
                else ComponentRelationship.SINGLE_PROTEIN
            )
            command = CreateTargetCommand(
                workspace_id=workspace_id,
                pref_name=name,  # DAIKON's curated trade name beats the derived default
                target_type=target_type,
                components=tuple(
                    ComponentInput(protein_id=pid, relationship=relationship)
                    for pid, _ in components
                ),
                organism_id=components[0][1],
            )
            if dry_run:
                counts[f"would create ({target_type.value})"] += 1
                continue
            await create_target(factory, command, auth)
            counts[f"created ({target_type.value})"] += 1
        duplicates = [names for names in by_components.values() if len(names) > 1]
        if duplicates:
            print(
                "\nsame protein set under more than one name — merge or delete in the UI:\n  "
                + "\n  ".join(" == ".join(sorted(n)) for n in sorted(duplicates))
            )
        if review:
            print(
                "\nmulti-protein — typed protein_complex from the gene count; check the ones that "
                "are really a family or a dual target:\n  " + "\n  ".join(sorted(review))
            )
        return counts
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load DAIKON legacy targets into a workspace.")
    parser.add_argument("--file", type=Path, required=True, help="Flattened DAIKON targets JSON")
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
