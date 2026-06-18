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
    return BuildInfo(
        version=os.getenv("APP_VERSION", "0.1.0"),
        git_sha=os.getenv("GIT_SHA", "dev"),
        build_date=os.getenv("BUILD_DATE", "unknown"),
        environment=os.getenv("APP_ENV", "development"),
    )
