"""Build/version info, surfaced at GET /version."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildInfo:
    version: str
    git_sha: str
    build_date: str
    environment: str


def build_info() -> BuildInfo:
    # Baked into the image by CI (backend/Dockerfile); exported by `make dev`
    # from scripts/build-info.sh. Same names the frontend uses.
    return BuildInfo(
        version=os.getenv("APP_VERSION", "0.0.0+dev"),
        git_sha=os.getenv("APP_GIT_SHA", "unknown"),
        build_date=os.getenv("APP_BUILD_DATE", "unknown"),
        environment=os.getenv("APP_ENV", "development"),
    )
