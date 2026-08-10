"""API tests for /api/v1/imports routes."""

from __future__ import annotations

import io
import uuid

import openpyxl
import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from protcellar.application.imports.job_enqueuer import JobEnqueuer

pytestmark = pytest.mark.asyncio


class _FakeEnqueuer:
    def __init__(self) -> None:
        self.enqueued = []

    async def enqueue_import(self, import_run_id, workspace_id) -> None:
        self.enqueued.append(import_run_id)

    async def aclose(self) -> None:
        return None


@pytest.fixture
def fake_enqueuer(api_app: FastAPI) -> _FakeEnqueuer:
    enq = _FakeEnqueuer()
    # lagom raises DuplicateDefinition on item-assignment when the type is already
    # registered, so we clone the container and re-define the binding there.
    cloned = api_app.state.container.clone()
    cloned.define(JobEnqueuer, lambda c: enq)
    api_app.state.container = cloned
    return enq


async def test_start_import_returns_202_queued_and_enqueues(
    client: AsyncClient, fake_enqueuer: object
) -> None:
    # Use a unique proteome_id so this test doesn't clash with other tests sharing the DB.
    proteome_id = f"UP{uuid.uuid4().hex[:9].upper()}"
    resp = await client.post(
        "/api/v1/imports",
        json={"import_type": "proteome", "params": {"proteome_id": proteome_id}},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["import_type"] == "proteome"
    assert len(fake_enqueuer.enqueued) == 1

    listed = await client.get("/api/v1/imports")
    assert any(r["id"] == body["id"] for r in listed.json()["items"])

    got = await client.get(f"/api/v1/imports/{body['id']}")
    assert got.json()["target_key"] == proteome_id


async def test_a_viewer_cannot_read_a_gene_enrichment_runs_params(
    client: AsyncClient, viewer_client: AsyncClient
) -> None:
    """params are write-only except for TARGET_BIOLOGY (whose preview screen
    needs them back to drive Apply) — every other import type's params, which
    can carry secrets such as a gff_url with embedded credentials, must never
    reach a reader, on either the detail or the list endpoint, and regardless
    of the caller's own role (even the admin's own create response is
    scrubbed)."""
    secret_url = "https://user:s3cr3t-token@example.com/genes.gff3"
    started = await client.post(
        "/api/v1/imports",
        json={
            "import_type": "gene_enrichment",
            "params": {"tax_id": 83332, "gff_url": secret_url},
        },
    )
    assert started.status_code == 202, started.text
    run_id = started.json()["id"]
    assert started.json()["params"] is None

    got = await viewer_client.get(f"/api/v1/imports/{run_id}")
    assert got.status_code == 200, got.text
    assert got.json()["params"] is None
    assert "s3cr3t-token" not in got.text

    listed = await viewer_client.get("/api/v1/imports")
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json()["items"] if r["id"] == run_id)
    assert row["params"] is None
    assert "s3cr3t-token" not in listed.text


async def test_duplicate_active_import_is_rejected(client: AsyncClient, fake_enqueuer) -> None:
    payload = {"import_type": "go_ontology", "params": {"force": False}}
    first = await client.post("/api/v1/imports", json=payload)
    assert first.status_code == 202
    dup = await client.post("/api/v1/imports", json=payload)
    assert dup.status_code == 409


async def test_upload_essentiality_xlsx(client: AsyncClient) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ORF ID", "Final Call"])
    ws.append(["Rv0667", "ES"])
    buf = io.BytesIO()
    wb.save(buf)
    resp = await client.post(
        "/api/v1/imports/uploads",
        files={
            "file": (
                "table_s3.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200
    assert resp.json()["upload_ref"]
