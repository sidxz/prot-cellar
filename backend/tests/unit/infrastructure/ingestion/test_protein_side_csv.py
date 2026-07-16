import uuid

import pytest

from protcellar.infrastructure.ingestion.protein_activity_assay_csv import (
    parse_protein_activity_assay_csv,
)
from protcellar.infrastructure.ingestion.protein_production_csv import (
    parse_protein_production_csv,
)
from protcellar.infrastructure.ingestion.unpublished_structure_csv import (
    parse_unpublished_structure_csv,
)


def test_production_parse() -> None:
    text = "accession\tstatus\texpression_host\tpurity\nP9WGE9\tproduced\tE. coli\t95"
    recs = parse_protein_production_csv(text)
    assert recs[0].accession == "P9WGE9"
    assert recs[0].status == "produced"
    assert recs[0].purity == 95.0


def test_production_requires_status() -> None:
    with pytest.raises(ValueError):
        parse_protein_production_csv("accession\nP9WGE9")


def test_activity_parse() -> None:
    recs = parse_protein_activity_assay_csv(
        "accession,activity,readout\nP9WGE9,ATPase,fluorescence"
    )
    assert recs[0].activity_measured == "ATPase"
    assert recs[0].readout == "fluorescence"


def test_structure_parse_ligands_and_experimental_default() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    text = f"accession\tmethod\tresolution\tligand_ids\nP9WGE9\tX-ray\t1.9\t{a};{b}"
    recs = parse_unpublished_structure_csv(text)
    assert recs[0].resolution == 1.9
    assert set(recs[0].ligand_ids) == {a, b}
    assert recs[0].is_experimental is True  # default when column absent
    assert recs[0].is_published is False
