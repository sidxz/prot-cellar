"""Organism CRUD + tax-id resolution endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.application.shared.sentinel import UNSET
from protcellar.application.taxonomy.create_organism import CreateOrganismCommand
from protcellar.application.taxonomy.get_organism import GetOrganismQuery
from protcellar.application.taxonomy.list_organisms import ListOrganismsQuery
from protcellar.application.taxonomy.resolve_tax_id import ResolveTaxIdQuery
from protcellar.application.taxonomy.update_organism import UpdateOrganismCommand
from protcellar.domain.taxonomy.enums import NameClass, OrganismSource
from protcellar.domain.taxonomy.organism import Organism
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.interface.dependencies import (
    AuthDep,
    CreateOrganismDep,
    GetOrganismDep,
    ListOrganismsDep,
    ResolveTaxIdDep,
    UpdateOrganismDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import clamp_limit, parse_cursor

router = APIRouter(prefix="/api/v1/organisms", tags=["organisms"])


class OrganismNameResponse(BaseModel):
    name: str
    name_class: NameClass
    unique_name: str | None = None
    is_preferred: bool


class OrganismResponse(BaseModel):
    id: uuid.UUID
    ncbi_tax_id: int | None = None
    ncbi_url: str | None = None
    parent_id: uuid.UUID | None = None
    rank: str
    scientific_name: str
    division: str | None = None
    is_merged: bool
    merged_into_id: uuid.UUID | None = None
    is_deleted: bool
    source: OrganismSource
    version: int
    names: list[OrganismNameResponse]

    @classmethod
    def from_domain(cls, org: Organism) -> OrganismResponse:
        ncbi_url = (
            IdentifierRegistry.default().resolve_url("ncbitaxon", str(org.ncbi_tax_id))
            if org.ncbi_tax_id is not None
            else None
        )
        return cls(
            id=org.id,
            ncbi_tax_id=org.ncbi_tax_id,
            ncbi_url=ncbi_url,
            parent_id=org.parent_id,
            rank=org.rank,
            scientific_name=org.scientific_name,
            division=org.division,
            is_merged=org.is_merged,
            merged_into_id=org.merged_into_id,
            is_deleted=org.is_deleted,
            source=org.source,
            version=org.version,
            names=[
                OrganismNameResponse(
                    name=n.name,
                    name_class=n.name_class,
                    unique_name=n.unique_name,
                    is_preferred=n.is_preferred,
                )
                for n in org.names
            ],
        )


class CreateOrganismBody(BaseModel):
    ncbi_tax_id: int | None = None
    rank: str
    scientific_name: str
    source: OrganismSource = OrganismSource.NCBI
    division: str | None = None
    source_version: str | None = None


class UpdateOrganismBody(BaseModel):
    scientific_name: str | None = None
    rank: str | None = None
    parent_id: uuid.UUID | None = None
    division: str | None = None
    source_version: str | None = None

    model_config = {"extra": "forbid"}


@router.get("/resolve/{tax_id}", response_model=OrganismResponse)
async def resolve_organism(
    tax_id: int,
    auth: AuthDep,
    use_case: ResolveTaxIdDep,
) -> OrganismResponse:
    query = ResolveTaxIdQuery(tax_id=tax_id)
    org = result_to_response(await use_case(query, auth=auth))
    return OrganismResponse.from_domain(org)


@router.get("", response_model=list[OrganismResponse])
async def list_organisms(
    auth: AuthDep,
    use_case: ListOrganismsDep,
    name: str | None = None,
    rank: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> list[OrganismResponse]:
    query = ListOrganismsQuery(
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit),
        name=name,
        rank=rank,
    )
    page = result_to_response(await use_case(query, auth=auth))
    return [OrganismResponse.from_domain(o) for o in page.items]


@router.get("/{organism_id}", response_model=OrganismResponse)
async def get_organism(
    organism_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetOrganismDep,
) -> OrganismResponse:
    query = GetOrganismQuery(organism_id=organism_id)
    org = result_to_response(await use_case(query, auth=auth))
    return OrganismResponse.from_domain(org)


@router.post("", response_model=OrganismResponse, status_code=201)
async def create_organism(
    body: CreateOrganismBody,
    auth: AuthDep,
    use_case: CreateOrganismDep,
) -> OrganismResponse:
    command = CreateOrganismCommand(
        ncbi_tax_id=body.ncbi_tax_id,
        rank=body.rank,
        scientific_name=body.scientific_name,
        source=body.source,
        division=body.division,
        source_version=body.source_version,
    )
    org = result_to_response(await use_case(command, auth=auth))
    return OrganismResponse.from_domain(org)


@router.patch("/{organism_id}", response_model=OrganismResponse)
async def update_organism(
    organism_id: uuid.UUID,
    body: UpdateOrganismBody,
    auth: AuthDep,
    use_case: UpdateOrganismDep,
) -> OrganismResponse:
    provided = body.model_fields_set
    command = UpdateOrganismCommand(
        organism_id=organism_id,
        scientific_name=body.scientific_name if "scientific_name" in provided else None,
        rank=body.rank if "rank" in provided else None,
        parent_id=body.parent_id if "parent_id" in provided else UNSET,
        division=body.division if "division" in provided else UNSET,
        source_version=body.source_version if "source_version" in provided else UNSET,
    )
    org = result_to_response(await use_case(command, auth=auth))
    return OrganismResponse.from_domain(org)
