from __future__ import annotations

import datetime
import io
import typing
import uuid
from dataclasses import fields
from typing import Any

import openpyxl
import pytest

from protcellar.application.target_biology.crud import RecordKind
from protcellar.infrastructure.ingestion.target_biology_workbook import (
    _BOOL,
    _CORE_FIELDS,
    _EXCLUDED_FROM_REQUIRED,
    _FLOAT,
    _LIGAND_IDS,
    _RECORD_CLASSES,
    _STR,
    _UUID,
    KnownExtensionField,
    RowProblem,
    SheetPlan,
    _coerce_extension_value,
    parse_workbook,
)


def _workbook(sheets: dict[str, list[list[Any]]]) -> bytes:
    """Build an in-memory .xlsx: sheet name -> rows, row 0 being the header."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _plan(
    data: bytes,
    match_by: str = "locus_tag",
    known_ext: dict[str, dict[str, KnownExtensionField]] | None = None,
) -> tuple[list[SheetPlan], list[RowProblem]]:
    return parse_workbook(data, match_by=match_by, known_extension_fields=known_ext or {})


# --- the nine tests named in the brief ------------------------------------------------


def test_a_sheet_per_kind_is_parsed_and_an_unknown_sheet_is_reported() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification"],
                ["Rv0001", "essential"],
            ],
            "vulnerability": [
                ["locus_tag", "vulnerability_score"],
                ["Rv0002", "0.8"],
            ],
            "not_a_kind": [["foo"], ["bar"]],
        }
    )
    plans, problems = _plan(data)

    kinds = {p.kind for p in plans}
    assert kinds == {RecordKind.ESSENTIALITY, RecordKind.VULNERABILITY}
    assert len(problems) == 1
    assert "not_a_kind" in problems[0].reason


def test_two_sheets_normalising_to_the_same_kind_the_second_is_rejected() -> None:
    """ "Vulnerability" and "vulnerability " both normalise to the same kind —
    the second must be a workbook-level problem, never silently written
    alongside the first while its own summary counts get overwritten."""
    data = _workbook(
        {
            "Vulnerability": [
                ["locus_tag", "condition"],
                ["Rv0001", "hypoxia"],
            ],
            "vulnerability ": [
                ["locus_tag", "condition"],
                ["Rv0002", "normoxia"],
            ],
        }
    )
    plans, problems = _plan(data)
    assert len(plans) == 1
    assert plans[0].kind == RecordKind.VULNERABILITY
    assert plans[0].records[0].locus_key == "Rv0001"  # the first sheet in the workbook wins
    assert len(problems) == 1
    assert problems[0].sheet == "vulnerability "
    assert "duplicate sheet" in problems[0].reason
    assert "vulnerability" in problems[0].reason.lower()


def test_two_identical_rows_become_one_record() -> None:
    data = _workbook(
        {
            "vulnerability": [
                ["locus_tag", "condition", "method"],
                ["Rv0001", "hypoxia", "CRISPRi"],
                ["Rv0001", "hypoxia", "CRISPRi"],
            ]
        }
    )
    plans, _ = _plan(data)
    (plan,) = plans
    assert plan.rows_read == 2
    assert len(plan.records) == 1
    assert plan.merged_identical == 1
    assert plan.problems == []


def test_changing_any_single_column_yields_two_records() -> None:
    data = _workbook(
        {
            "vulnerability": [
                ["locus_tag", "condition", "method"],
                ["Rv0001", "hypoxia", "CRISPRi"],
                ["Rv0001", "normoxia", "CRISPRi"],
            ]
        }
    )
    plans, _ = _plan(data)
    (plan,) = plans
    assert len(plan.records) == 2
    assert plan.merged_identical == 0


def test_thirteen_structures_differing_only_by_ligand_stay_thirteen() -> None:
    rows = [["accession", "method", "ligand_ids"]]
    for i in range(13):
        # None of these resolve as UUIDs — the exact shape of the corpus's real values.
        rows.append(["P9WGE9", "X-ray", f"unresolved-ligand-{i}"])
    data = _workbook({"unpublished_structure": rows})
    plans, _ = _plan(data)
    (plan,) = plans
    assert plan.rows_read == 13
    assert len(plan.records) == 13
    assert plan.merged_identical == 0
    for i, record in enumerate(plan.records):
        assert record.ligand_ids == ()
        assert record.extensions == {"ligand_reported": f"unresolved-ligand-{i}"}


def test_nine_hypomorphs_of_one_gene_stay_nine() -> None:
    rows = [["locus_tag", "growth_defect", "knockdown_strain"]]
    for i in range(9):
        rows.append(["Rv0001", "true", f"strain-{i}"])
    data = _workbook({"hypomorph": rows})
    plans, _ = _plan(data)
    (plan,) = plans
    assert plan.rows_read == 9
    assert len(plan.records) == 9
    assert plan.merged_identical == 0
    assert {r.knockdown_strain for r in plan.records} == {f"strain-{i}" for i in range(9)}


def test_an_unrecognised_column_becomes_an_extension_when_declared() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification", "vi_bin"],
                ["Rv0001", "essential", 3],
            ]
        }
    )
    known_ext = {"essentiality": {"vi_bin": KnownExtensionField(field_type="integer")}}
    plans, _ = _plan(data, known_ext=known_ext)
    (plan,) = plans
    assert plan.problems == []
    assert plan.records[0].extensions == {"vi_bin": 3}


def test_an_undeclared_column_fails_its_rows_and_names_the_column() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification", "mystery_column"],
                ["Rv0001", "essential", "x"],
                ["Rv0002", "essential", "y"],
            ]
        }
    )
    plans, _ = _plan(data)
    (plan,) = plans
    assert plan.records == []
    assert len(plan.problems) == 2
    assert all("mystery_column" in p.reason for p in plan.problems)
    assert [p.row for p in plan.problems] == [2, 3]


def test_a_row_missing_the_gene_column_is_a_problem_not_a_crash() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification"],
                ["Rv0001", "essential"],
                [None, "essential"],
            ]
        }
    )
    plans, _ = _plan(data)
    (plan,) = plans
    assert len(plan.records) == 1
    assert plan.rows_read == 2
    assert len(plan.problems) == 1
    assert plan.problems[0].row == 3
    assert "locus_tag" in plan.problems[0].reason


def test_an_unparseable_compound_id_fails_its_row_instead_of_merging_with_another() -> None:
    """A cell that isn't a UUID must fail its row (`_to_uuid` raising, mirroring
    `_to_float`) rather than silently becoming `None` — the old swallow-and-
    return-None behaviour made two distinct resistance mutations, naming two
    different compounds, dedup-collapse into one silently-merged record."""
    data = _workbook(
        {
            "resistance_mutation": [
                ["locus_tag", "mutation", "compound_id", "method"],
                ["Rv1908c", "S315T", "Isoniazid", "MIC"],
                ["Rv1908c", "S315T", "Rifampicin", "MIC"],
            ]
        }
    )
    plans, _ = _plan(data)
    (plan,) = plans
    assert plan.records == []
    assert plan.merged_identical == 0
    assert len(plan.problems) == 2
    assert all("compound_id" in p.reason for p in plan.problems)


def test_a_value_that_will_not_parse_fails_only_its_own_row() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification", "confidence"],
                ["Rv0001", "essential", "0.9"],
                ["Rv0002", "essential", "not-a-number"],
            ]
        }
    )
    plans, _ = _plan(data)
    (plan,) = plans
    assert len(plan.records) == 1
    assert plan.records[0].locus_key == "Rv0001"
    assert len(plan.problems) == 1
    assert plan.problems[0].row == 3
    assert "confidence" in plan.problems[0].reason


# --- the structural half of "missing gene column": workbook-level, not per-row --------


def test_a_sheet_with_no_gene_column_at_all_is_a_workbook_level_problem() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["classification"],
                ["essential"],
            ]
        }
    )
    plans, problems = _plan(data)
    (plan,) = plans
    assert plan.kind == RecordKind.ESSENTIALITY
    assert plan.records == []
    assert plan.problems == []  # not a row-level concern
    assert len(problems) == 1
    assert "locus_tag" in problems[0].reason


def test_a_protein_side_sheet_with_no_accession_column_is_one_workbook_level_problem() -> None:
    """The protein-side mirror of the gene-column case above: accession is a
    plain core column, not special-cased like gene_col, so without this
    workbook-level short-circuit a sheet missing it would fail every row
    individually instead of once."""
    data = _workbook(
        {
            "protein_production": [
                ["status"],
                ["produced"],
                ["produced"],
            ]
        }
    )
    plans, problems = _plan(data)
    (plan,) = plans
    assert plan.kind == RecordKind.PROTEIN_PRODUCTION
    assert plan.records == []
    assert plan.problems == []  # not a row-level concern
    assert len(problems) == 1
    assert "accession" in problems[0].reason


@pytest.mark.parametrize(
    ("sheet", "header", "row", "optional_field"),
    [
        (
            "protein_production",
            ["accession", "expression_host"],
            ["P9WGE9", "E. coli BL21"],
            "status",
        ),
        (
            "protein_activity_assay",
            ["accession", "method"],
            ["P9WGE9", "fluorescence"],
            "activity_measured",
        ),
    ],
)
def test_a_sheet_omitting_the_now_optional_status_or_activity_column_still_imports(
    sheet: str, header: list[str], row: list[Any], optional_field: str
) -> None:
    """status / activity_measured are no longer required on their dataclasses — a sheet
    that never had that column at all (the legacy corpus this exists for) must still
    import its row, unlike a genuinely missing identity column such as 'accession'
    above, which fails every row in the sheet."""
    data = _workbook({sheet: [header, row]})
    plans, problems = _plan(data)
    (plan,) = plans
    assert problems == []
    assert plan.problems == []
    (record,) = plan.records
    assert getattr(record, optional_field) is None


def test_a_hypomorph_sheet_with_a_blank_growth_defect_cell_still_imports() -> None:
    """growth_defect is no longer required on the dataclass — a row with the column
    present but the cell blank (the legacy corpus's 10 'TBD' rows, once a curator or
    export step has cleared the cell rather than write "TBD" into a boolean column)
    must still import, landing as None ("not determined") rather than failing the
    row. Distinct from the sheet-omits-the-column case above: here the column is
    present, just empty for this one row."""
    rows = [
        ["locus_tag", "growth_defect", "knockdown_strain"],
        ["Rv0001", None, "strainA"],
    ]
    data = _workbook({"hypomorph": rows})
    plans, problems = _plan(data)
    (plan,) = plans
    assert problems == []
    assert plan.problems == []
    (record,) = plan.records
    assert record.growth_defect is None
    assert record.knockdown_strain == "strainA"


# --- the two named traps ----------------------------------------------------------------


def test_a_boolean_cell_is_rejected_for_a_declared_integer_extension() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification", "vi_bin"],
                ["Rv0001", "essential", True],
            ]
        }
    )
    known_ext = {"essentiality": {"vi_bin": KnownExtensionField(field_type="integer")}}
    plans, _ = _plan(data, known_ext=known_ext)
    (plan,) = plans
    assert plan.records == []
    assert len(plan.problems) == 1
    assert "vi_bin" in plan.problems[0].reason


def test_a_date_formatted_cell_lands_as_an_iso_string_not_a_datetime() -> None:
    data = _workbook(
        {
            "protein_production": [
                ["accession", "status", "date_produced"],
                ["P9WGE9", "produced", datetime.date(2024, 1, 15)],
            ]
        }
    )
    known_ext = {"protein_production": {"date_produced": KnownExtensionField(field_type="date")}}
    plans, _ = _plan(data, known_ext=known_ext)
    (plan,) = plans
    assert plan.problems == []
    value = plan.records[0].extensions["date_produced"]
    assert value == "2024-01-15"
    assert isinstance(value, str)


# --- enum extension fields check declared options, not just "is a string" -------------


def test_an_enum_cell_outside_its_declared_options_fails_its_row() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification", "vi_bin_category"],
                ["Rv0001", "essential", "banana"],
            ]
        }
    )
    known_ext = {
        "essentiality": {
            "vi_bin_category": KnownExtensionField(field_type="enum", options=["low", "high"])
        }
    }
    plans, _ = _plan(data, known_ext=known_ext)
    (plan,) = plans
    assert plan.records == []
    assert len(plan.problems) == 1
    assert "vi_bin_category" in plan.problems[0].reason


def test_an_enum_cell_matching_a_declared_option_is_accepted() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification", "vi_bin_category"],
                ["Rv0001", "essential", "high"],
            ]
        }
    )
    known_ext = {
        "essentiality": {
            "vi_bin_category": KnownExtensionField(field_type="enum", options=["low", "high"])
        }
    }
    plans, _ = _plan(data, known_ext=known_ext)
    (plan,) = plans
    assert plan.problems == []
    assert plan.records[0].extensions == {"vi_bin_category": "high"}


# --- provenance columns are recognised without needing a landing field ----------------


def test_provenance_columns_are_recognised_pmid_and_reference_land_note_does_not() -> None:
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification", "pmid", "reference", "note"],
                ["Rv0001", "essential", "12345", "DeJesus 2017", "checked twice"],
            ]
        }
    )
    plans, _ = _plan(data)
    (plan,) = plans
    assert plan.problems == []
    record = plan.records[0]
    assert record.pmid == "12345"
    assert record.dataset == "DeJesus 2017"
    assert record.extensions is None  # "note" is recognised, not swept into extensions


# --- a schema-drift guard: the hand-maintained core-field table must track the dataclasses

_SHAPE_BY_TYPE: dict[type, str] = {
    str: _STR,
    bool: _BOOL,
    float: _FLOAT,
    uuid.UUID: _UUID,
}


def _expected_shape(annotation: Any) -> str:
    """Maps a *resolved* (``typing.get_type_hints``, not the bare stringified
    annotation ``from __future__ import annotations`` leaves on the
    dataclass) type hint to the ``_CORE_FIELDS`` shape constant it should be
    declared as. ``ligand_ids`` is the one field whose annotation isn't
    Optional-wrapped and isn't a plain scalar type."""
    if annotation == tuple[uuid.UUID, ...]:
        return _LIGAND_IDS
    args = typing.get_args(annotation)
    core = next((a for a in args if a is not type(None)), annotation)
    return _SHAPE_BY_TYPE[core]


