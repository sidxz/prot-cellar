import uuid

import pytest

from protcellar.infrastructure.ingestion.crispri_strain_csv import parse_crispri_strain_csv
from protcellar.infrastructure.ingestion.resistance_mutation_csv import (
    parse_resistance_mutation_csv,
)


def test_resistance_parse_with_compound_uuid() -> None:
    cid = uuid.uuid4()
    text = f"locus\tmutation\tcompound_id\tmic_shift\nkatG\tS315T\t{cid}\t64"
    recs = parse_resistance_mutation_csv(text)
    assert len(recs) == 1
    assert recs[0].mutation == "S315T"
    assert recs[0].compound_id == cid
    assert recs[0].mic_shift == 64.0


def test_resistance_bad_compound_uuid_is_none() -> None:
    recs = parse_resistance_mutation_csv("locus\tmutation\tcompound_id\nkatG\tS315T\tnot-a-uuid")
    assert recs[0].compound_id is None


def test_resistance_requires_mutation_column() -> None:
    with pytest.raises(ValueError):
        parse_resistance_mutation_csv("locus\nkatG")


def test_crispri_parse() -> None:
    recs = parse_crispri_strain_csv("target_gene\tname\nrpoB\tsgRNA-rpoB-1")
    assert len(recs) == 1
    assert recs[0].locus_key == "rpoB"
    assert recs[0].name == "sgRNA-rpoB-1"


def test_crispri_requires_name() -> None:
    with pytest.raises(ValueError):
        parse_crispri_strain_csv("locus\nrpoB")
