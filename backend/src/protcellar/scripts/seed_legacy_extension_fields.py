"""Declare the extension fields a legacy Gene-service import needs somewhere to land.

The eight target-biology tables model the fields this service curates. A legacy
corpus carries a tail of per-method values those columns deliberately don't model —
credible bounds, percentile bins, knockdown estimates, free-text construct
descriptions. Each record's ``extensions`` JSONB bag exists for exactly that, and a
value in it is unreadable until a declaration gives it a label, a type and a place in
the forms and tables. This script writes those declarations.

Provenance is **not** here. ``reference``/``pmid`` land on each record's own
``pmid``/``dataset`` fields; ``url``, ``note``, ``contributor`` and ``observed_on`` are
read and discarded by the current (workbook) import pipeline — the import preview names
them in ``ignored_columns``, not the shared ``provenance`` value object. Restating any
of the five as an extension field would be a second, unvalidated way to say the same
thing.

One kind gets nothing, deliberately:

* **crispri_strain** — the legacy collection is empty, so there is no tail to host.

Idempotent: a declaration whose ``(kind, name)`` already exists is left exactly as it
is, edits included. Re-running only adds what is missing, so this is safe to run
against a workspace an admin has already been curating.

Usage::

    uv run python -m protcellar.scripts.seed_legacy_extension_fields <workspace-uuid>

Requires ``DATABASE_URL`` in the env (or ``.env``).
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)
from protcellar.infrastructure.persistence.settings import DatabaseSettings
from protcellar.infrastructure.persistence.sqlalchemy.workspace_config.extension_field_def_repository import (  # noqa: E501
    SQLAlchemyExtensionFieldDefRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork

_T = ExtensionFieldType

# (name, label, type, options, show_in_table). Order is the position order.
#
# On typing: the legacy store keeps every one of these as a string, so the type here
# is a judgement about what the value *means*, and the migration coerces. Where the
# string carries something a number would throw away — a range, a comparator, a unit —
# the declaration stays a string and the parsed half goes in the core column instead.
_Decl = tuple[str, str, ExtensionFieldType, list[str] | None, bool]

_FIELDS: dict[str, list[_Decl]] = {
    # Core columns already hold condition, method and the 0-1 score. What is left is
    # the CRISPRi-VI statistical tail, ~2,900 of 3,000 records deep.
    "vulnerability": [
        # The source's VulnerabilityIndex. It cannot go in the core
        # ``vulnerability_score`` column, which the aggregate constrains to [0, 1]
        # while this ranges roughly -21..0.8 — a different quantity wearing a
        # similar name.
        ("vulnerability_index", "Vulnerability index", _T.NUMBER, None, True),
        ("vi_lower_bound", "VI lower bound", _T.NUMBER, None, False),
        ("vi_upper_bound", "VI upper bound", _T.NUMBER, None, False),
        # "5.0" in the source, but it is a 1-5 percentile bucket, not a measurement.
        ("vi_bin", "VI bin", _T.INTEGER, None, True),
        # "7%" — a numeric with a unit suffix, exactly like purity_reported and
        # resolution_reported below. An earlier draft declared this INTEGER on the
        # theory that the "%" is uniform and therefore carries nothing; live QA
        # settled it the other way. The importer will not strip a suffix for one
        # named field, and asking the export to do it for this column alone while
        # copying every other faithfully is more moving parts than storing what the
        # source actually says.
        ("pct_of_max", "Percent of max", _T.STRING, None, False),
        ("rank", "Rank", _T.NUMBER, None, False),
        ("score", "Score", _T.NUMBER, None, False),
        ("certain", "Certain", _T.BOOLEAN, None, False),
        (
            "high_confidence_call",
            "High-confidence call",
            _T.BOOLEAN,
            None,
            True,
        ),
        # Essentiality calls carried alongside the vulnerability row rather than as
        # essentiality records of their own. Left as declared here rather than
        # promoted into essentiality_records — that is a migration decision, not a
        # schema one, and it wants its own pass.
        (
            "tnseq_ess",
            "TnSeq essentiality",
            _T.ENUM,
            ["Essential", "NonEssential", "Uncertain", "Unknown"],
            False,
        ),
        (
            "crispr_ess",
            "CRISPRi essentiality",
            _T.ENUM,
            ["Essential", "NonEssential"],
            False,
        ),
    ],
    # Classification, method and reference map onto core columns. `condition` does
    # not: the core column is varchar(128) and holds a short label ("7H9",
    # "cholesterol"), while the source stores a full methods paragraph there —
    # 187 characters at its longest, and over the cap on all 4,014 rows. An earlier
    # draft of this file claimed essentiality needed no extension fields at all;
    # a real import proved otherwise.
    "essentiality": [
        ("condition_detail", "Condition detail", _T.TEXT, None, False),
    ],
    # growth_defect, its severity, condition, method and the strain link are core.
    "hypomorph": [
        (
            "estimated_knockdown_relative_to_wt",
            "Estimated knockdown vs WT",
            # "~85%", "ND", "TBD", "100%" in one column — approximate, absent and
            # measured values share it, and a number would have to discard two of the three.
            _T.STRING,
            None,
            True,
        ),
        ("knockdown_level", "Knockdown level", _T.ENUM, ["Known", "Unknown"], False),
        ("estimate_based_on", "Estimate based on", _T.ENUM, ["RNA", "Protein", "N/A"], False),
        (
            "suitable_for_screening",
            "Suitable for screening",
            # Tri-state on purpose: TBD is a curation state, and a boolean would
            # collapse it into No.
            _T.ENUM,
            ["Yes", "No", "TBD"],
            True,
        ),
        (
            "selectively_sensitizes_to_on_target_inhibitors",
            "Selectively sensitizes to on-target inhibitors",
            _T.ENUM,
            ["Yes", "No", "TBD"],
            False,
        ),
        # Empty across all 195 legacy records, declared so an import does not silently
        # drop a column that the source schema says exists.
        ("phenotype", "Phenotype", _T.STRING, None, False),
        # The source's free-text note, and the only place the knockdown strain is
        # actually recorded ("Gene name : AftB_03", alongside the background it was
        # made in). Not `note`: that is a reserved provenance column, which the
        # importer discards and — decisively — excludes from the identity used to
        # deduplicate rows. Carried here instead, the strain identity survives and
        # 195 source rows stay 195 records rather than collapsing to 133.
        ("construct_note", "Construct note", _T.TEXT, None, False),
    ],
    # mutation, compound, parent strain, protein coordinate and method are core.
    "resistance_mutation": [
        ("isolate", "Isolate", _T.STRING, None, False),
        # "20x", "32", "8" — the core mic_shift double takes the parsed number; this
        # keeps what was actually written down.
        ("mic_shift_reported", "MIC shift as reported", _T.STRING, None, False),
    ],
    # status, expression host, purity, condition and method are core.
    "protein_production": [
        # Paragraph-length construct descriptions: tag, vector, host, truncation.
        ("production", "Production", _T.TEXT, None, False),
        # ">90%", "90-95%", ">92%" — the comparator and the range are the point.
        ("purity_reported", "Purity as reported", _T.STRING, None, False),
        ("date_produced", "Date produced", _T.DATE, None, True),
    ],
    # activity measured, readout, throughput, condition and method are core.
    "protein_activity_assay": [
        ("assay", "Assay", _T.TEXT, None, False),
    ],
    # method, resolution, ligands and the two published/experimental flags are core.
    "unpublished_structure": [
        ("organization", "Organization", _T.STRING, None, True),
        # "1.9-2.8 Angstroms", "2.1 Angstrom", "2.68" — a range in the same column as
        # a scalar, so the core resolution double cannot hold every row.
        ("resolution_reported", "Resolution as reported", _T.STRING, None, False),
        # "Apo", "SO4 and PEG bound", a raw SMILES string — ligand text the core
        # `ligand_ids` (chem-cellar UUIDs only) cannot hold. The workbook parser
        # routes it here instead of dropping it, which is what full-row
        # deduplication needs to keep otherwise-identical structures apart.
        ("ligand_reported", "Ligand as reported", _T.STRING, None, False),
    ],
}


async def _main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: python -m protcellar.scripts.seed_legacy_extension_fields <workspace-uuid>\n"
            "Declarations are per-workspace; there is no default, so that a mistyped "
            "command cannot seed the wrong tenant."
        )
    workspace_id = uuid.UUID(sys.argv[1])

    settings = DatabaseSettings()  # type: ignore[call-arg]
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uow = AsyncUnitOfWork(factory)
    added, kept = 0, 0
    try:
        async with uow:
            repo = SQLAlchemyExtensionFieldDefRepository(uow)
            for kind, decls in _FIELDS.items():
                for position, (name, label, field_type, options, show_in_table) in enumerate(
                    decls
                ):
                    if await repo.find_by_name(workspace_id, kind, name) is not None:
                        kept += 1
                        continue
                    await repo.save(
                        ExtensionFieldDef.create(
                            workspace_id=workspace_id,
                            kind=kind,
                            name=name,
                            label=label,
                            field_type=field_type,
                            options=options,
                            position=position,
                            show_in_table=show_in_table,
                        )
                    )
                    added += 1
            await uow.commit()
        print(f"workspace {workspace_id}: declared {added}, left {kept} already-present untouched")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
