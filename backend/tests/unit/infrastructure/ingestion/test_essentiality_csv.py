import pytest

from protcellar.infrastructure.ingestion.essentiality_csv import parse_essentiality_csv


def test_parse_tsv_with_optional_columns() -> None:
    text = "Locus\tFinal Call\tMethod\tPMID\nRv0667\tES\tTnSeq\t28096490\nRv1908c\tNE\tTnSeq\t"
    recs = parse_essentiality_csv(text)
    assert len(recs) == 2
    assert recs[0].locus_key == "Rv0667"
    assert recs[0].classification == "ES"
    assert recs[0].method == "TnSeq"
    assert recs[0].pmid == "28096490"
    assert recs[1].pmid is None  # empty cell -> None


def test_parse_csv_delimiter() -> None:
    recs = parse_essentiality_csv("locus,classification\nRv0001,essential")
    assert len(recs) == 1 and recs[0].locus_key == "Rv0001"
    assert recs[0].classification == "essential"


def test_missing_required_columns_raises() -> None:
    with pytest.raises(ValueError):
        parse_essentiality_csv("foo\tbar\n1\t2")


def test_blank_rows_skipped() -> None:
    text = "locus\tcall\nRv0667\tES\n\n\t\nRv1908c\tNE"
    recs = parse_essentiality_csv(text)
    assert [r.locus_key for r in recs] == ["Rv0667", "Rv1908c"]
