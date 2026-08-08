"""Organism CRUD + tax-id resolution endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from protcellar.application.shared.sentinel import UNSET
from protcellar.application.taxonomy.bulk_upsert_organisms import (
    BulkUpsertOrganismsCommand,
    OrganismImportRecord,
)
from protcellar.application.taxonomy.create_organism import CreateOrganismCommand
from protcellar.application.taxonomy.get_organism import GetOrganismQuery
from protcellar.application.taxonomy.list_organisms import ListOrganismsQuery
from protcellar.application.taxonomy.resolve_tax_id import ResolveTaxIdQuery
from protcellar.application.taxonomy.update_organism import UpdateOrganismCommand
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import NameClass, OrganismSource
from protcellar.domain.taxonomy.organism import Organism
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.interface.dependencies import (
    AuthDep,
    BulkUpsertOrganismsDep,
    CreateOrganismDep,
    GetOrganismDep,
    ListOrganismsDep,
    ResolveTaxIdDep,
    UpdateOrganismDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import PaginatedResponse, clamp_limit, parse_cursor

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
    reference_strain_id: uuid.UUID | None = None
    is_merged: bool
    merged_into_id: uuid.UUID | None = None
    is_deleted: bool
    source: OrganismSource
    source_release: str | None = None
    version: int
    names: list[OrganismNameResponse]
    is_shared: bool

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
            reference_strain_id=org.reference_strain_id,
            is_merged=org.is_merged,
            merged_into_id=org.merged_into_id,
            is_deleted=org.is_deleted,
            source=org.source,
            source_release=org.source_release,
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
            is_shared=(org.workspace_id == SHARED_WORKSPACE_ID),
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
    reference_strain_id: uuid.UUID | None = None
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


@router.get("", response_model=PaginatedResponse[OrganismResponse])
async def list_organisms(
    auth: AuthDep,
    use_case: ListOrganismsDep,
    name: str | None = None,
    rank: str | None = None,
    tags: list[uuid.UUID] | None = Query(default=None),
    tag_logic: Literal["any", "all"] = "any",
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[OrganismResponse]:
    query = ListOrganismsQuery(
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit),
        name=name,
        rank=rank,
        tag_ids=tuple(tags) if tags else (),
        match_all=tag_logic == "all",
    )
    page = result_to_response(await use_case(query, auth=auth))
    return PaginatedResponse(
        items=[OrganismResponse.from_domain(o) for o in page.items],
        next_cursor=page.next_cursor,
    )


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
        reference_strain_id=(
            body.reference_strain_id if "reference_strain_id" in provided else UNSET
        ),
        source_version=body.source_version if "source_version" in provided else UNSET,
    )
    org = result_to_response(await use_case(command, auth=auth))
    return OrganismResponse.from_domain(org)


class BulkRecordBody(BaseModel):
    ncbi_tax_id: int | None = None
    rank: str
    scientific_name: str
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    division: str | None = None


class BulkUpsertBody(BaseModel):
    records: list[BulkRecordBody]
    dry_run: bool = False


class ItemResultResponse(BaseModel):
    index: int
    status: str
    id: str | None = None
    error: str | None = None


class BulkSummaryResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    failed: int


class BulkUpsertResponse(BaseModel):
    results: list[ItemResultResponse]
    summary: BulkSummaryResponse


@router.post("/bulk", response_model=BulkUpsertResponse)
async def bulk_upsert_organisms(
    body: BulkUpsertBody,
    auth: AuthDep,
    use_case: BulkUpsertOrganismsDep,
) -> BulkUpsertResponse:
    command = BulkUpsertOrganismsCommand(
        records=tuple(
            OrganismImportRecord(
                ncbi_tax_id=r.ncbi_tax_id,
                rank=r.rank,
                scientific_name=r.scientific_name,
                source=r.source,
                source_release=r.source_release,
                source_record_id=r.source_record_id,
                source_record_checksum=r.source_record_checksum,
                division=r.division,
            )
            for r in body.records
        ),
        dry_run=body.dry_run,
    )
    item_results = result_to_response(await use_case(command, auth=auth))
    summary = BulkSummaryResponse(
        created=sum(1 for r in item_results if r.status == "created"),
        updated=sum(1 for r in item_results if r.status == "updated"),
        skipped=sum(1 for r in item_results if r.status == "skipped"),
        failed=sum(1 for r in item_results if r.status == "failed"),
    )
    return BulkUpsertResponse(
        results=[
            ItemResultResponse(index=r.index, status=r.status, id=r.id, error=r.error)
            for r in item_results
        ],
        summary=summary,
    )
