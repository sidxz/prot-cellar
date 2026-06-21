"""Pure parser for the DeJesus 2017 (mBio, PMID:28096490) essentiality table.

Maps each locus tag to a normalized essentiality call. Accepts TSV or CSV,
detects the locus and call columns by header aliases, and normalizes the HMM
call codes (ES/ESD/GD/NE/GA, else uncertain). No I/O — the loader reads the
file and hands the text here, so this stays unit-testable on fixtures.
"""

from __future__ import annotations

import csv
import io

_LOCUS_HEADERS = ("orf", "rv id", "rv_id", "locus", "locus_tag", "gene id", "id")
_CALL_HEADERS = (
    "final call",
    "call",
    "essentiality",
    "essentiality call",
    "state",
    "prediction",
)

# HMM call codes → normalized vocabulary (see plan Global Constraints).
_CALL_MAP = {
    "es": "essential",
    "esd": "essential",  # essential domain
    "gd": "growth-defect",
    "ne": "non-essential",
    "ga": "growth-advantage",
}


def parse_dejesus_essentiality(text: str) -> dict[str, str]:
    """Parse an essentiality table into ``{locus_tag: normalized_call}``."""
    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return {}

    header = [cell.strip().lower() for cell in rows[0]]
    locus_idx = _column(header, _LOCUS_HEADERS, default=0)
    call_idx = _column(header, _CALL_HEADERS, default=len(header) - 1)

    calls: dict[str, str] = {}
    for row in rows[1:]:
        if len(row) <= max(locus_idx, call_idx):
            continue
        locus = row[locus_idx].strip()
        if not locus:
            continue
        calls[locus] = _normalize(row[call_idx])
    return calls


def _column(header: list[str], aliases: tuple[str, ...], *, default: int) -> int:
    for alias in aliases:
        if alias in header:
            return header.index(alias)
    return default


def _normalize(raw: str) -> str:
    return _CALL_MAP.get(raw.strip().lower(), "uncertain")
