"""Gene CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.application.protein_catalog.create_gene import CreateGeneCommand
from protcellar.application.protein_catalog.get_gene import GetGeneQuery
from protcellar.application.protein_catalog.list_genes import ListGenesQuery
from protcellar.application.protein_catalog.update_gene import UpdateGeneCommand
from protcellar.application.shared.sentinel import UNSET
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.interface.dependencies import (
    AuthDep,
    CreateGeneDep,
    GetGeneDep,
    ListGenesDep,
    UpdateGeneDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import PaginatedResponse, clamp_limit, parse_cursor

router = APIRouter(prefix="/api/v1/genes", tags=["genes"])


class CrossReferenceResponse(BaseModel):
    database: str
    accession: str
    curie: str
    url: str | None = None


class GeneResponse(BaseModel):
    id: uuid.UUID
    primary_name: str
    organism_id: uuid.UUID
    synonyms: list[str]
    ncbi_gene_id: str | None = None
    ncbi_gene_url: str | None = None
    ensembl_gene_id: str | None = None
    ensembl_url: str | None = None
    hgnc_id: str | None = None
    cross_references: list[CrossReferenceResponse]
    version: int

    @classmethod
    def from_domain(cls, g: Gene) -> GeneResponse:
        ncbi_gene_url = (
            IdentifierRegistry.default().resolve_url("ncbigene", g.ncbi_gene_id)
            if g.ncbi_gene_id is not None
            else None
        )
        ensembl_url = (
            IdentifierRegistry.default().resolve_url("ensembl", g.ensembl_gene_id)
            if g.ensembl_gene_id is not None
            else None
        )
        return cls(
            id=g.id,
            primary_name=g.primary_name,
            organism_id=g.organism_id,
            synonyms=g.synonyms,
            ncbi_gene_id=g.ncbi_gene_id,
            ncbi_gene_url=ncbi_gene_url,
            ensembl_gene_id=g.ensembl_gene_id,
            ensembl_url=ensembl_url,
            hgnc_id=g.hgnc_id,
            cross_references=[
                CrossReferenceResponse(
                    database=x.database,
                    accession=x.accession,
                    curie=x.to_curie(),
                    url=IdentifierRegistry.default().resolve_url(x.database, x.accession),
                )
                for x in g.cross_references
            ],
            version=g.version,
        )


class CreateGeneBody(BaseModel):
    primary_name: str
    organism_id: uuid.UUID
    synonyms: list[str] = []
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    hgnc_id: str | None = None


class UpdateGeneBody(BaseModel):
    primary_name: str | None = None
    synonyms: list[str] | None = None
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    hgnc_id: str | None = None

    model_config = {"extra": "forbid"}


@router.get("", response_model=PaginatedResponse[GeneResponse])
async def list_genes(
    auth: AuthDep,
    use_case: ListGenesDep,
    name: str | None = None,
    organism_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[GeneResponse]:
    query = ListGenesQuery(
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit),
        name=name,
        organism_id=organism_id,
    )
    page = result_to_response(await use_case(query, auth=auth))
    return PaginatedResponse(
        items=[GeneResponse.from_domain(g) for g in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/{gene_id}", response_model=GeneResponse)
async def get_gene(
    gene_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetGeneDep,
) -> GeneResponse:
    query = GetGeneQuery(gene_id=gene_id)
    gene = result_to_response(await use_case(query, auth=auth))
    return GeneResponse.from_domain(gene)


@router.post("", response_model=GeneResponse, status_code=201)
async def create_gene(
    body: CreateGeneBody,
    auth: AuthDep,
    use_case: CreateGeneDep,
) -> GeneResponse:
    command = CreateGeneCommand(
        primary_name=body.primary_name,
        organism_id=body.organism_id,
        synonyms=body.synonyms,
        ncbi_gene_id=body.ncbi_gene_id,
        ensembl_gene_id=body.ensembl_gene_id,
        hgnc_id=body.hgnc_id,
    )
    gene = result_to_response(await use_case(command, auth=auth))
    return GeneResponse.from_domain(gene)


@router.patch("/{gene_id}", response_model=GeneResponse)
async def update_gene(
    gene_id: uuid.UUID,
    body: UpdateGeneBody,
    auth: AuthDep,
    use_case: UpdateGeneDep,
) -> GeneResponse:
    provided = body.model_fields_set
    command = UpdateGeneCommand(
        gene_id=gene_id,
        primary_name=body.primary_name if "primary_name" in provided else None,
        synonyms=body.synonyms if "synonyms" in provided else None,
        ncbi_gene_id=body.ncbi_gene_id if "ncbi_gene_id" in provided else UNSET,
        ensembl_gene_id=body.ensembl_gene_id if "ensembl_gene_id" in provided else UNSET,
        hgnc_id=body.hgnc_id if "hgnc_id" in provided else UNSET,
    )
    gene = result_to_response(await use_case(command, auth=auth))
    return GeneResponse.from_domain(gene)
