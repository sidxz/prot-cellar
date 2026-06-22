"""Imports FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.imports.get_import_run import GetImportRun
from protcellar.application.imports.list_import_runs import ListImportRuns
from protcellar.application.imports.start_import import StartImport
from protcellar.application.imports.store_upload import GetUpload, StoreUpload

from ._core import _get_use_case

__all__ = [
    "GetImportRunDep",
    "GetUploadDep",
    "ListImportRunsDep",
    "StartImportDep",
    "StoreUploadDep",
]

# --- FastAPI type-alias Deps ---
StartImportDep = Annotated[StartImport, Depends(_get_use_case(StartImport))]
ListImportRunsDep = Annotated[ListImportRuns, Depends(_get_use_case(ListImportRuns))]
GetImportRunDep = Annotated[GetImportRun, Depends(_get_use_case(GetImportRun))]
StoreUploadDep = Annotated[StoreUpload, Depends(_get_use_case(StoreUpload))]
GetUploadDep = Annotated[GetUpload, Depends(_get_use_case(GetUpload))]
