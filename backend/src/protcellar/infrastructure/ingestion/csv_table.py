"""Tiny CSV/TSV table helper for import parsers.

Auto-detects tab vs comma, lower-cases the header, and offers alias-based column
lookup — so each record parser is just a column map, not delimiter/header plumbing.
"""

from __future__ import annotations

import csv
import io


class CsvTable:
    def __init__(self, text: str) -> None:
        self.header: list[str] = []
        self._rows: list[list[str]] = []
        text = text.strip()
        if not text:
            return
        delimiter = "\t" if "\t" in text.splitlines()[0] else ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = [r for r in reader if any(c.strip() for c in r)]
        if rows:
            self.header = [h.strip().lower() for h in rows[0]]
            self._rows = rows[1:]

    def col(self, *aliases: str) -> int | None:
        return next((i for i, h in enumerate(self.header) if h in aliases), None)

    def require(self, *aliases: str) -> int:
        idx = self.col(*aliases)
        if idx is None:
            raise ValueError(f"missing required column (one of: {', '.join(aliases)})")
        return idx

    @property
    def data_rows(self) -> list[list[str]]:
        return self._rows

    @staticmethod
    def cell(row: list[str], idx: int | None) -> str | None:
        if idx is None or idx >= len(row):
            return None
        return row[idx].strip() or None

    @staticmethod
    def as_bool(value: str | None) -> bool:
        """Parse a truthy cell; empty/unrecognised -> False."""
        return (value or "").strip().lower() in {"true", "1", "yes", "y", "t"}
