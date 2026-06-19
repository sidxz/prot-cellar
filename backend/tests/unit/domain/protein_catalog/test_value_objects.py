from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.value_objects import ProteinNames


def test_protein_existence_level_roundtrip() -> None:
    assert ProteinExistence.from_level(1) is ProteinExistence.PROTEIN_LEVEL
    assert ProteinExistence.PROTEIN_LEVEL.level == 1
    assert ProteinExistence.from_level(5).level == 5


def test_protein_names_to_from_dict_roundtrip() -> None:
    names = ProteinNames(recommended="Serum albumin", alternative=("Albumin",), submitted=())
    restored = ProteinNames.from_dict(names.to_dict())
    assert restored == names
    assert restored.display_name == "Serum albumin"


def test_protein_names_from_none_is_empty() -> None:
    empty = ProteinNames.from_dict(None)
    assert empty.recommended is None
    assert empty.alternative == ()
    assert empty.submitted == ()
    assert empty.display_name is None


def test_display_name_falls_back_to_submitted_then_alternative() -> None:
    assert ProteinNames(submitted=("Sub name",)).display_name == "Sub name"
    assert ProteinNames(alternative=("Alt name",)).display_name == "Alt name"
