"""Parse a CRISPRi-strain CSV/TSV upload into CrispriStrainImportRecords.

Required: a locus column (the target gene) and a name column (name/strain).
Optional: pmid, dataset.
"""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_crispri_strain import (
    CrispriStrainImportRecord,
)
from protcellar.infrastructure.ingestion.csv_table import CsvTable


def parse_crispri_strain_csv(text: str) -> list[CrispriStrainImportRecord]:
    t = CsvTable(text)
    if not t.header:
        return []
    i_locus = t.require("locus", "locus_tag", "orf", "gene", "target_gene", "gene_id")
    i_name = t.require("name", "strain", "strain_name")
    i_pmid, i_ds = t.col("pmid"), t.col("dataset", "source")

    records: list[CrispriStrainImportRecord] = []
    for row in t.data_rows:
        locus, name = t.cell(row, i_locus), t.cell(row, i_name)
        if not locus or not name:
            continue
        records.append(
            CrispriStrainImportRecord(
                locus_key=locus,
                name=name,
                pmid=t.cell(row, i_pmid),
                dataset=t.cell(row, i_ds),
            )
        )
    return records
