"""Parse a hypomorph CSV/TSV upload into HypomorphImportRecords.

Required: a locus column and a growth_defect column (growth_defect/defect/
has_defect). Optional: severity, condition, method, pmid, dataset.
"""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_hypomorph import HypomorphImportRecord
from protcellar.infrastructure.ingestion.csv_table import CsvTable


def parse_hypomorph_csv(text: str) -> list[HypomorphImportRecord]:
    t = CsvTable(text)
    if not t.header:
        return []
    i_locus = t.require("locus", "locus_tag", "orf", "gene", "gene_id")
    i_defect = t.require("growth_defect", "defect", "has_defect")
    i_sev = t.col("severity", "growth_defect_severity")
    i_cond, i_meth = t.col("condition"), t.col("method")
    i_pmid, i_ds = t.col("pmid"), t.col("dataset", "source")

    records: list[HypomorphImportRecord] = []
    for row in t.data_rows:
        locus = t.cell(row, i_locus)
        if not locus:
            continue
        records.append(
            HypomorphImportRecord(
                locus_key=locus,
                growth_defect=t.as_bool(t.cell(row, i_defect)),
                growth_defect_severity=t.cell(row, i_sev),
                condition=t.cell(row, i_cond),
                method=t.cell(row, i_meth),
                pmid=t.cell(row, i_pmid),
                dataset=t.cell(row, i_ds),
            )
        )
    return records
