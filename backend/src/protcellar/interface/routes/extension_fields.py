"""Admin CRUD for the per-workspace, per-record-kind extension field registry.

Declares which extra fields a workspace has added on top of a target-biology
record kind's core schema. Nothing here reads or writes a record's
``extensions`` bag — this is the registry of what's *allowed* in it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response
from pydantic import BaseModel

from protcellar.application.shared.sentinel import UNSET
from protcellar.application.target_biology.crud import RecordKind
from protcellar.application.workspace_config.extension_fields.create_field_def import (
    CreateFieldDefCommand,
)
from protcellar.application.workspace_config.extension_fields.delete_field_def import (
    DeleteFieldDefCommand,
)
from protcellar.application.workspace_config.extension_fields.list_field_defs import (
    ListFieldDefsQuery,
)
from protcellar.application.workspace_config.extension_fields.update_field_def import (
    UpdateFieldDefCommand,
)
from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)
from protcellar.interface.dependencies import (
    AuthDep,
    CreateFieldDefDep,
    DeleteFieldDefDep,
    ListFieldDefsDep,
    UpdateFieldDefDep,
)
from protcellar.interface.error_handlers import result_to_response

router = APIRouter(prefix="/api/v1/extension-fields", tags=["extension-fields"])


class ExtensionFieldDefResponse(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    label: str
    field_type: str
    options: list[str] | None
    position: int
    show_in_table: bool
    version: int

    @classmethod
    def from_domain(cls, field_def: ExtensionFieldDef) -> ExtensionFieldDefResponse:
        return cls(
            id=field_def.id,
            kind=field_def.kind,
            name=field_def.name,
            label=field_def.label,
            field_type=field_def.field_type.value,
            options=field_def.options,
            position=field_def.position,
            show_in_table=field_def.show_in_table,
            version=field_def.version,
        )


class CreateFieldDefBody(BaseModel):
    # kind is validated against RecordKind by FastAPI before this body runs — the
    # same mechanism the bulk target-biology list route uses for its {kind} path
    # segment — so an unknown kind 422s with no database round trip.
    kind: RecordKind
    name: str
    label: str
    field_type: ExtensionFieldType
    options: list[str] | None = None
    position: int
    show_in_table: bool


class UpdateFieldDefBody(BaseModel):
    """``name`` (and ``kind``) are deliberately absent: renaming would orphan every
    stored value already keyed under the old name, and moving a declaration to a
    different kind isn't a supported edit. Omitting the field from the body — not
    a hand-rolled guard in the use case — is what turns a client's attempt to send
    ``name`` into a 422 (``extra="forbid"``), matching ``UpdateGeneBody``.
    """

    label: str | None = None
    field_type: ExtensionFieldType | None = None
    options: list[str] | None = None
    position: int | None = None
    show_in_table: bool | None = None

    model_config = {"extra": "forbid"}


@router.get("", response_model=list[ExtensionFieldDefResponse])
async def list_field_defs(
    auth: AuthDep,
    use_case: ListFieldDefsDep,
    kind: RecordKind | None = None,
) -> list[ExtensionFieldDefResponse]:
    query = ListFieldDefsQuery(workspace_id=auth.workspace_id, kind=kind)
    field_defs = result_to_response(await use_case(query, auth=auth))
    return [ExtensionFieldDefResponse.from_domain(f) for f in field_defs]


@router.post("", response_model=ExtensionFieldDefResponse, status_code=201)
async def create_field_def(
    body: CreateFieldDefBody,
    auth: AuthDep,
    use_case: CreateFieldDefDep,
) -> ExtensionFieldDefResponse:
    command = CreateFieldDefCommand(
        workspace_id=auth.workspace_id,
        kind=body.kind.value,
        name=body.name,
        label=body.label,
        field_type=body.field_type,
        options=body.options,
        position=body.position,
        show_in_table=body.show_in_table,
    )
    field_def = result_to_response(await use_case(command, auth=auth))
    return ExtensionFieldDefResponse.from_domain(field_def)


@router.patch("/{field_def_id}", response_model=ExtensionFieldDefResponse)
async def update_field_def(
    field_def_id: uuid.UUID,
    body: UpdateFieldDefBody,
    auth: AuthDep,
    use_case: UpdateFieldDefDep,
) -> ExtensionFieldDefResponse:
    provided = body.model_fields_set
    command = UpdateFieldDefCommand(
        workspace_id=auth.workspace_id,
        field_def_id=field_def_id,
        label=body.label,
        field_type=body.field_type,
        options=body.options if "options" in provided else UNSET,
        position=body.position,
        show_in_table=body.show_in_table,
    )
    field_def = result_to_response(await use_case(command, auth=auth))
    return ExtensionFieldDefResponse.from_domain(field_def)


@router.delete("/{field_def_id}", status_code=204)
async def delete_field_def(
    field_def_id: uuid.UUID,
    auth: AuthDep,
    use_case: DeleteFieldDefDep,
) -> Response:
    command = DeleteFieldDefCommand(workspace_id=auth.workspace_id, field_def_id=field_def_id)
    result_to_response(await use_case(command, auth=auth))
    return Response(status_code=204)
