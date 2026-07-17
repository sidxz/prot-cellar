"""Plugin-enablement FastAPI dependency aliases."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from protcellar.application.plugins.enablement import ListEnabledPluginIds, SetPluginEnablement

from ._core import _get_use_case

__all__ = ["ListEnabledPluginIdsDep", "SetPluginEnablementDep"]

ListEnabledPluginIdsDep = Annotated[
    ListEnabledPluginIds, Depends(_get_use_case(ListEnabledPluginIds))
]
SetPluginEnablementDep = Annotated[
    SetPluginEnablement, Depends(_get_use_case(SetPluginEnablement))
]
