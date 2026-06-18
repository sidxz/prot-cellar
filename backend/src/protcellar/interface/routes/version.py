"""Unauthenticated version endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.version import build_info

router = APIRouter(tags=["meta"])


class VersionResponse(BaseModel):
    version: str
    git_sha: str
    build_date: str
    environment: str


@router.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    info = build_info()
    return VersionResponse(
        version=info.version,
        git_sha=info.git_sha,
        build_date=info.build_date,
        environment=info.environment,
    )
