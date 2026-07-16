import uuid

import pytest
from returns.result import Success

from protcellar.application.target_biology._import_support import ItemResult
from protcellar.application.target_biology.bulk_upsert_essentiality import (
    BulkUpsertEssentialityCommand,
    EssentialityImportRecord,
)
from protcellar.infrastructure.plugins.in_tree_sink import InTreeSink
from tests.fakes.fake_auth import FakeAuth


class _FakeEssentiality:
    def __init__(self) -> None:
        self.commands: list[BulkUpsertEssentialityCommand] = []

    async def __call__(self, cmd: BulkUpsertEssentialityCommand, auth=None):
        self.commands.append(cmd)
        return Success([ItemResult(index=0, status="created", id="abc")])


def _sink(
    fake: _FakeEssentiality, *, organism_id: uuid.UUID | None, run_id: uuid.UUID
) -> InTreeSink:
    return InTreeSink(
        essentiality=fake,  # type: ignore[arg-type]
        organism_id=organism_id,
        generation_method="imported",
        source_run_id=run_id,
        dry_run=False,
        auth=FakeAuth(role="admin"),
    )


@pytest.mark.asyncio
async def test_essentiality_upsert_stamps_and_accumulates() -> None:
    fake = _FakeEssentiality()
    org, run_id = uuid.uuid4(), uuid.uuid4()
    sink = _sink(fake, organism_id=org, run_id=run_id)
    out = await sink.upsert(
        "essentiality", [EssentialityImportRecord(locus_key="rpoB", classification="ES")]
    )
    assert [r.status for r in out] == ["created"]
    assert sink.results == out
    cmd = fake.commands[0]
    assert cmd.organism_id == org
    assert cmd.generation_method == "imported"
    assert cmd.source_run_id == run_id
    assert cmd.dry_run is False


@pytest.mark.asyncio
async def test_unknown_record_type_raises() -> None:
    sink = _sink(_FakeEssentiality(), organism_id=uuid.uuid4(), run_id=uuid.uuid4())
    with pytest.raises(ValueError):
        await sink.upsert("nope", [])


@pytest.mark.asyncio
async def test_essentiality_without_organism_raises() -> None:
    sink = _sink(_FakeEssentiality(), organism_id=None, run_id=uuid.uuid4())
    with pytest.raises(ValueError):
        await sink.upsert("essentiality", [])