def test_core_field_tables_match_the_dataclasses() -> None:
    for kind, record_cls in _RECORD_CLASSES.items():
        real_fields = {f.name for f in fields(record_cls)} - _EXCLUDED_FROM_REQUIRED
        assert set(_CORE_FIELDS[kind]) == real_fields, kind

        # A name matching isn't enough: a field whose declared type changes
        # under a stable name would slip past the check above, and
        # _CORE_FIELDS drives both coercion and the dedup key.
        hints = typing.get_type_hints(record_cls)
        for name, shape in _CORE_FIELDS[kind].items():
            assert _expected_shape(hints[name]) == shape, (kind, name)


@pytest.mark.parametrize(
    ("declared", "cell", "expected"),
    [
        # A spreadsheet has no number-vs-string distinction to preserve: whether a
        # cell arrives as text is a property of whatever produced the sheet. The
        # corpus this importer was built for writes every numeric as text.
        ("integer", "3.0", 3),
        ("integer", "3", 3),
        ("integer", 3.0, 3),
        ("number", "347.0", 347.0),
        ("number", "-8.4", -8.4),
    ],
)
def test_a_text_formatted_number_is_accepted(
    declared: str, cell: object, expected: object
) -> None:
    field = KnownExtensionField(field_type=declared)
    assert _coerce_extension_value(cell, field, "x") == expected


