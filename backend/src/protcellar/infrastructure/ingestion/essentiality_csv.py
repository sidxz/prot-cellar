"""Parse an essentiality CSV/TSV upload into EssentialityImportRecords.

Required: a locus column (locus/locus_tag/orf/gene) and a call column
(call/classification/essentiality/final call/state). Optional: condition, method,
confidence, pmid, dataset.
"""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_essentiality import (
    EssentialityImportRecord,
)
from protcellar.infrastructure.ingestion.csv_table import CsvTable


def parse_essentiality_csv(text: str) -> list[EssentialityImportRecord]:
    t = CsvTable(text)
    if not t.header:
        return []
    i_locus = t.require("locus", "locus_tag", "orf", "gene", "gene_id")
    i_call = t.require(
        "call", "classification", "essentiality", "essentiality call", "final call", "state"
    )
    i_cond, i_meth, i_conf = t.col("condition"), t.col("method"), t.col("confidence")
    i_pmid, i_ds = t.col("pmid"), t.col("dataset", "source")

    records: list[EssentialityImportRecord] = []
    for row in t.data_rows:
        locus, call = t.cell(row, i_locus), t.cell(row, i_call)
        if not locus or not call:
            continue
        conf = t.cell(row, i_conf)
        records.append(
            EssentialityImportRecord(
                locus_key=locus,
                classification=call,
                condition=t.cell(row, i_cond),
                method=t.cell(row, i_meth),
                confidence=float(conf) if conf else None,
                pmid=t.cell(row, i_pmid),
                dataset=t.cell(row, i_ds),
            )
        )
    return records
