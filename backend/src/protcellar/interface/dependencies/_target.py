"""Target FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.target.create_target import CreateTarget
from protcellar.application.target.get_target import GetTarget
from protcellar.application.target.list_targets import ListTargets
from protcellar.application.target.update_target import UpdateTarget

from ._core import _get_use_case

__all__ = [
    "CreateTargetDep",
    "GetTargetDep",
    "ListTargetsDep",
    "UpdateTargetDep",
]

CreateTargetDep = Annotated[CreateTarget, Depends(_get_use_case(CreateTarget))]
UpdateTargetDep = Annotated[UpdateTarget, Depends(_get_use_case(UpdateTarget))]
GetTargetDep = Annotated[GetTarget, Depends(_get_use_case(GetTarget))]
ListTargetsDep = Annotated[ListTargets, Depends(_get_use_case(ListTargets))]
