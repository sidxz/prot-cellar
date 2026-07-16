"""Parse an unpublished-structure CSV/TSV upload into UnpublishedStructureImportRecords.

Required: an accession column. Optional: method, resolution, ligand_ids
(a ;/,-separated list of chem-cellar UUIDs), is_published, is_experimental,
pmid, dataset.
"""

from __future__ import annotations

import re
import uuid

from protcellar.application.target_biology.bulk_upsert_unpublished_structure import (
    UnpublishedStructureImportRecord,
)
from protcellar.infrastructure.ingestion.csv_table import CsvTable


def _uuids(value: str | None) -> tuple[uuid.UUID, ...]:
    if not value:
        return ()
    parsed = (CsvTable.as_uuid(part.strip()) for part in re.split(r"[;,]", value))
    return tuple(u for u in parsed if u is not None)


def parse_unpublished_structure_csv(text: str) -> list[UnpublishedStructureImportRecord]:
    t = CsvTable(text)
    if not t.header:
        return []
    i_acc = t.require("accession", "protein", "uniprot")
    i_meth, i_res = t.col("method"), t.col("resolution")
    i_lig = t.col("ligand_ids", "ligands")
    i_pub, i_exp = t.col("is_published", "published"), t.col("is_experimental", "experimental")
    i_pmid, i_ds = t.col("pmid"), t.col("dataset", "source")

    records: list[UnpublishedStructureImportRecord] = []
    for row in t.data_rows:
        acc = t.cell(row, i_acc)
        if not acc:
            continue
        res = t.cell(row, i_res)
        records.append(
            UnpublishedStructureImportRecord(
                accession=acc,
                method=t.cell(row, i_meth),
                resolution=float(res) if res else None,
                ligand_ids=_uuids(t.cell(row, i_lig)),
                is_published=t.as_bool(t.cell(row, i_pub)),
                is_experimental=(
                    t.as_bool(t.cell(row, i_exp)) if i_exp is not None else True
                ),
                pmid=t.cell(row, i_pmid),
                dataset=t.cell(row, i_ds),
            )
        )
    return records
