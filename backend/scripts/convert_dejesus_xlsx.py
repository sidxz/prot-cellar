"""Convert the DeJesus 2017 essentiality Table S3 (XLSX) into a TSV for import.

The DeJesus 2017 (mBio, PMID:28096490) per-ORF essentiality calls are published
as supplementary "Table S3" — an XLSX whose sheet "ORF Essentiality Calls" has the
Rv locus in column A ("ORF ID") and the HMM call in column M ("Final Call":
ES / ESD / GD / NE / GA / uncertain).

Sourcing (open access, no JS gate — unlike the PMC bin/ URLs):

    curl -sL "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5241402/supplementaryFiles" -o suppl.zip
    unzip -o suppl.zip 'mbo002173137st3.xlsx' -d dejesus

Then:

    uv run --with openpyxl python scripts/convert_dejesus_xlsx.py dejesus/mbo002173137st3.xlsx dejesus_essentiality.tsv
    uv run python -m protcellar.scripts.enrich_genes --tax-id 83332 --essentiality-file dejesus_essentiality.tsv

The emitted TSV (header ``ORF ID\tFinal Call``) is consumed by
``parse_dejesus_essentiality`` (it auto-detects the "Final Call" column and
defaults the locus to column 0). Idempotent end-to-end.
"""

from __future__ import annotations

import sys

import openpyxl

_ORF_COL = 0  # column A
_CALL_COL = 12  # column M ("Final Call")
_DATA_START_ROW = 3  # row 1 = title, row 2 = header, data from row 3 (1-indexed)


def convert(xlsx_path: str, out_path: str) -> int:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    lines = ["ORF ID\tFinal Call"]
    for row in ws.iter_rows(min_row=_DATA_START_ROW, values_only=True):
        orf, call = row[_ORF_COL], row[_CALL_COL]
        if orf and str(orf).strip():
            lines.append(f"{str(orf).strip()}\t{str(call).strip() if call else ''}")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return len(lines) - 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: convert_dejesus_xlsx.py <table_s3.xlsx> <out.tsv>")
    n = convert(sys.argv[1], sys.argv[2])
    print(f"wrote {n} rows to {sys.argv[2]}")
