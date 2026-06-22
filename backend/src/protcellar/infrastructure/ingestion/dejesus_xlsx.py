"""In-memory XLSX→TSV converter for DeJesus 2017 essentiality uploads.

Supports:
- ``.xlsx`` files: parsed in-memory with openpyxl.  Column detection mirrors
  the one-off ``scripts/convert_dejesus_xlsx.py`` (ORF ID in col A, Final Call
  in col M of the real Table S3), but also handles simpler workbooks where the
  header row is row 1 (e.g. in-test fixtures).
- ``.tsv`` / ``.csv`` / ``.txt``: decoded as UTF-8 and passed through unchanged.

In all cases the result is validated by running ``parse_dejesus_essentiality``;
an empty result raises ``ValueError("no essentiality rows parsed")``.
"""

from __future__ import annotations

import io

import openpyxl
import structlog

from protcellar.infrastructure.ingestion.dejesus_essentiality import (
    parse_dejesus_essentiality,
)

logger = structlog.get_logger(__name__)

# Column indices used by the real DeJesus 2017 Table S3 XLSX:
#   col A (0) = ORF ID, col M (12) = Final Call.
# Data starts at row 3 because row 1 is a title and row 2 is the header.
_REAL_ORF_COL = 0
_REAL_CALL_COL = 12
_REAL_DATA_START_ROW = 3  # 1-indexed

# Header aliases for dynamic detection (lowercase).
_ORF_ALIASES = ("orf id", "orf", "rv id", "rv_id", "locus", "locus_tag", "gene id", "id")
_CALL_ALIASES = ("final call", "call", "essentiality", "essentiality call", "state", "prediction")


def essentiality_upload_to_tsv(filename: str, data: bytes) -> str:
    """Convert an uploaded essentiality file to ``locus\\tcall`` TSV text.

    Parameters
    ----------
    filename:
        Original filename — used only to dispatch on extension.
    data:
        Raw file bytes.

    Returns
    -------
    str
        Validated TSV text (header + data rows).

    Raises
    ------
    ValueError
        If ``parse_dejesus_essentiality`` returns an empty dict (nothing parsed).
    """
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        text = _xlsx_to_tsv(data, filename=filename)
    else:
        # .tsv / .csv / .txt — pass through as UTF-8
        text = data.decode("utf-8")

    _validate(text)
    return text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _xlsx_to_tsv(data: bytes, *, filename: str = "<unknown>") -> str:
    """Extract locus + call columns from an XLSX and emit TSV."""
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active

    # Scan each row for a header row (contains an ORF alias AND a call alias).
    # This handles both the real Table S3 (header on row 2) and simple test
    # fixtures (header on row 1).
    header_row_idx: int | None = None
    orf_col: int | None = None
    call_col: int | None = None

    all_rows = list(ws.iter_rows(values_only=True))
    for row_idx, row in enumerate(all_rows):
        cells = [str(c).strip().lower() if c is not None else "" for c in row]
        candidate_orf = _find_col(cells, _ORF_ALIASES)
        candidate_call = _find_col(cells, _CALL_ALIASES)
        if candidate_orf is not None and candidate_call is not None:
            header_row_idx = row_idx
            orf_col = candidate_orf
            call_col = candidate_call
            break

    if header_row_idx is None:
        # Fall back to script's hardcoded layout (row 2 header / row 3+ data)
        # and column positions used in the real Table S3.
        logger.warning(
            "dejesus_xlsx.header_detection_failed_using_fixed_indices",
            filename=filename,
        )
        orf_col = _REAL_ORF_COL
        call_col = _REAL_CALL_COL
        data_rows = all_rows[_REAL_DATA_START_ROW - 1 :]  # 0-indexed slice
    else:
        data_rows = all_rows[header_row_idx + 1 :]

    lines = ["ORF ID\tFinal Call"]
    for row in data_rows:
        if len(row) <= max(orf_col, call_col):  # type: ignore[arg-type]
            continue
        orf = row[orf_col]  # type: ignore[index]
        call = row[call_col]  # type: ignore[index]
        if orf and str(orf).strip():
            lines.append(f"{str(orf).strip()}\t{str(call).strip() if call else ''}")

    return "\n".join(lines) + "\n"


def _find_col(header_cells: list[str], aliases: tuple[str, ...]) -> int | None:
    # Normalize each header cell: collapse internal whitespace/newlines so that
    # e.g. "ORF\nID" or "ORF  ID" both match the alias "orf id".
    normalized = [" ".join(str(h).split()).lower() for h in header_cells]
    for alias in aliases:
        if alias in normalized:
            return normalized.index(alias)
    return None


def _validate(text: str) -> None:
    parsed = parse_dejesus_essentiality(text)
    if not parsed:
        raise ValueError("no essentiality rows parsed")
