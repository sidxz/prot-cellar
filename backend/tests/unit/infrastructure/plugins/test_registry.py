import pytest

from protcellar.infrastructure.plugins.registry import all_manifests, get_plugin


def test_dejesus_is_registered() -> None:
    assert get_plugin("dejesus_essentiality").manifest().id == "dejesus_essentiality"


def test_unknown_plugin_raises() -> None:
    with pytest.raises(KeyError):
        get_plugin("does_not_exist")


def test_all_manifests_includes_dejesus() -> None:
    ids = {m.id for m in all_manifests()}
    assert "dejesus_essentiality" in ids
