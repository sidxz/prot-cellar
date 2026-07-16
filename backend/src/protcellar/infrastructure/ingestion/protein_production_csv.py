"""Parse a protein-production CSV/TSV upload into ProteinProductionImportRecords.

Required: an accession column and a status column. Optional: expression_host,
purity, condition, method, pmid, dataset.
"""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_protein_production import (
    ProteinProductionImportRecord,
)
from protcellar.infrastructure.ingestion.csv_table import CsvTable


def parse_protein_production_csv(text: str) -> list[ProteinProductionImportRecord]:
    t = CsvTable(text)
    if not t.header:
        return []
    i_acc = t.require("accession", "protein", "uniprot")
    i_status = t.require("status")
    i_host = t.col("expression_host", "host")
    i_purity = t.col("purity")
    i_cond, i_meth = t.col("condition"), t.col("method")
    i_pmid, i_ds = t.col("pmid"), t.col("dataset", "source")

    records: list[ProteinProductionImportRecord] = []
    for row in t.data_rows:
        acc, status = t.cell(row, i_acc), t.cell(row, i_status)
        if not acc or not status:
            continue
        purity = t.cell(row, i_purity)
        records.append(
            ProteinProductionImportRecord(
                accession=acc,
                status=status,
                expression_host=t.cell(row, i_host),
                purity=float(purity) if purity else None,
                condition=t.cell(row, i_cond),
                method=t.cell(row, i_meth),
                pmid=t.cell(row, i_pmid),
                dataset=t.cell(row, i_ds),
            )
        )
    return records
