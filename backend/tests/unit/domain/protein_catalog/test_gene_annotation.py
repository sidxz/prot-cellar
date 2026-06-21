import pytest

from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.domain.shared.errors import ValidationError


def test_create_vulnerability_annotation() -> None:
    a = GeneAnnotation(
        axis=GeneAnnotationAxis.VULNERABILITY,
        key="essentiality",
        value="essential",
        dataset="DeJesus 2017",
        condition="in vitro 7H9",
        evidence="PMID:28096490",
    )
    assert a.axis is GeneAnnotationAxis.VULNERABILITY
    assert a.value == "essential"
    assert a.value_type == "categorical"  # default


def test_axis_is_string_enum() -> None:
    assert GeneAnnotationAxis.VULNERABILITY == "vulnerability"


def test_key_and_value_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        GeneAnnotation(axis=GeneAnnotationAxis.CONTEXT, key="  ", value="x")
    with pytest.raises(ValidationError):
        GeneAnnotation(axis=GeneAnnotationAxis.CONTEXT, key="functional_category", value="")


def test_is_frozen() -> None:
    a = GeneAnnotation(axis=GeneAnnotationAxis.CONTEXT, key="functional_category", value="Cell wall")
    with pytest.raises(Exception):
        a.value = "other"  # type: ignore[misc]
