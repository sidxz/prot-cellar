"""pref_name defaulting: curators want the short gene form, not the UniProt name."""

import pytest

from protcellar.application.target.default_pref_name import component_label, default_pref_name
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.target.enums import TargetType


class _Names:
    def __init__(self, recommended: str | None) -> None:
        self.recommended = recommended


class _Protein:
    def __init__(self, accession: str, recommended: str | None = None) -> None:
        self.primary_accession = accession
        self.protein_names = _Names(recommended)


class _Gene:
    def __init__(self, primary_name: str) -> None:
        self.primary_name = primary_name


@pytest.mark.parametrize(
    "gene_name,expected",
    [("pptT", "PptT"), ("pks13", "Pks13"), ("gyrA", "GyrA"), ("clpC1", "ClpC1")],
)
def test_gene_name_is_capitalised_not_title_cased(gene_name: str, expected: str) -> None:
    assert component_label(_Protein("P00001"), _Gene(gene_name)) == expected


def test_falls_back_to_recommended_name_then_accession() -> None:
    assert component_label(_Protein("P00001", "Malate dehydrogenase"), None) == (
        "Malate dehydrogenase"
    )
    assert component_label(_Protein("P00001"), None) == "P00001"


def test_single_and_domain_and_multi_component_shapes() -> None:
    assert default_pref_name(TargetType.SINGLE_PROTEIN, ["Pks13"]) == "Pks13"
    assert default_pref_name(TargetType.DOMAIN, ["Pks13"]) == "Pks13 domain"
    assert default_pref_name(TargetType.PROTEIN_COMPLEX, ["GyrA", "GyrB"]) == "GyrA/GyrB"


def test_no_components_requires_an_explicit_name() -> None:
    with pytest.raises(ValidationError):
        default_pref_name(TargetType.ORGANISM, [])
