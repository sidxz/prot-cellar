"""The two rules that are not obvious: name is immutable, options belong to enums."""

from __future__ import annotations

import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)

WS = uuid.uuid4()


def _def(**kw: object) -> ExtensionFieldDef:
    base = dict(
        workspace_id=WS,
        kind="vulnerability",
        name="vi_lower_bound",
        label="VI lower bound",
        field_type=ExtensionFieldType.NUMBER,
        options=None,
        position=0,
        show_in_table=False,
    )
    base.update(kw)
    return ExtensionFieldDef.create(**base)  # type: ignore[arg-type]


def test_name_is_immutable_after_creation() -> None:
    d = _def()
    with pytest.raises(AttributeError):
        d.name = "something_else"  # type: ignore[misc]


def test_update_changes_label_and_shape_but_not_name() -> None:
    d = _def()
    d.update(
        label="Lower bound",
        field_type=ExtensionFieldType.STRING,
        options=None,
        position=3,
        show_in_table=True,
    )
    assert (d.name, d.label, d.position, d.show_in_table) == (
        "vi_lower_bound",
        "Lower bound",
        3,
        True,
    )


def test_enum_requires_options() -> None:
    with pytest.raises(ValidationError):
        _def(field_type=ExtensionFieldType.ENUM, options=None)
    with pytest.raises(ValidationError):
        _def(field_type=ExtensionFieldType.ENUM, options=[])


def test_non_enum_rejects_options() -> None:
    with pytest.raises(ValidationError):
        _def(field_type=ExtensionFieldType.NUMBER, options=["a"])


@pytest.mark.parametrize("bad", ["", "  ", "has space", "Has-Dash", "1leading"])
def test_name_must_be_a_snake_case_identifier(bad: str) -> None:
    with pytest.raises(ValidationError):
        _def(name=bad)
