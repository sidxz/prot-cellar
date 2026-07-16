import pytest

from protcellar.infrastructure.ingestion.hypomorph_csv import parse_hypomorph_csv


def test_parse_bool_and_severity() -> None:
    text = (
        "locus\tgrowth_defect\tseverity\tmethod\n"
        "Rv0667\tyes\tsevere\tCRISPRi\n"
        "Rv1908c\tno\t\tCRISPRi"
    )
    recs = parse_hypomorph_csv(text)
    assert len(recs) == 2
    assert recs[0].growth_defect is True
    assert recs[0].growth_defect_severity == "severe"
    assert recs[1].growth_defect is False
    assert recs[1].growth_defect_severity is None


def test_unrecognised_defect_is_false() -> None:
    recs = parse_hypomorph_csv("locus\tgrowth_defect\nRv0667\t")
    assert recs[0].growth_defect is False


def test_missing_defect_column_raises() -> None:
    with pytest.raises(ValueError):
        parse_hypomorph_csv("locus\nRv0667")
