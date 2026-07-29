"""Unit tests for GetGeneNeighborhood.

The essentiality call in each neighbour summary is read from target-biology
``Essentiality`` records (the plugin's home), not a legacy gene annotation.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from protcellar.application.protein_catalog.get_gene_neighborhood import (
    GetGeneNeighborhood,
    GetGeneNeighborhoodQuery,
    _consensus_essentiality,
)
from protcellar.domain.target_biology.enums import EssentialityClass
from tests.fakes.fake_auth import FakeAuth


class _FakeUoW:
    async def __aenter__(self) -> _FakeUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


def _gene(gid: uuid.UUID, name: str, *, organism: uuid.UUID, start: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=gid,
        primary_name=name,
        ordered_locus_names=[],
        orf_names=[],
        organism_id=organism,
        genomic_accession="NC_000962.3",
        genomic_start=start,
        genomic_end=start + 100,
        genomic_strand="+",
    )


class _FakeGeneRepo:
    def __init__(self, anchor: SimpleNamespace, neighbors: list[SimpleNamespace]) -> None:
        self._anchor = anchor
        self._neighbors = neighbors

    async def find_by_id_in_workspace(
        self, _ws: uuid.UUID, gid: uuid.UUID
    ) -> SimpleNamespace | None:
        return self._anchor if gid == self._anchor.id else None

    async def find_genomic_neighbors(self, **_kw: object) -> list[SimpleNamespace]:
        return self._neighbors


class _FakeEssRepo:
    def __init__(self, by_gene: dict[uuid.UUID, list[SimpleNamespace]]) -> None:
        self._by_gene = by_gene

    async def find_by_gene(self, _ws: uuid.UUID, gene_id: uuid.UUID) -> list[SimpleNamespace]:
        return self._by_gene.get(gene_id, [])


@pytest.mark.asyncio
async def test_essentiality_comes_from_target_biology_records() -> None:
    org = uuid.uuid4()
    anchor = _gene(uuid.uuid4(), "Rv0667", organism=org, start=100)
    n_has = _gene(uuid.uuid4(), "Rv0668", organism=org, start=200)
    n_none = _gene(uuid.uuid4(), "Rv0669", organism=org, start=300)
    ess = {n_has.id: [SimpleNamespace(classification=EssentialityClass.ESSENTIAL)]}

    uc = GetGeneNeighborhood(_FakeUoW(), _FakeGeneRepo(anchor, [n_has, n_none]), _FakeEssRepo(ess))
    result = await uc(GetGeneNeighborhoodQuery(gene_id=anchor.id), auth=FakeAuth(role="admin"))

    by_name = {s.primary_name: s for s in result.unwrap().neighbors}
    assert by_name["Rv0668"].essentiality == "essential"  # from the target-biology record
    assert by_name["Rv0669"].essentiality is None  # no record -> no call


def _rec(cls: EssentialityClass) -> SimpleNamespace:
    return SimpleNamespace(classification=cls)


def test_consensus_essentiality_is_modal_with_severity_tiebreak() -> None:
    assert _consensus_essentiality([]) is None
    assert _consensus_essentiality([_rec(EssentialityClass.ESSENTIAL)]) == "essential"
    # the modal call wins
    assert (
        _consensus_essentiality(
            [
                _rec(EssentialityClass.ESSENTIAL),
                _rec(EssentialityClass.ESSENTIAL),
                _rec(EssentialityClass.NON_ESSENTIAL),
            ]
        )
        == "essential"
    )
    # a modal tie breaks toward the more severe call
    assert (
        _consensus_essentiality(
            [_rec(EssentialityClass.NON_ESSENTIAL), _rec(EssentialityClass.ESSENTIAL)]
        )
        == "essential"
    )
    assert (
        _consensus_essentiality(
            [_rec(EssentialityClass.GROWTH_ADVANTAGE), _rec(EssentialityClass.GROWTH_DEFECT)]
        )
        == "growth_defect"
    )


@pytest.mark.asyncio
async def test_missing_anchor_returns_failure() -> None:
    anchor = _gene(uuid.uuid4(), "x", organism=uuid.uuid4(), start=1)
    uc = GetGeneNeighborhood(_FakeUoW(), _FakeGeneRepo(anchor, []), _FakeEssRepo({}))
    result = await uc(GetGeneNeighborhoodQuery(gene_id=uuid.uuid4()), auth=FakeAuth(role="admin"))
    assert result.failure() is not None
