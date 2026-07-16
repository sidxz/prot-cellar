import uuid

from protcellar.application.imports.params import target_key, upload_ref_of, validate_params
from protcellar.domain.imports.enums import ImportType


def test_validate_params_plugin_passthrough() -> None:
    raw = {"plugin_id": "dejesus_essentiality", "organism_id": "x", "junk": 1}
    assert validate_params(ImportType.PLUGIN, raw) == raw


def test_target_key_includes_plugin_and_dry_flag() -> None:
    params = {"plugin_id": "dejesus_essentiality", "organism_id": "org-1", "dry_run": True}
    assert target_key(ImportType.PLUGIN, params) == "dejesus_essentiality:org-1:dry"
    params["dry_run"] = False
    assert target_key(ImportType.PLUGIN, params) == "dejesus_essentiality:org-1:run"


def test_upload_ref_of_reads_upload_ref() -> None:
    ref = uuid.uuid4()
    assert upload_ref_of(ImportType.PLUGIN, {"upload_ref": str(ref)}) == ref
    assert upload_ref_of(ImportType.PLUGIN, {"plugin_id": "x"}) is None
