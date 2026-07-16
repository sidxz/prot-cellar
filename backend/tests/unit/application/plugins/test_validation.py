import pytest

from protcellar.application.plugins.manifest import ParamField, ParamType, PluginManifest
from protcellar.application.plugins.validation import validate_against_manifest
from protcellar.domain.shared.errors import ValidationError as DomainValidationError
from protcellar.domain.shared.provenance import GenerationMethod


def _manifest(*params: ParamField) -> PluginManifest:
    return PluginManifest(
        id="t",
        version="1.0.0",
        name="T",
        description="d",
        target_records=("essentiality",),
        default_generation_method=GenerationMethod.IMPORTED,
        params=tuple(params),
    )


def test_required_missing_raises() -> None:
    m = _manifest(ParamField(key="x", label="X", type=ParamType.STRING, required=True))
    with pytest.raises(DomainValidationError):
        validate_against_manifest(m, {})


def test_defaults_are_filled() -> None:
    m = _manifest(ParamField(key="force", label="F", type=ParamType.BOOL, default=False))
    assert validate_against_manifest(m, {}) == {"force": False}


def test_bool_string_false_is_false() -> None:
    m = _manifest(ParamField(key="flag", label="F", type=ParamType.BOOL, required=True))
    assert validate_against_manifest(m, {"flag": "false"}) == {"flag": False}
    assert validate_against_manifest(m, {"flag": "true"}) == {"flag": True}
    assert validate_against_manifest(m, {"flag": True}) == {"flag": True}


def test_number_is_coerced() -> None:
    m = _manifest(ParamField(key="n", label="N", type=ParamType.NUMBER, required=True))
    assert validate_against_manifest(m, {"n": "83332"}) == {"n": 83332}


def test_enum_rejects_out_of_set() -> None:
    m = _manifest(
        ParamField(key="c", label="C", type=ParamType.ENUM, options=("a", "b"), required=True)
    )
    assert validate_against_manifest(m, {"c": "a"}) == {"c": "a"}
    with pytest.raises(DomainValidationError):
        validate_against_manifest(m, {"c": "z"})


def test_unknown_keys_are_dropped() -> None:
    m = _manifest(ParamField(key="x", label="X", type=ParamType.STRING))
    assert validate_against_manifest(m, {"x": "v", "junk": 1}) == {"x": "v"}
