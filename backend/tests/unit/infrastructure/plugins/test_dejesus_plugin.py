import uuid

import pytest

from protcellar.application.imports.progress_reporter import NoopProgressReporter
from protcellar.application.plugins.context import PluginRunContext
from protcellar.infrastructure.plugins.dejesus_essentiality import plugin as plugin_module
from tests.fakes.fake_auth import FakeAuth

PLUGIN = plugin_module.PLUGIN


class _FakeSink:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list]] = []

    async def upsert(self, record_type: str, records):
        self.upserts.append((record_type, list(records)))
        return []


async def _load_upload(_ref: uuid.UUID) -> bytes:
    return b"unused - parser is monkeypatched"


def test_manifest_shape() -> None:
    m = PLUGIN.manifest()
    assert m.id == "dejesus_essentiality"
    assert m.target_records == ("essentiality",)
    assert {p.key for p in m.params} == {"organism_id", "upload", "condition"}


@pytest.mark.asyncio
async def test_run_maps_records_with_dejesus_citation(monkeypatch) -> None:
    # Patch the parser on the plugin submodule. PLUGIN is the instance and the
    # module also holds parse_dejesus_essentiality — distinct names, nothing aliased.
    monkeypatch.setattr(
        plugin_module,
        "parse_dejesus_essentiality",
        lambda text: {"Rv0667": "essential", "Rv0668": "non-essential"},
    )
    sink = _FakeSink()
    ctx = PluginRunContext(
        params={
            "upload_ref": str(uuid.uuid4()),
            "organism_id": str(uuid.uuid4()),
            "condition": "7H9",
        },
        organism_id=uuid.uuid4(),
        load_upload=_load_upload,
        sink=sink,
        reporter=NoopProgressReporter(),
        auth=FakeAuth(role="admin"),
    )
    await PLUGIN.run(ctx)
    record_type, records = sink.upserts[0]
    assert record_type == "essentiality"
    assert {r.locus_key for r in records} == {"Rv0667", "Rv0668"}
    assert all(r.pmid == "28096490" for r in records)
    assert all(r.dataset == "DeJesus 2017" for r in records)
    assert all(r.condition == "7H9" for r in records)
