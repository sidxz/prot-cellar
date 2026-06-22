from __future__ import annotations

import io

import openpyxl
import pytest

from protcellar.infrastructure.ingestion.dejesus_xlsx import essentiality_upload_to_tsv


def _xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ORF ID", "Name", "Final Call"])
    ws.append(["Rv0667", "rpoB", "ES"])
    ws.append(["Rv0668", "rpoC", "GD"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_to_tsv_extracts_locus_and_call() -> None:
    tsv = essentiality_upload_to_tsv("table_s3.xlsx", _xlsx_bytes())
    assert "Rv0667" in tsv and "ES" in tsv


def test_tsv_passthrough() -> None:
    tsv = essentiality_upload_to_tsv("d.tsv", b"Rv0667\tES\nRv0668\tGD\n")
    assert "Rv0667" in tsv


def test_unparseable_raises() -> None:
    with pytest.raises(ValueError):
        essentiality_upload_to_tsv("empty.tsv", b"\n\n")
