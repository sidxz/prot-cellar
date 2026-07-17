"""Plugin catalog + plugin-run endpoints. A plugin run IS an ImportRun."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from protcellar.application.imports.start_import import StartImportCommand
from protcellar.application.plugins.enablement import SetPluginEnablementCommand
from protcellar.application.plugins.manifest import ParamField, ParamType, PluginManifest
from protcellar.application.plugins.validation import validate_against_manifest
from protcellar.domain.imports.enums import ImportType
from protcellar.domain.shared.errors import DomainError
from protcellar.infrastructure.plugins.registry import all_manifests, get_plugin
from protcellar.interface.dependencies import (
    AuthDep,
    ListEnabledPluginIdsDep,
    SetPluginEnablementDep,
    StartImportDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.routes.imports import ImportRunResponse

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


class ParamFieldResponse(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    default: Any | None = None
    options: list[str] = []
    help: str | None = None

    @classmethod
    def from_domain(cls, p: ParamField) -> ParamFieldResponse:
        return cls(
            key=p.key,
            label=p.label,
            type=p.type.value,
            required=p.required,
            default=p.default,
            options=list(p.options),
            help=p.help,
        )


class PluginManifestResponse(BaseModel):
    id: str
    version: str
    name: str
    description: str
    target_records: list[str]
    default_generation_method: str
    params: list[ParamFieldResponse]
    requires_secrets: list[str]
    enabled: bool

    @classmethod
    def from_domain(cls, m: PluginManifest, *, enabled: bool) -> PluginManifestResponse:
        return cls(
            id=m.id,
            version=m.version,
            name=m.name,
            description=m.description,
            target_records=list(m.target_records),
            default_generation_method=m.default_generation_method.value,
            params=[ParamFieldResponse.from_domain(p) for p in m.params],
            requires_secrets=list(m.requires_secrets),
            enabled=enabled,
        )


class StartPluginRunBody(BaseModel):
    params: dict[str, Any] = {}
    dry_run: bool = False


class SetEnabledBody(BaseModel):
    enabled: bool


@router.get("", response_model=list[PluginManifestResponse])
async def list_plugins(
    auth: AuthDep, enabled_uc: ListEnabledPluginIdsDep
) -> list[PluginManifestResponse]:
    enabled = await enabled_uc(auth)
    return [
        PluginManifestResponse.from_domain(m, enabled=m.id in enabled) for m in all_manifests()
    ]


@router.put("/{plugin_id}/enabled", status_code=204)
async def set_plugin_enabled(
    plugin_id: str,
    body: SetEnabledBody,
    auth: AuthDep,
    use_case: SetPluginEnablementDep,
) -> Response:
    """Admin turns a plugin on/off for their workspace."""
    try:
        get_plugin(plugin_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    result_to_response(
        await use_case(
            SetPluginEnablementCommand(plugin_id=plugin_id, enabled=body.enabled), auth=auth
        )
    )
    return Response(status_code=204)


@router.post("/{plugin_id}/runs", response_model=ImportRunResponse, status_code=202)
async def start_plugin_run(
    plugin_id: str,
    body: StartPluginRunBody,
    auth: AuthDep,
    use_case: StartImportDep,
    enabled_uc: ListEnabledPluginIdsDep,
) -> ImportRunResponse:
    try:
        manifest = get_plugin(plugin_id).manifest()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        validated = validate_against_manifest(manifest, body.params)
    except DomainError as e:
        raise HTTPException(status_code=422, detail=e.message) from e

    if plugin_id not in await enabled_uc(auth):
        raise HTTPException(
            status_code=403, detail=f"plugin '{plugin_id}' is not enabled for this workspace"
        )

    params: dict[str, Any] = {**validated, "plugin_id": plugin_id, "dry_run": bool(body.dry_run)}
    file_field = next((p for p in manifest.params if p.type is ParamType.FILE_UPLOAD), None)
    if file_field is not None and file_field.key in params:
        params["upload_ref"] = params[file_field.key]

    command = StartImportCommand(import_type=ImportType.PLUGIN, params=params)
    run = result_to_response(await use_case(command, auth=auth))
    return ImportRunResponse.from_domain(run)
