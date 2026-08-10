"""API tests for the Proteome endpoints."""

from __future__ import annotations

import random

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_proteome(client: AsyncClient) -> None:
    # Create an organism first (use a unique tax_id)
    org_resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": 7227,
            "rank": "species",
            "scientific_name": "Drosophila melanogaster",
        },
    )
    assert org_resp.status_code == 201
    organism_id = org_resp.json()["id"]

    # Create a proteome referencing that organism
    resp = await client.post(
        "/api/v1/proteomes",
        json={
            "uniprot_proteome_id": "UP000000803",
            "organism_id": organism_id,
            "proteome_type": "reference",
            "is_reference": True,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["uniprot_proteome_id"] == "UP000000803"
    assert body["organism_id"] == organism_id
    assert body["is_reference"] is True
    assert body["proteome_url"] == "https://www.uniprot.org/proteomes/UP000000803"
    # Display name, resolved server-side from the related organism row —
    # no strain on this proteome, so strain_name stays None.
    assert body["organism_name"] == "Drosophila melanogaster"
    assert body["strain_name"] is None
    proteome_id = body["id"]

    # GET the proteome by ID
    get_resp = await client.get(f"/api/v1/proteomes/{proteome_id}")
    assert get_resp.status_code == 200
    gotten = get_resp.json()
    assert gotten["uniprot_proteome_id"] == "UP000000803"
    assert gotten["id"] == proteome_id
    assert gotten["organism_name"] == "Drosophila melanogaster"
    assert gotten["strain_name"] is None


@pytest.mark.asyncio
async def test_proteome_display_names_include_the_strain_when_pinned(
    client: AsyncClient,
) -> None:
    org_resp = await client.post(
        "/api/v1/organisms",
        json={
            # A random tax_id, not the real 83332 — that literal is already
            # reused by other test files sharing this DB across one run, and
            # collides (see test_organisms.py's own pre-existing order
            # dependency on it).
            "ncbi_tax_id": random.randint(200_000, 999_999),
            "rank": "species",
            "scientific_name": "M. tuberculosis",
        },
    )
    assert org_resp.status_code == 201
    organism_id = org_resp.json()["id"]

    strain_resp = await client.post(
        "/api/v1/strains",
        json={"species_organism_id": organism_id, "name": "ATCC 25618 / H37Rv"},
    )
    assert strain_resp.status_code == 201
    strain_id = strain_resp.json()["id"]

    resp = await client.post(
        "/api/v1/proteomes",
        json={
            "uniprot_proteome_id": "UP000001584",
            "organism_id": organism_id,
            "strain_id": strain_id,
            "proteome_type": "reference",
            "is_reference": True,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["organism_name"] == "M. tuberculosis"
    assert body["strain_name"] == "ATCC 25618 / H37Rv"

    # Same names, taken from the related rows without an extra client fetch,
    # on the list endpoint too.
    list_resp = await client.get(f"/api/v1/proteomes?organism_id={organism_id}")
    assert list_resp.status_code == 200
    item = next(p for p in list_resp.json()["items"] if p["uniprot_proteome_id"] == "UP000001584")
    assert item["organism_name"] == "M. tuberculosis"
    assert item["strain_name"] == "ATCC 25618 / H37Rv"


@pytest.mark.asyncio
async def test_list_proteomes(client: AsyncClient) -> None:
    # Create an organism
    org_resp = await client.post(
        "/api/v1/organisms",
        json={"ncbi_tax_id": 6239, "rank": "species", "scientific_name": "Caenorhabditis elegans"},
    )
    assert org_resp.status_code == 201
    organism_id = org_resp.json()["id"]

    # Create a proteome
    await client.post(
        "/api/v1/proteomes",
        json={
            "uniprot_proteome_id": "UP000001940",
            "organism_id": organism_id,
            "proteome_type": "reference",
            "is_reference": True,
        },
    )

    # List all proteomes
    list_resp = await client.get("/api/v1/proteomes")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert "items" in body
    ids = [p["uniprot_proteome_id"] for p in body["items"]]
    assert "UP000001940" in ids


@pytest.mark.asyncio
async def test_invalid_proteome_id_returns_422(client: AsyncClient) -> None:
    # Create an organism for the reference
    org_resp = await client.post(
        "/api/v1/organisms",
        json={
            "ncbi_tax_id": 4932,
            "rank": "species",
            "scientific_name": "Saccharomyces cerevisiae",
        },
    )
    assert org_resp.status_code == 201
    organism_id = org_resp.json()["id"]

    # Attempt to create a proteome with an invalid UP id
    resp = await client.post(
        "/api/v1/proteomes",
        json={
            "uniprot_proteome_id": "NOTAPROTEOME",
            "organism_id": organism_id,
            "proteome_type": "reference",
            "is_reference": True,
        },
    )
    assert resp.status_code == 422