@pytest.mark.parametrize(
    ("declared", "cell"),
    [
        ("integer", "5.5"),  # a fraction is still not an integer
        ("integer", "2%"),  # a unit suffix is not a formatting accident
        ("integer", True),  # isinstance(True, int) is True — must stay rejected
        ("number", "abc"),
        ("number", True),
        ("number", ""),
    ],
)
def test_text_that_is_not_a_number_still_fails(declared: str, cell: object) -> None:
    field = KnownExtensionField(field_type=declared)
    with pytest.raises(ValueError):
        _coerce_extension_value(cell, field, "x")


@pytest.mark.parametrize(
    ("cell", "expected"),
    [("True", True), ("FALSE", False), ("true", True), ("Yes", True), ("no", False), (True, True)],
)
def test_a_text_formatted_boolean_is_accepted(cell: object, expected: bool) -> None:
    # The corpus writes every boolean as text. A declared boolean leaves no room
    # for "yes" to mean anything but true; a source with three states wants an
    # enum declaration instead, which is what suitable_for_screening uses.
    field = KnownExtensionField(field_type="boolean")
    assert _coerce_extension_value(cell, field, "x") is expected


@pytest.mark.parametrize("cell", ["TBD", "maybe", "", 1, 0, None])
def test_text_that_is_not_a_boolean_still_fails(cell: object) -> None:
    field = KnownExtensionField(field_type="boolean")
    with pytest.raises(ValueError):
        _coerce_extension_value(cell, field, "x")


def test_a_core_string_longer_than_its_column_fails_only_its_own_row() -> None:
    """asyncpg raises StringDataRightTruncationError at flush — a DBAPIError, not a
    DomainError — so the bulk commands' per-row handler does not catch it and one
    over-long cell fails the entire run. A real import of the legacy corpus died
    exactly this way, after a preview that had promised 4,002 creates."""
    long_condition = "x" * 200  # essentiality_records.condition is varchar(128)
    data = _workbook(
        {
            "essentiality": [
                ["locus_tag", "classification", "condition"],
                ["Rv0001", "essential", long_condition],
                ["Rv0002", "essential", "7H9"],
            ]
        }
    )
    plans, _ = _plan(data)
    plan = plans[0]
    assert len(plan.records) == 1  # the short row survives
    assert len(plan.problems) == 1
    assert plan.problems[0].row == 2
    assert "128" in plan.problems[0].reason
