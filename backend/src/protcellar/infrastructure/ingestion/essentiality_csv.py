"""Parse an essentiality CSV/TSV upload into EssentialityImportRecords.

Header-driven, delimiter auto-detected (tab or comma). Required: a locus column
(locus/locus_tag/orf/gene) and a call column (call/classification/essentiality/
final call/state). Optional: condition, method, confidence, pmid, dataset.
"""

from __future__ import annotations

import csv
import io

from protcellar.application.target_biology.bulk_upsert_essentiality import (
    EssentialityImportRecord,
)

_LOCUS = ("locus", "locus_tag", "orf", "gene", "gene_id")
_CALL = ("call", "classification", "essentiality", "essentiality call", "final call", "state")
_CONDITION = ("condition",)
_METHOD = ("method",)
_CONFIDENCE = ("confidence",)
_PMID = ("pmid",)
_DATASET = ("dataset", "source")


def parse_essentiality_csv(text: str) -> list[EssentialityImportRecord]:
    text = text.strip()
    if not text:
        return []
    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []
    header = [h.strip().lower() for h in rows[0]]

    def col(aliases: tuple[str, ...]) -> int | None:
        return next((i for i, h in enumerate(header) if h in aliases), None)

    i_locus, i_call = col(_LOCUS), col(_CALL)
    if i_locus is None or i_call is None:
        raise ValueError("essentiality file must have a locus column and a call column")
    i_cond, i_meth, i_conf = col(_CONDITION), col(_METHOD), col(_CONFIDENCE)
    i_pmid, i_ds = col(_PMID), col(_DATASET)

    def cell(row: list[str], idx: int | None) -> str | None:
        if idx is None or idx >= len(row):
            return None
        value = row[idx].strip()
        return value or None

    records: list[EssentialityImportRecord] = []
    for row in rows[1:]:
        locus, call = cell(row, i_locus), cell(row, i_call)
        if not locus or not call:
            continue
        conf = cell(row, i_conf)
        records.append(
            EssentialityImportRecord(
                locus_key=locus,
                classification=call,
                condition=cell(row, i_cond),
                method=cell(row, i_meth),
                confidence=float(conf) if conf else None,
                pmid=cell(row, i_pmid),
                dataset=cell(row, i_ds),
            )
        )
    return records
