"""Parse a protein-activity-assay CSV/TSV upload into ProteinActivityAssayImportRecords.

Required: an accession column and an activity column (activity/activity_measured).
Optional: readout, throughput, condition, method, pmid, dataset.
"""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_protein_activity_assay import (
    ProteinActivityAssayImportRecord,
)
from protcellar.infrastructure.ingestion.csv_table import CsvTable


def parse_protein_activity_assay_csv(text: str) -> list[ProteinActivityAssayImportRecord]:
    t = CsvTable(text)
    if not t.header:
        return []
    i_acc = t.require("accession", "protein", "uniprot")
    i_act = t.require("activity", "activity_measured")
    i_read, i_tp = t.col("readout"), t.col("throughput")
    i_cond, i_meth = t.col("condition"), t.col("method")
    i_pmid, i_ds = t.col("pmid"), t.col("dataset", "source")

    records: list[ProteinActivityAssayImportRecord] = []
    for row in t.data_rows:
        acc, act = t.cell(row, i_acc), t.cell(row, i_act)
        if not acc or not act:
            continue
        records.append(
            ProteinActivityAssayImportRecord(
                accession=acc,
                activity_measured=act,
                readout=t.cell(row, i_read),
                throughput=t.cell(row, i_tp),
                condition=t.cell(row, i_cond),
                method=t.cell(row, i_meth),
                pmid=t.cell(row, i_pmid),
                dataset=t.cell(row, i_ds),
            )
        )
    return records
