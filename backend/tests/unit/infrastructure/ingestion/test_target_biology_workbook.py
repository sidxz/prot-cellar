from __future__ import annotations

import datetime
import io
from dataclasses import fields
from typing import Any

import openpyxl

from protcellar.application.target_biology.crud import RecordKind
from protcellar.infrastructure.ingestion.target_biology_workbook import (
    _CORE_FIELDS,
    _EXCLUDED_FROM_REQUIRED,
    _RECORD_CLASSES,
    RowProblem,
    SheetPlan,
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
    known_ext: dict[str, dict[str, str]] | None = None,
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
    known_ext = {"essentiality": {"vi_bin": "integer"}}
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
    known_ext = {"essentiality": {"vi_bin": "integer"}}
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
    known_ext = {"protein_production": {"date_produced": "date"}}
    plans, _ = _plan(data, known_ext=known_ext)
    (plan,) = plans
    assert plan.problems == []
    value = plan.records[0].extensions["date_produced"]
    assert value == "2024-01-15"
    assert isinstance(value, str)


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


def test_core_field_tables_match_the_dataclasses() -> None:
    for kind, record_cls in _RECORD_CLASSES.items():
        real_fields = {f.name for f in fields(record_cls)} - _EXCLUDED_FROM_REQUIRED
        assert set(_CORE_FIELDS[kind]) == real_fields, kind
