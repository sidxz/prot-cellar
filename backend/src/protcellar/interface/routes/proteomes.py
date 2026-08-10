"""Proteome CRUD endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from protcellar.application.taxonomy.create_proteome import CreateProteomeCommand
from protcellar.application.taxonomy.get_proteome import GetProteomeQuery
from protcellar.application.taxonomy.list_proteomes import ListProteomesQuery
from protcellar.domain.taxonomy.enums import ProteomeType
from protcellar.domain.taxonomy.proteome import Proteome
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.organism_repository import (
    SQLAlchemyOrganismRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.taxonomy.strain_repository import (
    SQLAlchemyStrainRepository,
)
from protcellar.infrastructure.persistence.unit_of_work import AsyncUnitOfWork
from protcellar.interface.dependencies import (
    AuthDep,
    CreateProteomeDep,
    GetProteomeDep,
    ListProteomesDep,
    UoWDep,
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
    # Display names for the picker (target-biology workbook import) — a
    # proteome's own row carries only ids. Both are optional even though
    # organism_id is NOT NULL: they are resolved best-effort by the route (see
    # `_resolve_names` below) and this response must not 500 the whole list
    # over one denormalised label the caller happens not to be able to read.
    organism_name: str | None = None
    strain_name: str | None = None

    @classmethod
    def from_domain(
        cls,
        p: Proteome,
        *,
        organism_name: str | None = None,
        strain_name: str | None = None,
    ) -> ProteomeResponse:
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
            organism_name=organism_name,
            strain_name=strain_name,
        )


async def _resolve_names(
    proteomes: list[Proteome], *, workspace_id: uuid.UUID, uow: AsyncUnitOfWork
) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    """Batch id->name lookups for a page of proteomes: one query for every
    distinct organism_id, one for every distinct strain_id — never one query
    per row (that's the "no extra client fetches" contract pushed down to a
    "no N+1 either" one).

    Reaches past the use-case layer directly into the taxonomy repositories,
    the same scoped exception as `_require_readable_protein` in
    `interface/routes/target_biology.py`: this is a read-only label lookup for
    a response field, not a command, and there is no `GetOrganism`/`GetStrain`
    shaped query that returns more than one name at a time.
    """
    organism_ids = {p.organism_id for p in proteomes}
    strain_ids = {p.strain_id for p in proteomes if p.strain_id is not None}
    async with uow:
        organism_names = await SQLAlchemyOrganismRepository(uow).find_names_by_ids(
            list(organism_ids), workspace_id=workspace_id
        )
        strain_names = await SQLAlchemyStrainRepository(uow).find_names_by_ids(
            list(strain_ids), workspace_id=workspace_id
        )
    return organism_names, strain_names


def _to_response(
    p: Proteome, organism_names: dict[uuid.UUID, str], strain_names: dict[uuid.UUID, str]
) -> ProteomeResponse:
    return ProteomeResponse.from_domain(
        p,
        organism_name=organism_names.get(p.organism_id),
        strain_name=strain_names.get(p.strain_id) if p.strain_id is not None else None,
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
    uow: UoWDep,
    organism_id: uuid.UUID | None = None,
    tags: list[uuid.UUID] | None = Query(default=None),
    tag_logic: Literal["any", "all"] = "any",
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[ProteomeResponse]:
    query = ListProteomesQuery(
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit),
        organism_id=organism_id,
        tag_ids=tuple(tags) if tags else (),
        match_all=tag_logic == "all",
    )
    page = result_to_response(await use_case(query, auth=auth))
    organism_names, strain_names = await _resolve_names(
        page.items, workspace_id=auth.workspace_id, uow=uow
    )
    return PaginatedResponse(
        items=[_to_response(p, organism_names, strain_names) for p in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{proteome_id}", response_model=ProteomeResponse)
async def get_proteome(
    proteome_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetProteomeDep,
    uow: UoWDep,
) -> ProteomeResponse:
    query = GetProteomeQuery(proteome_id=proteome_id)
    proteome = result_to_response(await use_case(query, auth=auth))
    organism_names, strain_names = await _resolve_names(
        [proteome], workspace_id=auth.workspace_id, uow=uow
    )
    return _to_response(proteome, organism_names, strain_names)


@router.post("", response_model=ProteomeResponse, status_code=201)
async def create_proteome(
    body: CreateProteomeBody,
    auth: AuthDep,
    use_case: CreateProteomeDep,
    uow: UoWDep,
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
    organism_names, strain_names = await _resolve_names(
        [proteome], workspace_id=auth.workspace_id, uow=uow
    )
    return _to_response(proteome, organism_names, strain_names)
