"""Parse a target-biology workbook into one import plan per recognised sheet.

Pure: bytes in, dataclasses out. No database, no network, no I/O — that purity is what
makes the collapse numbers below testable, and what Task 5's worker composes over.

**One workbook, one sheet per record kind**, the sheet name being the kind's value
(``vulnerability``, ``hypomorph``, ...). Row 1 is the header. Each header cell is matched
case-folded and stripped, in this order:

1. the gene column named by ``match_by`` (``"locus_tag"`` or ``"gene_name"``) — gene-side
   kinds only; protein-side kinds (``protein_production``, ``protein_activity_assay``,
   ``unpublished_structure``) identify a row by ``accession``, which is already one of the
   kind's own core field names and needs no special-casing.
2. provenance — ``pmid`` and ``reference``/``dataset`` land on the record's own ``pmid``/
   ``dataset`` fields; ``source_type``, ``url``, ``note``, ``contributor`` and
   ``observed_on`` are recognised so they never get mistaken for an extension or an
   undeclared column, but none of the eight ``*ImportRecord`` classes has a field for them
   today, so their values are read and discarded. Closing that gap is a follow-up, not this
   task.
3. the kind's own core field names.
4. anything left over goes to ``extensions``, checked against the caller-supplied
   ``known_extension_fields[kind]`` — a column that matches nothing fails every row in the
   sheet, naming itself, rather than being silently dropped.

Record identity for deduplication is **the full row**: every mapped core value plus every
extension value, excluding provenance (metadata about the row, not the record). Two rows
identical on that tuple are one record; changing any single column makes them two. That is
the operator's own rule, and on the corpus this was built for it loses nothing but genuine
duplicates.

**Four small coercion rules are duplicated from
``application/target_biology/extension_validator.py`` rather than imported.** That module
is application-layer; this is infrastructure, and — independent of whatever the layer
contract would technically allow (``infrastructure/di/_target_biology.py`` already imports
it for DI wiring) — its one public method is ``async`` and needs a workspace-scoped
repository, which this module's purity contract forbids. The two traps it already fixed and
this module must not reintroduce:

- ``isinstance(True, int)`` is ``True`` in Python — ``integer`` and ``number`` must both
  reject booleans explicitly.
- ``date`` values must land as ISO-8601 strings, never a Python ``date``/``datetime`` — the
  ``extensions`` bag is JSONB and cannot serialise one, and openpyxl returns real
  ``datetime`` objects for date-formatted cells.

**Unresolvable ligand text.** ``UnpublishedStructureImportRecord.ligand_ids`` is a tuple of
UUIDs; a cell token that is not a UUID (a bare name like ``"Apo"``, ``"SO4 and PEG bound"``,
a raw SMILES string) cannot become one. Dropping it, as
``unpublished_structure_csv.py:_uuids`` does, is what let thirteen distinct structures
collapse into one under the widened ``(protein_id, method, ligands)`` key — two records
sharing only unresolved ligand text are indistinguishable from "no ligand" once the text is
gone. So here, a non-UUID token goes to ``extensions["ligand_reported"]`` instead (joined in
source order when a cell holds several), which full-row deduplication then keeps apart. This
closes the gap for add mode only: update mode's natural key still cannot discriminate two
structures whose ligands both fail to resolve, which is Task 5's preview to warn about.
"""

from __future__ import annotations

import datetime
import io
import re
import uuid
from dataclasses import MISSING, dataclass, fields
from typing import Any

import openpyxl

