"""Parse a resistance-mutation CSV/TSV upload into ResistanceMutationImportRecords.

Required: a locus column and a mutation column. Optional: compound_id (a
chem-cellar UUID), compound_name, mic_shift, parent_strain, protein_coordinate,
method, pmid, dataset.
"""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_resistance_mutation import (
    ResistanceMutationImportRecord,
)
from protcellar.infrastructure.ingestion.csv_table import CsvTable


def parse_resistance_mutation_csv(text: str) -> list[ResistanceMutationImportRecord]:
    t = CsvTable(text)
    if not t.header:
        return []
    i_locus = t.require("locus", "locus_tag", "orf", "gene", "gene_id")
    i_mut = t.require("mutation", "variant")
    i_cid, i_cname = t.col("compound_id"), t.col("compound_name", "compound")
    i_mic = t.col("mic_shift", "mic_fold", "fold")
    i_parent, i_coord = t.col("parent_strain"), t.col("protein_coordinate", "residue")
    i_meth, i_pmid, i_ds = t.col("method"), t.col("pmid"), t.col("dataset", "source")

    records: list[ResistanceMutationImportRecord] = []
    for row in t.data_rows:
        locus, mutation = t.cell(row, i_locus), t.cell(row, i_mut)
        if not locus or not mutation:
            continue
        mic = t.cell(row, i_mic)
        records.append(
            ResistanceMutationImportRecord(
                locus_key=locus,
                mutation=mutation,
                compound_id=t.as_uuid(t.cell(row, i_cid)),
                compound_name=t.cell(row, i_cname),
                mic_shift=float(mic) if mic else None,
                parent_strain=t.cell(row, i_parent),
                protein_coordinate=t.cell(row, i_coord),
                method=t.cell(row, i_meth),
                pmid=t.cell(row, i_pmid),
                dataset=t.cell(row, i_ds),
            )
        )
    return records
