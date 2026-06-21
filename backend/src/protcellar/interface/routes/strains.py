"""Strain CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.application.shared.sentinel import UNSET
from protcellar.application.taxonomy.create_strain import CreateStrainCommand
from protcellar.application.taxonomy.get_strain import GetStrainQuery
from protcellar.application.taxonomy.list_strains import ListStrainsQuery
from protcellar.application.taxonomy.update_strain import UpdateStrainCommand
from protcellar.domain.taxonomy.strain import Strain
from protcellar.interface.dependencies import (
    AuthDep,
    CreateStrainDep,
    GetStrainDep,
    ListStrainsDep,
    UpdateStrainDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import PaginatedResponse, clamp_limit, parse_cursor

router = APIRouter(prefix="/api/v1/strains", tags=["strains"])


class StrainResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    species_organism_id: uuid.UUID
    ncbi_taxon_id: int | None = None
    name: str
    isolate: str | None = None
    biosample_acc: str | None = None
    assembly_acc: str | None = None
    culture_collection: str | None = None
    host_organism_id: uuid.UUID | None = None
    metadata: dict[str, object] | None = None
    version: int

    @classmethod
    def from_domain(cls, strain: Strain) -> StrainResponse:
        return cls(
            id=strain.id,
            workspace_id=strain.workspace_id,
            species_organism_id=strain.species_organism_id,
            ncbi_taxon_id=strain.ncbi_taxon_id,
            name=strain.name,
            isolate=strain.isolate,
            biosample_acc=strain.biosample_acc,
            assembly_acc=strain.assembly_acc,
            culture_collection=strain.culture_collection,
            host_organism_id=strain.host_organism_id,
            metadata=strain.metadata,
            version=strain.version,
        )


class CreateStrainBody(BaseModel):
    species_organism_id: uuid.UUID
    name: str
    ncbi_taxon_id: int | None = None
    isolate: str | None = None
    biosample_acc: str | None = None
    assembly_acc: str | None = None
    culture_collection: str | None = None
    host_organism_id: uuid.UUID | None = None
    metadata: dict[str, object] | None = None


class UpdateStrainBody(BaseModel):
    name: str | None = None
    ncbi_taxon_id: int | None = None
    isolate: str | None = None
    biosample_acc: str | None = None
    assembly_acc: str | None = None
    culture_collection: str | None = None
    host_organism_id: uuid.UUID | None = None
    metadata: dict[str, object] | None = None

    model_config = {"extra": "forbid"}


@router.get("", response_model=PaginatedResponse[StrainResponse])
async def list_strains(
    auth: AuthDep,
    use_case: ListStrainsDep,
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[StrainResponse]:
    query = ListStrainsQuery(
        workspace_id=auth.workspace_id,
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit),
    )
    page = result_to_response(await use_case(query, auth=auth))
    return PaginatedResponse(
        items=[StrainResponse.from_domain(s) for s in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{strain_id}", response_model=StrainResponse)
async def get_strain(
    strain_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetStrainDep,
) -> StrainResponse:
    query = GetStrainQuery(workspace_id=auth.workspace_id, strain_id=strain_id)
    strain = result_to_response(await use_case(query, auth=auth))
    return StrainResponse.from_domain(strain)


@router.post("", response_model=StrainResponse, status_code=201)
async def create_strain(
    body: CreateStrainBody,
    auth: AuthDep,
    use_case: CreateStrainDep,
) -> StrainResponse:
    command = CreateStrainCommand(
        workspace_id=auth.workspace_id,
        species_organism_id=body.species_organism_id,
        name=body.name,
        ncbi_taxon_id=body.ncbi_taxon_id,
        isolate=body.isolate,
        biosample_acc=body.biosample_acc,
        assembly_acc=body.assembly_acc,
        culture_collection=body.culture_collection,
        host_organism_id=body.host_organism_id,
        metadata=body.metadata,
    )
    strain = result_to_response(await use_case(command, auth=auth))
    return StrainResponse.from_domain(strain)


@router.patch("/{strain_id}", response_model=StrainResponse)
async def update_strain(
    strain_id: uuid.UUID,
    body: UpdateStrainBody,
    auth: AuthDep,
    use_case: UpdateStrainDep,
) -> StrainResponse:
    provided = body.model_fields_set
    command = UpdateStrainCommand(
        workspace_id=auth.workspace_id,
        strain_id=strain_id,
        name=body.name if "name" in provided else None,
        ncbi_taxon_id=body.ncbi_taxon_id if "ncbi_taxon_id" in provided else UNSET,
        isolate=body.isolate if "isolate" in provided else UNSET,
        biosample_acc=body.biosample_acc if "biosample_acc" in provided else UNSET,
        assembly_acc=body.assembly_acc if "assembly_acc" in provided else UNSET,
        culture_collection=body.culture_collection if "culture_collection" in provided else UNSET,
        host_organism_id=body.host_organism_id if "host_organism_id" in provided else UNSET,
        metadata=body.metadata if "metadata" in provided else UNSET,
    )
    strain = result_to_response(await use_case(command, auth=auth))
    return StrainResponse.from_domain(strain)
