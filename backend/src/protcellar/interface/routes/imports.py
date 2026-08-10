"""Import runs + file upload endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from protcellar.application.imports.get_import_run import GetImportRunQuery
from protcellar.application.imports.list_import_runs import ListImportRunsQuery
from protcellar.application.imports.start_import import StartImportCommand
from protcellar.domain.imports.enums import ImportStatus, ImportType
from protcellar.domain.imports.import_run import ImportRun
from protcellar.infrastructure.ingestion.dejesus_xlsx import essentiality_upload_to_tsv
from protcellar.interface.dependencies import (
    AuthDep,
    GetImportRunDep,
    ListImportRunsDep,
    StartImportDep,
    StoreUploadDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import PaginatedResponse, clamp_limit

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


class ImportRunResponse(BaseModel):
    id: uuid.UUID
    import_type: ImportType
    target_key: str
    status: ImportStatus
    phase: str | None = None
    progress: dict[str, Any]
    summary: dict[str, Any]
    params: dict[str, Any]
    source_version: str | None = None
    error: str | None = None
    requested_by: uuid.UUID
    upload_ref: uuid.UUID | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def from_domain(cls, run: ImportRun) -> ImportRunResponse:
        return cls(
            id=run.id,
            import_type=run.import_type,
            target_key=run.target_key,
            status=run.status,
            phase=run.phase,
            progress={"processed": run.processed, "total": run.total},
            summary=run.summary,
            params=run.params,
            source_version=run.source_version,
            error=run.error,
            requested_by=run.requested_by,
            upload_ref=run.upload_ref,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )


class StartImportBody(BaseModel):
    import_type: ImportType
    params: dict[str, Any] = {}


class UploadResponse(BaseModel):
    upload_ref: str


@router.post("", response_model=ImportRunResponse, status_code=202)
async def start_import(
    body: StartImportBody,
    auth: AuthDep,
    use_case: StartImportDep,
) -> ImportRunResponse:
    command = StartImportCommand(import_type=body.import_type, params=body.params)
    run = result_to_response(await use_case(command, auth=auth))
    return ImportRunResponse.from_domain(run)


@router.get("", response_model=PaginatedResponse[ImportRunResponse])
async def list_import_runs(
    auth: AuthDep,
    use_case: ListImportRunsDep,
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[ImportRunResponse]:
    # ListImportRunsQuery.cursor is a raw str | None; parse_ts_cursor is called internally.
    query = ListImportRunsQuery(
        cursor=cursor,
        limit=clamp_limit(limit),
    )
    page = result_to_response(await use_case(query, auth=auth))
    return PaginatedResponse(
        items=[ImportRunResponse.from_domain(r) for r in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{import_run_id}", response_model=ImportRunResponse)
async def get_import_run(
    import_run_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetImportRunDep,
) -> ImportRunResponse:
    query = GetImportRunQuery(import_run_id=import_run_id)
    run = result_to_response(await use_case(query, auth=auth))
    return ImportRunResponse.from_domain(run)


@router.post("/uploads", response_model=UploadResponse)
async def upload_essentiality_file(
    auth: AuthDep,
    use_case: StoreUploadDep,
    file: UploadFile,
    import_type: ImportType | None = None,
) -> UploadResponse:
    """Store a raw upload for an import adapter to parse later.

    ``import_type=target_biology`` stores the file's bytes unchanged —
    ``parse_workbook`` needs a real multi-sheet XLSX, not the two-column
    ``locus\\tcall`` TSV every other caller of this route gets. Omitting
    ``import_type`` (every other caller today) keeps the original behaviour:
    convert to that TSV, which is what the DeJesus essentiality plugin expects.
    """
    data = await file.read()

    if import_type is ImportType.TARGET_BIOLOGY:
        upload = result_to_response(
            await use_case(
                filename=file.filename or "upload",
                content_type=file.content_type,
                data=data,
                auth=auth,
            )
        )
        return UploadResponse(upload_ref=str(upload.id))

    try:
        text = essentiality_upload_to_tsv(file.filename or "upload", data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    upload = result_to_response(
        await use_case(
            filename=file.filename or "upload",
            content_type="text/tab-separated-values",
            data=text.encode(),
            auth=auth,
        )
    )
    return UploadResponse(upload_ref=str(upload.id))
