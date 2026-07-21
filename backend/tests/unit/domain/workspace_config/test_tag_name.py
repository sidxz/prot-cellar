import pytest

from protcellar.domain.workspace_config.tagging.tag import TagName


def test_key_required_and_trimmed():
    assert TagName(key="  Priority  ").key == "Priority"
    with pytest.raises(ValueError):
        TagName(key="   ")


def test_value_optional_blank_becomes_none():
    assert TagName(key="k", value="  ").value is None
    assert TagName(key="k").value is None


def test_normalized_is_casefolded():
    n = TagName(key="Priority", value="High")
    assert n.normalized_key == "priority"
    assert n.normalized_value == "high"


def test_length_limits():
    with pytest.raises(ValueError):
        TagName(key="k" * 129)
    with pytest.raises(ValueError):
        TagName(key="k", value="v" * 257)


def test_control_chars_rejected():
    with pytest.raises(ValueError):
        TagName(key="a\x00b")