from protcellar.application.target_biology.bulk_upsert_crispri_strain import (
    CrispriStrainImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_essentiality import (
    EssentialityImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_hypomorph import HypomorphImportRecord
from protcellar.application.target_biology.bulk_upsert_protein_activity_assay import (
    ProteinActivityAssayImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_protein_production import (
    ProteinProductionImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_resistance_mutation import (
    ResistanceMutationImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_unpublished_structure import (
    UnpublishedStructureImportRecord,
)
from protcellar.application.target_biology.bulk_upsert_vulnerability import (
    VulnerabilityImportRecord,
)
from protcellar.application.target_biology.crud import RecordKind


@dataclass(frozen=True, kw_only=True)
class RowProblem:
    sheet: str
    row: int  # 1-based, as the spreadsheet shows it
    reason: str


@dataclass(frozen=True, kw_only=True)
class SheetPlan:
    kind: RecordKind
    records: list[Any]  # the kind's *ImportRecord instances, deduplicated
    rows_read: int
    merged_identical: int
    problems: list[RowProblem]


@dataclass(frozen=True, kw_only=True)
class KnownExtensionField:
    """One workspace-declared extension field, as ``known_extension_fields``
    carries it in — enough to both coerce a cell (``field_type``) and, for
    ``enum``, check it against the declared options."""

    field_type: str
    options: list[str] | None = None


_RECORD_CLASSES: dict[RecordKind, type[Any]] = {
    RecordKind.ESSENTIALITY: EssentialityImportRecord,
    RecordKind.VULNERABILITY: VulnerabilityImportRecord,
    RecordKind.HYPOMORPH: HypomorphImportRecord,
    RecordKind.CRISPRI_STRAIN: CrispriStrainImportRecord,
    RecordKind.RESISTANCE_MUTATION: ResistanceMutationImportRecord,
    RecordKind.PROTEIN_PRODUCTION: ProteinProductionImportRecord,
    RecordKind.PROTEIN_ACTIVITY_ASSAY: ProteinActivityAssayImportRecord,
    RecordKind.UNPUBLISHED_STRUCTURE: UnpublishedStructureImportRecord,
}

_GENE_SIDE: frozenset[RecordKind] = frozenset(
    {
        RecordKind.ESSENTIALITY,
        RecordKind.VULNERABILITY,
        RecordKind.HYPOMORPH,
        RecordKind.CRISPRI_STRAIN,
        RecordKind.RESISTANCE_MUTATION,
    }
)

# Coercion shapes for the kind's own core columns. Hand-maintained rather than derived from
# the dataclasses' annotations, which `from __future__ import annotations` turns into plain
# strings at runtime — not worth a fragile parser for eight small, stable classes.
# `test_core_field_tables_match_the_dataclasses` guards against this table drifting from the
# real fields (a name here that stops matching a real field silently reroutes that column to
# `extensions` instead of erroring, which is exactly the kind of drift worth a cheap alarm).
_STR, _BOOL, _FLOAT, _UUID, _LIGAND_IDS = "str", "bool", "float", "uuid", "ligand_ids"

_CORE_FIELDS: dict[RecordKind, dict[str, str]] = {
    RecordKind.ESSENTIALITY: {
        "classification": _STR,
        "condition": _STR,
        "method": _STR,
        "confidence": _FLOAT,
    },
    RecordKind.VULNERABILITY: {
        "vulnerability_score": _FLOAT,
        "confidence": _FLOAT,
        "condition": _STR,
        "method": _STR,
    },
    RecordKind.HYPOMORPH: {
        "growth_defect": _BOOL,
        "growth_defect_severity": _STR,
        "knockdown_strain": _STR,
        "condition": _STR,
        "method": _STR,
    },
    RecordKind.CRISPRI_STRAIN: {
        "name": _STR,
    },
    RecordKind.RESISTANCE_MUTATION: {
        "mutation": _STR,
        # Unlike ligands below, `compound_id` has no "unresolved" fallback: a cell
        # that isn't a UUID fails its row (`_to_uuid` raises) rather than being
        # silently dropped. A free-text compound label belongs in the separate
        # `compound_name` column below — nothing routes a failed `compound_id`
        # cell into it.
        "compound_id": _UUID,
        "compound_name": _STR,
        "mic_shift": _FLOAT,
        "parent_strain": _STR,
        "protein_coordinate": _STR,
        "method": _STR,
    },
    RecordKind.PROTEIN_PRODUCTION: {
        "accession": _STR,
        "status": _STR,
        "expression_host": _STR,
        "purity": _FLOAT,
        "condition": _STR,
        "method": _STR,
    },
    RecordKind.PROTEIN_ACTIVITY_ASSAY: {
        "accession": _STR,
        "activity_measured": _STR,
        "readout": _STR,
        "throughput": _STR,
        "condition": _STR,
        "method": _STR,
    },
    RecordKind.UNPUBLISHED_STRUCTURE: {
        "accession": _STR,
        "method": _STR,
        "resolution": _FLOAT,
        "ligand_ids": _LIGAND_IDS,
        "is_published": _BOOL,
        "is_experimental": _BOOL,
    },
}

# Recognised provenance headers. `pmid`/`dataset` (and the workbook's own `reference` name
# for the same field) land on the record; the rest are read and discarded — see module
# docstring §2.
_PROVENANCE_TO_FIELD: dict[str, str] = {
    "pmid": "pmid",
    "dataset": "dataset",
    "reference": "dataset",
}
_PROVENANCE_DROPPED: frozenset[str] = frozenset(
    {"source_type", "url", "note", "contributor", "observed_on"}
)

_EXCLUDED_FROM_REQUIRED = frozenset({"extensions", "locus_key", "pmid", "dataset"})


def _required_core_fields(kind: RecordKind) -> frozenset[str]:
    return frozenset(
        f.name
        for f in fields(_RECORD_CLASSES[kind])
        if f.name not in _EXCLUDED_FROM_REQUIRED
        and f.default is MISSING
        and f.default_factory is MISSING
    )


_REQUIRED: dict[RecordKind, frozenset[str]] = {k: _required_core_fields(k) for k in RecordKind}


def parse_workbook(
    data: bytes,
    *,
    match_by: str,
    known_extension_fields: dict[str, dict[str, KnownExtensionField]],
) -> tuple[list[SheetPlan], list[RowProblem]]:
    """Parse a workbook into one plan per recognised sheet. The second element holds
    workbook-level problems (unrecognised sheet, missing gene column)."""
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    kinds_by_sheet_name = {k.value: k for k in RecordKind}

    plans: list[SheetPlan] = []
    workbook_problems: list[RowProblem] = []
    seen_kinds: dict[RecordKind, str] = {}  # kind -> the first sheet name that claimed it
    for sheet_name in wb.sheetnames:
        kind = kinds_by_sheet_name.get(sheet_name.strip().casefold())
        if kind is None:
            workbook_problems.append(
                RowProblem(sheet=sheet_name, row=1, reason=f"unrecognised sheet {sheet_name!r}")
            )
            continue
        first_sheet = seen_kinds.get(kind)
        if first_sheet is not None:
            # Two sheet names ("Vulnerability", "vulnerability ") can both
            # normalise to the same kind. One plan exists per *sheet*
            # downstream, keyed by kind — a second plan for a kind already
            # claimed would silently overwrite the first's summary entry
            # while both still got dispatched and written. Reject the
            # duplicate outright instead: the first sheet in workbook order
            # wins, later ones are a workbook-level problem, never parsed.
            workbook_problems.append(
                RowProblem(
                    sheet=sheet_name,
                    row=1,
                    reason=(
                        f"duplicate sheet for kind {kind.value!r} — {first_sheet!r} already "
                        "supplies it in this workbook"
                    ),
                )
            )
            continue
        seen_kinds[kind] = sheet_name
        plan, sheet_workbook_problems = _parse_sheet(
            wb[sheet_name],
            kind,
            sheet_name,
            match_by,
            known_extension_fields.get(kind.value, {}),
        )
        plans.append(plan)
        workbook_problems.extend(sheet_workbook_problems)
    return plans, workbook_problems


def _parse_sheet(
    ws: Any,
    kind: RecordKind,
    sheet_name: str,
    match_by: str,
    known_ext: dict[str, KnownExtensionField],
) -> tuple[SheetPlan, list[RowProblem]]:
    rows = ws.iter_rows(values_only=True)
    header = [str(cell).strip().casefold() if cell is not None else "" for cell in next(rows, ())]
    gene_col, core_cols, ext_cols, provenance_cols, unknown_cols = _classify_header(
        header, kind, match_by, known_ext
    )

    workbook_problems: list[RowProblem] = []
    missing_gene_column = kind in _GENE_SIDE and gene_col is None
    if missing_gene_column:
        workbook_problems.append(
            RowProblem(sheet=sheet_name, row=1, reason=f"no {match_by!r} column found")
        )
    # The protein-side mirror of missing_gene_column: accession is a plain
    # core column (module docstring, header group 1), not a special-cased
    # gene_col, so a sheet missing it entirely would otherwise fail every
    # single row with the same "missing accession" reason — at corpus scale,
    # thousands of identical problems and zero records. One workbook-level
    # problem instead.
    missing_accession_column = kind not in _GENE_SIDE and "accession" not in core_cols.values()
    if missing_accession_column:
        workbook_problems.append(
            RowProblem(sheet=sheet_name, row=1, reason="no 'accession' column found")
        )

    record_cls = _RECORD_CLASSES[kind]
    required = _REQUIRED[kind]
    records: list[Any] = []
    problems: list[RowProblem] = []
    seen: set[tuple[Any, ...]] = set()
    rows_read = 0
    merged_identical = 0

    for row_num, row in enumerate(rows, start=2):
        if row is None or all(c is None for c in row):
            continue
        rows_read += 1

        if missing_gene_column or missing_accession_column:
            continue  # already reported once, at the workbook level
        if unknown_cols:
            problems.append(
                RowProblem(
                    sheet=sheet_name,
                    row=row_num,
                    reason=(
                        f"unrecognised column(s) {', '.join(unknown_cols)} — fix the header "
                        "or declare as an extension field"
                    ),
                )
            )
            continue

        try:
            kwargs = _row_kwargs(
                row, kind, match_by, gene_col, core_cols, ext_cols, provenance_cols
            )
            missing = required - kwargs.keys()
            if missing:
                raise ValueError(f"missing {', '.join(sorted(missing))}")
            record = record_cls(**kwargs)
        except ValueError as exc:
            problems.append(RowProblem(sheet=sheet_name, row=row_num, reason=str(exc)))
            continue

        key = _dedup_key(kind, kwargs)
        if key in seen:
            merged_identical += 1
            continue
        seen.add(key)
        records.append(record)

    plan = SheetPlan(
        kind=kind,
        records=records,
        rows_read=rows_read,
        merged_identical=merged_identical,
        problems=problems,
    )
    return plan, workbook_problems


def _classify_header(
    header: list[str],
    kind: RecordKind,
    match_by: str,
    known_ext: dict[str, KnownExtensionField],
) -> tuple[
    int | None,
    dict[int, str],
    list[tuple[int, str, KnownExtensionField]],
    dict[int, str],
    list[str],
]:
    """One pass over the header row. Returns ``(gene_col, core_cols, ext_cols,
    provenance_cols, unknown_column_names)`` — see the module docstring for the
    classification order."""
    match_by_key = match_by.strip().casefold()
    core_map = _CORE_FIELDS[kind]

    gene_col: int | None = None
    core_cols: dict[int, str] = {}
    ext_cols: list[tuple[int, str, KnownExtensionField]] = []
    provenance_cols: dict[int, str] = {}
    unknown: list[str] = []

    for idx, name in enumerate(header):
        if not name:
            continue  # a stray unnamed column — common Excel cruft, nothing to report
        if kind in _GENE_SIDE and gene_col is None and name == match_by_key:
            gene_col = idx
            continue
        if name in core_map:
            core_cols[idx] = name
            continue
        if name in _PROVENANCE_TO_FIELD:
            provenance_cols[idx] = _PROVENANCE_TO_FIELD[name]
            continue
        if name in _PROVENANCE_DROPPED:
            continue
        field = known_ext.get(name)
        if field is None:
            unknown.append(name)
            continue
        ext_cols.append((idx, name, field))

    return gene_col, core_cols, ext_cols, provenance_cols, unknown


def _row_kwargs(
    row: tuple[Any, ...],
    kind: RecordKind,
    match_by: str,
    gene_col: int | None,
    core_cols: dict[int, str],
    ext_cols: list[tuple[int, str, KnownExtensionField]],
    provenance_cols: dict[int, str],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    extensions: dict[str, Any] = {}

    if kind in _GENE_SIDE:
        identity = _to_str(_cell(row, gene_col))
        if identity is None:
            raise ValueError(f"missing {match_by}")
        kwargs["locus_key"] = identity

    for col_idx, field_name in provenance_cols.items():
        value = _to_str(_cell(row, col_idx))
        if value is not None:
            kwargs[field_name] = value

    for col_idx, field_name in core_cols.items():
        raw = _cell(row, col_idx)
        shape = _CORE_FIELDS[kind][field_name]
        if shape == _LIGAND_IDS:
            ligand_ids, reported = _parse_ligands(raw)
            kwargs[field_name] = ligand_ids
            if reported is not None:
                extensions["ligand_reported"] = reported
            continue
        coerced = _coerce_core(raw, shape, field_name)
        if coerced is None:
            continue  # leave the dataclass's own default in place
        kwargs[field_name] = coerced

    for col_idx, field_name, field in ext_cols:
        raw = _cell(row, col_idx)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        extensions[field_name] = _coerce_extension_value(raw, field, field_name)

    if extensions:
        kwargs["extensions"] = extensions
    return kwargs


def _dedup_key(kind: RecordKind, kwargs: dict[str, Any]) -> tuple[Any, ...]:
    """The full tuple of mapped domain values — core plus extensions, excluding
    provenance (`pmid`/`dataset` are metadata about the row, not the record)."""
    identity_field = "locus_key" if kind in _GENE_SIDE else "accession"
    core_values = tuple(kwargs.get(name) for name in _CORE_FIELDS[kind])
    extensions = kwargs.get("extensions") or {}
    return (kwargs.get(identity_field), core_values, tuple(sorted(extensions.items())))


def _cell(row: tuple[Any, ...], idx: int | None) -> Any:
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def _coerce_core(value: Any, shape: str, name: str) -> Any:
    if shape == _STR:
        return _to_str(value)
    if shape == _BOOL:
        return None if value is None else _to_bool(value)
    if shape == _FLOAT:
        return _to_float(value, name)
    if shape == _UUID:
        return _to_uuid(value, name)
    raise AssertionError(f"unhandled core field shape {shape!r}")  # pragma: no cover


def _to_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def _to_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, bool):  # isinstance(True, int) is True — reject before float()
        raise ValueError(f"{name!r} must be a number, got {value!r}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name!r} is not a number: {value!r}") from exc


def _to_uuid(value: Any, name: str) -> uuid.UUID | None:
    text = _to_str(value)
    if text is None:
        return None
    try:
        return uuid.UUID(text)
    except ValueError as exc:
        raise ValueError(f"{name!r} is not a valid UUID: {value!r}") from exc


def _parse_ligands(value: Any) -> tuple[tuple[uuid.UUID, ...], str | None]:
    """Split a ``;``/``,``-separated ligand cell into resolved UUIDs and unresolved text.
    See the module docstring's "Unresolvable ligand text" section."""
    text = _to_str(value)
    if text is None:
        return (), None
    tokens = [t.strip() for t in re.split(r"[;,]", text) if t.strip()]
    ids: list[uuid.UUID] = []
    unresolved: list[str] = []
    for token in tokens:
        try:
            ids.append(uuid.UUID(token))
        except ValueError:
            unresolved.append(token)
    return tuple(ids), ("; ".join(unresolved) if unresolved else None)


def _numeric_cell(value: Any, name: str, article: str) -> int | float:
    """A numeric cell, accepting a numeric *string* as well as a real number.

    This is the one place the parser deliberately diverges from
    ``extension_validator.py``, and the reason is the input medium. The
    validator reads JSON, where the difference between ``3`` and ``"3"`` is
    real and a string is a genuine type error. A spreadsheet has no such
    distinction to preserve: whether a cell arrives as a number or as text is
    a formatting accident of how the sheet was produced, and an export from
    almost any system writes numbers as text. Rejecting ``"3.0"`` here would
    fail thousands of otherwise-valid rows for a property of the exporter
    nobody chose.

    Non-numeric text still fails, and ``bool`` is still rejected outright —
    ``isinstance(True, int)`` is ``True``, so it has to be caught before the
    numeric check rather than after.
    """
    if isinstance(value, bool):
        raise ValueError(f"{name!r} must be {article}")
    if isinstance(value, int | float):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"{name!r} must be {article}, got {value!r}") from None
    raise ValueError(f"{name!r} must be {article}")


def _coerce_extension_value(value: Any, field: KnownExtensionField, name: str) -> Any:
    """Mirrors ``extension_validator.py``'s coercion rules — duplicated, not
    imported; see the module docstring. ``field`` carries the declared type
    *and* (for ``enum``) the declared options, exactly like the validator's
    own ``ExtensionFieldDef``, so an enum cell that isn't one of them fails
    its row here too.
    """
    field_type = field.field_type
    if isinstance(value, datetime.datetime):
        value = value.date().isoformat()
    elif isinstance(value, datetime.date):
        value = value.isoformat()

    if field_type in ("string", "text"):
        if not isinstance(value, str):
            raise ValueError(f"{name!r} must be a string")
        return value
    if field_type == "enum":
        if not isinstance(value, str):
            raise ValueError(f"{name!r} must be a string")
        if value not in (field.options or ()):
            raise ValueError(f"{name!r} must be one of {field.options}")
        return value
    if field_type == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{name!r} must be a boolean")
        return value
    if field_type == "integer":
        number = _numeric_cell(value, name, "an integer")
        if not float(number).is_integer():
            raise ValueError(f"{name!r} must be an integer")
        return int(number)
    if field_type == "number":
        return _numeric_cell(value, name, "a number")
    if field_type == "date":
        if not isinstance(value, str):
            raise ValueError(f"{name!r} must be an ISO-8601 date string")
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"{name!r} must be an ISO-8601 date string, got {value!r}") from None
        return value  # store the original string — JSONB can't hold a `date`
    raise ValueError(f"{name!r} has an unrecognised declared type {field_type!r}")
