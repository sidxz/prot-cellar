from protcellar.domain.shared.cross_reference import CrossReference


def test_curie() -> None:
    xref = CrossReference(database="uniprot", accession="P0DTC2")
    assert xref.to_curie() == "uniprot:P0DTC2"
