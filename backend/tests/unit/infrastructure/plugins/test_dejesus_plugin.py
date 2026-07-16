import importlib
import uuid

import pytest

from protcellar.application.imports.progress_reporter import NoopProgressReporter
from protcellar.application.plugins.context import PluginRunContext
from protcellar.infrastructure.plugins.dejesus_essentiality import plugin
from tests.fakes.fake_auth import FakeAuth


class _FakeSink:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list]] = []

    async def upsert(self, record_type: str, records):
        self.upserts.append((record_type, list(records)))
        return []


async def _load_upload(_ref: uuid.UUID) -> bytes:
    return b"unused - parser is monkeypatched"


def test_manifest_shape() -> None:
    m = plugin.manifest()
    assert m.id == "dejesus_essentiality"
    assert m.target_records == ("essentiality",)
    assert {p.key for p in m.params} == {"organism_id", "upload", "condition"}


@pytest.mark.asyncio
async def test_run_maps_records_with_dejesus_citation(monkeypatch) -> None:
    # NB: target the submodule object directly, not the dotted string form.
    # __init__.py re-exports the `plugin` instance under the same name as the
    # `plugin` submodule, so the package's `.plugin` attribute resolves to the
    # instance once imported — pytest's string-based monkeypatch.setattr walks
    # attributes via getattr and would silently patch the instance instead of
    # the module, then fail with AttributeError looking up parse_dejesus_essentiality.
    plugin_module = importlib.import_module(
        "protcellar.infrastructure.plugins.dejesus_essentiality.plugin"
    )
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
    await plugin.run(ctx)
    record_type, records = sink.upserts[0]
    assert record_type == "essentiality"
    assert {r.locus_key for r in records} == {"Rv0667", "Rv0668"}
    assert all(r.pmid == "28096490" for r in records)
    assert all(r.dataset == "DeJesus 2017" for r in records)
    assert all(r.condition == "7H9" for r in records)
