from protcellar.domain.taxonomy.enums import KNOWN_RANKS, NameClass


def test_known_ranks_contains_species() -> None:
    assert "species" in KNOWN_RANKS


def test_name_class_values() -> None:
    assert NameClass.UNIPROT_MNEMONIC.value == "uniprot_mnemonic"
