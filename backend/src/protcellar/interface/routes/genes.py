"""Gene CRUD endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.application.protein_catalog.bulk_upsert_genes import (
    BulkUpsertGenesCommand,
    GeneImportRecord,
)
from protcellar.application.protein_catalog.create_gene import CreateGeneCommand
from protcellar.application.protein_catalog.get_gene import GetGeneQuery
from protcellar.application.protein_catalog.get_gene_neighborhood import (
    GetGeneNeighborhoodQuery,
)
from protcellar.application.protein_catalog.list_genes import ListGenesQuery
from protcellar.application.protein_catalog.update_gene import UpdateGeneCommand
from protcellar.application.shared.sentinel import UNSET
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.gene_annotation import GeneAnnotation, GeneAnnotationAxis
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.interface.dependencies import (
    AuthDep,
    BulkUpsertGenesDep,
    CreateGeneDep,
    GetGeneDep,
    GetGeneNeighborhoodDep,
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


class GeneAnnotationResponse(BaseModel):
    axis: str
    key: str
    value: str
    value_type: str
    dataset: str | None = None
    condition: str | None = None
    evidence: str | None = None
    source: str | None = None
    source_url: str | None = None

    @classmethod
    def from_domain(cls, a: GeneAnnotation) -> GeneAnnotationResponse:
        return cls(
            axis=a.axis.value,
            key=a.key,
            value=a.value,
            value_type=a.value_type,
            dataset=a.dataset,
            condition=a.condition,
            evidence=a.evidence,
            source=a.source,
            source_url=a.source_url,
        )


class GeneResponse(BaseModel):
    id: uuid.UUID
    primary_name: str
    organism_id: uuid.UUID
    strain_id: uuid.UUID | None = None
    synonyms: list[str]
    ncbi_gene_id: str | None = None
    ncbi_gene_url: str | None = None
    ensembl_gene_id: str | None = None
    ensembl_url: str | None = None
    hgnc_id: str | None = None
    cross_references: list[CrossReferenceResponse]
    genomic_accession: str | None = None
    genomic_start: int | None = None
    genomic_end: int | None = None
    genomic_strand: str | None = None
    assembly: str | None = None
    length_bp: int | None = None
    annotations: list[GeneAnnotationResponse]
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
            strain_id=g.strain_id,
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
            genomic_accession=g.genomic_accession,
            genomic_start=g.genomic_start,
            genomic_end=g.genomic_end,
            genomic_strand=g.genomic_strand,
            assembly=g.assembly,
            length_bp=g.length_bp,
            annotations=[GeneAnnotationResponse.from_domain(a) for a in g.annotations],
            version=g.version,
        )


class GeneAnnotationBody(BaseModel):
    """Inbound axis-typed annotation (mirrors GeneAnnotationResponse minus computed fields)."""

    axis: GeneAnnotationAxis
    key: str
    value: str
    value_type: str = "categorical"
    dataset: str | None = None
    condition: str | None = None
    evidence: str | None = None
    source: str | None = None
    source_url: str | None = None

    def to_domain(self) -> GeneAnnotation:
        return GeneAnnotation(
            axis=self.axis,
            key=self.key,
            value=self.value,
            value_type=self.value_type,
            dataset=self.dataset,
            condition=self.condition,
            evidence=self.evidence,
            source=self.source,
            source_url=self.source_url,
        )


class GeneNeighborSummary(BaseModel):
    id: uuid.UUID
    primary_name: str
    genomic_start: int | None = None
    genomic_end: int | None = None
    genomic_strand: str | None = None
    essentiality: str | None = None


class GeneNeighborhoodResponse(BaseModel):
    center_id: uuid.UUID
    accession: str
    neighbors: list[GeneNeighborSummary]


class CreateGeneBody(BaseModel):
    primary_name: str
    organism_id: uuid.UUID
    synonyms: list[str] = []
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    hgnc_id: str | None = None
    genomic_accession: str | None = None
    genomic_start: int | None = None
    genomic_end: int | None = None
    genomic_strand: str | None = None
    assembly: str | None = None
    annotations: list[GeneAnnotationBody] = []


class UpdateGeneBody(BaseModel):
    primary_name: str | None = None
    synonyms: list[str] | None = None
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    hgnc_id: str | None = None
    genomic_accession: str | None = None
    genomic_start: int | None = None
    genomic_end: int | None = None
    genomic_strand: str | None = None
    assembly: str | None = None
    annotations: list[GeneAnnotationBody] | None = None

    model_config = {"extra": "forbid"}


class BulkCrossReferenceBody(BaseModel):
    database: str
    accession: str
    properties: dict[str, str] | None = None
    evidence: str | None = None


class BulkGeneRecordBody(BaseModel):
    primary_name: str
    organism_id: uuid.UUID
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    synonyms: list[str] = []
    ncbi_gene_id: str | None = None
    ensembl_gene_id: str | None = None
    cross_references: list[BulkCrossReferenceBody] = []


class BulkUpsertGenesBody(BaseModel):
    records: list[BulkGeneRecordBody]
    dry_run: bool = False


class GeneItemResultResponse(BaseModel):
    index: int
    status: str
    id: str | None = None
    error: str | None = None


class GeneBulkSummaryResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    failed: int


class GeneBulkUpsertResponse(BaseModel):
    results: list[GeneItemResultResponse]
    summary: GeneBulkSummaryResponse


@router.get("", response_model=PaginatedResponse[GeneResponse])
async def list_genes(
    auth: AuthDep,
    use_case: ListGenesDep,
    name: str | None = None,
    organism_id: uuid.UUID | None = None,
    strain_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[GeneResponse]:
    query = ListGenesQuery(
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit),
        name=name,
        organism_id=organism_id,
        strain_id=strain_id,
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


@router.get("/{gene_id}/neighborhood", response_model=GeneNeighborhoodResponse)
async def get_gene_neighborhood(
    gene_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetGeneNeighborhoodDep,
    window: int = 8,
) -> GeneNeighborhoodResponse:
    query = GetGeneNeighborhoodQuery(gene_id=gene_id, window=window)
    result = result_to_response(await use_case(query, auth=auth))
    return GeneNeighborhoodResponse(
        center_id=result.center_id,
        accession=result.accession,
        neighbors=[
            GeneNeighborSummary(
                id=n.id,
                primary_name=n.primary_name,
                genomic_start=n.genomic_start,
                genomic_end=n.genomic_end,
                genomic_strand=n.genomic_strand,
                essentiality=n.essentiality,
            )
            for n in result.neighbors
        ],
    )


@router.post("/bulk", response_model=GeneBulkUpsertResponse)
async def bulk_upsert_genes(
    body: BulkUpsertGenesBody,
    auth: AuthDep,
    use_case: BulkUpsertGenesDep,
) -> GeneBulkUpsertResponse:
    command = BulkUpsertGenesCommand(
        records=tuple(
            GeneImportRecord(
                primary_name=r.primary_name,
                organism_id=r.organism_id,
                source=r.source,
                source_release=r.source_release,
                source_record_id=r.source_record_id,
                source_record_checksum=r.source_record_checksum,
                synonyms=tuple(r.synonyms),
                ncbi_gene_id=r.ncbi_gene_id,
                ensembl_gene_id=r.ensembl_gene_id,
                cross_references=tuple(
                    CrossReference(
                        database=xr.database,
                        accession=xr.accession,
                        properties=xr.properties,
                        evidence=xr.evidence,
                    )
                    for xr in r.cross_references
                ),
            )
            for r in body.records
        ),
        dry_run=body.dry_run,
    )
    items = result_to_response(await use_case(command, auth=auth))
    summary = GeneBulkSummaryResponse(
        created=sum(1 for i in items if i.status == "created"),
        updated=sum(1 for i in items if i.status == "updated"),
        skipped=sum(1 for i in items if i.status == "skipped"),
        failed=sum(1 for i in items if i.status == "failed"),
    )
    return GeneBulkUpsertResponse(
        results=[
            GeneItemResultResponse(index=i.index, status=i.status, id=i.id, error=i.error)
            for i in items
        ],
        summary=summary,
    )


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
        genomic_accession=body.genomic_accession,
        genomic_start=body.genomic_start,
        genomic_end=body.genomic_end,
        genomic_strand=body.genomic_strand,
        assembly=body.assembly,
        annotations=[a.to_domain() for a in body.annotations],
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
    annotations = (
        [a.to_domain() for a in (body.annotations or [])] if "annotations" in provided else UNSET
    )
    command = UpdateGeneCommand(
        gene_id=gene_id,
        primary_name=body.primary_name if "primary_name" in provided else None,
        synonyms=body.synonyms if "synonyms" in provided else None,
        ncbi_gene_id=body.ncbi_gene_id if "ncbi_gene_id" in provided else UNSET,
        ensembl_gene_id=body.ensembl_gene_id if "ensembl_gene_id" in provided else UNSET,
        hgnc_id=body.hgnc_id if "hgnc_id" in provided else UNSET,
        genomic_accession=body.genomic_accession if "genomic_accession" in provided else UNSET,
        genomic_start=body.genomic_start if "genomic_start" in provided else UNSET,
        genomic_end=body.genomic_end if "genomic_end" in provided else UNSET,
        genomic_strand=body.genomic_strand if "genomic_strand" in provided else UNSET,
        assembly=body.assembly if "assembly" in provided else UNSET,
        annotations=annotations,
    )
    gene = result_to_response(await use_case(command, auth=auth))
    return GeneResponse.from_domain(gene)
