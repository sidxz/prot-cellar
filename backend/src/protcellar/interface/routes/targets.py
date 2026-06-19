"""Target CRUD endpoints (workspace-scoped)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.application.shared.sentinel import UNSET
from protcellar.application.target.create_target import ComponentInput, CreateTargetCommand
from protcellar.application.target.get_target import GetTargetQuery
from protcellar.application.target.list_targets import ListTargetsQuery
from protcellar.application.target.update_target import UpdateTargetCommand
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.domain.target.enums import ComponentRelationship, TargetType
from protcellar.domain.target.target import Target
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.interface.dependencies import (
    AuthDep,
    CreateTargetDep,
    GetTargetDep,
    ListTargetsDep,
    UpdateTargetDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import PaginatedResponse, clamp_limit, parse_cursor

router = APIRouter(prefix="/api/v1/targets", tags=["targets"])


class ComponentBody(BaseModel):
    protein_id: uuid.UUID
    relationship: ComponentRelationship


class CrossReferenceBody(BaseModel):
    database: str
    accession: str
    properties: dict[str, str] | None = None
    evidence: str | None = None


class ComponentResponse(BaseModel):
    id: uuid.UUID
    protein_id: uuid.UUID
    relationship: ComponentRelationship


class TargetResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    pref_name: str
    target_type: TargetType
    components: list[ComponentResponse]
    organism_id: uuid.UUID | None = None
    chembl_id: str | None = None
    chembl_url: str | None = None
    pharmacological_class: str | None = None
    cross_references: list[dict[str, str | None]]
    version: int

    @classmethod
    def from_domain(cls, t: Target) -> TargetResponse:
        registry = IdentifierRegistry.default()
        chembl_url = registry.resolve_url("chembl.target", t.chembl_id) if t.chembl_id else None
        cross_references = [
            {
                "database": x.database,
                "accession": x.accession,
                "curie": x.to_curie(),
                "url": registry.resolve_url(x.database, x.accession),
            }
            for x in t.cross_references
        ]
        return cls(
            id=t.id,
            workspace_id=t.workspace_id,
            pref_name=t.pref_name,
            target_type=t.target_type,
            components=[
                ComponentResponse(id=c.id, protein_id=c.protein_id, relationship=c.relationship)
                for c in t.components
            ],
            organism_id=t.organism_id,
            chembl_id=t.chembl_id,
            chembl_url=chembl_url,
            pharmacological_class=t.pharmacological_class,
            cross_references=cross_references,
            version=t.version,
        )


class CreateTargetBody(BaseModel):
    pref_name: str
    target_type: TargetType
    components: list[ComponentBody] = []
    organism_id: uuid.UUID | None = None
    chembl_id: str | None = None
    pharmacological_class: str | None = None
    cross_references: list[CrossReferenceBody] = []


class UpdateTargetBody(BaseModel):
    pref_name: str | None = None
    target_type: TargetType | None = None
    components: list[ComponentBody] | None = None
    organism_id: uuid.UUID | None = None
    chembl_id: str | None = None
    pharmacological_class: str | None = None
    cross_references: list[CrossReferenceBody] | None = None

    model_config = {"extra": "forbid"}


@router.get("", response_model=PaginatedResponse[TargetResponse])
async def list_targets(
    auth: AuthDep,
    use_case: ListTargetsDep,
    target_type: str | None = None,
    chembl_id: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[TargetResponse]:
    parsed_target_type: TargetType | None = None
    if target_type is not None:
        parsed_target_type = TargetType(target_type)
    query = ListTargetsQuery(
        workspace_id=auth.workspace_id,
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit),
        target_type=parsed_target_type,
        chembl_id=chembl_id,
    )
    page = result_to_response(await use_case(query, auth=auth))
    return PaginatedResponse(
        items=[TargetResponse.from_domain(t) for t in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetTargetDep,
) -> TargetResponse:
    query = GetTargetQuery(workspace_id=auth.workspace_id, target_id=target_id)
    target = result_to_response(await use_case(query, auth=auth))
    return TargetResponse.from_domain(target)


@router.post("", response_model=TargetResponse, status_code=201)
async def create_target(
    body: CreateTargetBody,
    auth: AuthDep,
    use_case: CreateTargetDep,
) -> TargetResponse:
    command = CreateTargetCommand(
        workspace_id=auth.workspace_id,
        pref_name=body.pref_name,
        target_type=body.target_type,
        components=tuple(
            ComponentInput(protein_id=c.protein_id, relationship=c.relationship)
            for c in body.components
        ),
        organism_id=body.organism_id,
        chembl_id=body.chembl_id,
        pharmacological_class=body.pharmacological_class,
        cross_references=tuple(
            CrossReference(
                database=xr.database,
                accession=xr.accession,
                properties=xr.properties,
                evidence=xr.evidence,
            )
            for xr in body.cross_references
        ),
    )
    target = result_to_response(await use_case(command, auth=auth))
    return TargetResponse.from_domain(target)


@router.patch("/{target_id}", response_model=TargetResponse)
async def update_target(
    target_id: uuid.UUID,
    body: UpdateTargetBody,
    auth: AuthDep,
    use_case: UpdateTargetDep,
) -> TargetResponse:
    provided = body.model_fields_set

    components: tuple[ComponentInput, ...] | None = None
    if "components" in provided and body.components is not None:
        components = tuple(
            ComponentInput(protein_id=c.protein_id, relationship=c.relationship)
            for c in body.components
        )

    cross_references: tuple[CrossReference, ...] | None = None
    if "cross_references" in provided and body.cross_references is not None:
        cross_references = tuple(
            CrossReference(
                database=xr.database,
                accession=xr.accession,
                properties=xr.properties,
                evidence=xr.evidence,
            )
            for xr in body.cross_references
        )

    command = UpdateTargetCommand(
        workspace_id=auth.workspace_id,
        target_id=target_id,
        pref_name=body.pref_name if "pref_name" in provided else None,
        target_type=body.target_type if "target_type" in provided else None,
        components=components,
        organism_id=body.organism_id if "organism_id" in provided else UNSET,
        chembl_id=body.chembl_id if "chembl_id" in provided else UNSET,
        pharmacological_class=(
            body.pharmacological_class if "pharmacological_class" in provided else UNSET
        ),
        cross_references=cross_references,
    )
    target = result_to_response(await use_case(command, auth=auth))
    return TargetResponse.from_domain(target)
