"""Proteome CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.application.taxonomy.create_proteome import CreateProteomeCommand
from protcellar.application.taxonomy.get_proteome import GetProteomeQuery
from protcellar.application.taxonomy.list_proteomes import ListProteomesQuery
from protcellar.domain.taxonomy.enums import ProteomeType
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.interface.dependencies import (
    AuthDep,
    CreateProteomeDep,
    GetProteomeDep,
    ListProteomesDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import PaginatedResponse, clamp_limit, parse_cursor

router = APIRouter(prefix="/api/v1/proteomes", tags=["proteomes"])


class ProteomeResponse(BaseModel):
    id: uuid.UUID
    uniprot_proteome_id: str
    proteome_url: str | None = None
    organism_id: uuid.UUID
    strain_id: uuid.UUID | None = None
    proteome_type: ProteomeType
    is_reference: bool
    assembly_acc: str | None = None
    source_version: str | None = None
    version: int

    @classmethod
    def from_domain(cls, p: Proteome) -> ProteomeResponse:
        proteome_url = IdentifierRegistry.default().resolve_url("proteome", p.uniprot_proteome_id)
        return cls(
            id=p.id,
            uniprot_proteome_id=p.uniprot_proteome_id,
            proteome_url=proteome_url,
            organism_id=p.organism_id,
            strain_id=p.strain_id,
            proteome_type=p.proteome_type,
            is_reference=p.is_reference,
            assembly_acc=p.assembly_acc,
            source_version=p.source_version,
            version=p.version,
        )


class CreateProteomeBody(BaseModel):
    uniprot_proteome_id: str
    organism_id: uuid.UUID
    proteome_type: ProteomeType
    is_reference: bool
    strain_id: uuid.UUID | None = None
    assembly_acc: str | None = None
    source_version: str | None = None


@router.get("", response_model=PaginatedResponse[ProteomeResponse])
async def list_proteomes(
    auth: AuthDep,
    use_case: ListProteomesDep,
    organism_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[ProteomeResponse]:
    query = ListProteomesQuery(
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit),
        organism_id=organism_id,
    )
    page = result_to_response(await use_case(query, auth=auth))
    return PaginatedResponse(
        items=[ProteomeResponse.from_domain(p) for p in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{proteome_id}", response_model=ProteomeResponse)
async def get_proteome(
    proteome_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetProteomeDep,
) -> ProteomeResponse:
    query = GetProteomeQuery(proteome_id=proteome_id)
    proteome = result_to_response(await use_case(query, auth=auth))
    return ProteomeResponse.from_domain(proteome)


@router.post("", response_model=ProteomeResponse, status_code=201)
async def create_proteome(
    body: CreateProteomeBody,
    auth: AuthDep,
    use_case: CreateProteomeDep,
) -> ProteomeResponse:
    command = CreateProteomeCommand(
        uniprot_proteome_id=body.uniprot_proteome_id,
        organism_id=body.organism_id,
        proteome_type=body.proteome_type,
        is_reference=body.is_reference,
        strain_id=body.strain_id,
        assembly_acc=body.assembly_acc,
        source_version=body.source_version,
    )
    proteome = result_to_response(await use_case(command, auth=auth))
    return ProteomeResponse.from_domain(proteome)
