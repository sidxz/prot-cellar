"""Protein CRUD + search + FASTA + ID-resolution endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from protcellar.application.protein_catalog.bulk_upsert_proteins import (
    BulkUpsertProteinsCommand,
    ProteinImportRecord,
)
from protcellar.application.protein_catalog.create_protein import CreateProteinCommand
from protcellar.application.protein_catalog.get_protein import GetProteinQuery
from protcellar.application.protein_catalog.list_proteins import ListProteinsQuery, ProteinListItem
from protcellar.application.protein_catalog.resolve_protein_id import ResolveProteinIdQuery
from protcellar.application.protein_catalog.update_protein import UpdateProteinCommand
from protcellar.application.shared.sentinel import UNSET
from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.value_objects import (
    ProteinCitation,
    ProteinComment,
    ProteinFeature,
    ProteinIsoform,
    ProteinKeyword,
    ProteinNames,
)
from protcellar.domain.shared.cross_reference import CrossReference
from protcellar.infrastructure.identifiers.registry import IdentifierRegistry
from protcellar.interface.dependencies import (
    AuthDep,
    BulkUpsertProteinsDep,
    CreateProteinDep,
    GetProteinDep,
    ListProteinsDep,
    ResolveProteinIdDep,
    UpdateProteinDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import (
    BULK_PAGE_SIZE,
    PaginatedResponse,
    clamp_limit,
    parse_cursor,
)

router = APIRouter(prefix="/api/v1/proteins", tags=["proteins"])


class FeatureResponse(BaseModel):
    feature_type: str
    start: int | None = None
    end: int | None = None
    start_modifier: str | None = None
    end_modifier: str | None = None
    description: str | None = None
    feature_id: str | None = None
    ligand: dict[str, object] | None = None
    alternative_sequence: str | None = None
    evidence: list[dict[str, object]] | None = None


class FeatureBody(BaseModel):
    feature_type: str
    start: int | None = None
    end: int | None = None
    start_modifier: str | None = None
    end_modifier: str | None = None
    description: str | None = None
    feature_id: str | None = None
    ligand: dict[str, object] | None = None
    alternative_sequence: str | None = None
    evidence: list[dict[str, object]] | None = None


class CommentResponse(BaseModel):
    comment_type: str
    text: str | None = None
    payload: dict[str, object] | None = None
    evidence: list[dict[str, object]] | None = None


class CommentBody(BaseModel):
    comment_type: str
    text: str | None = None
    payload: dict[str, object] | None = None
    evidence: list[dict[str, object]] | None = None


class IsoformResponse(BaseModel):
    isoform_accession: str
    name: str | None = None
    is_displayed: bool = False
    sequence: str | None = None
    event: str | None = None
    note: str | None = None


class IsoformBody(BaseModel):
    isoform_accession: str
    name: str | None = None
    is_displayed: bool = False
    sequence: str | None = None
    event: str | None = None
    note: str | None = None


class KeywordRefResponse(BaseModel):
    kw_id: str
    name: str | None = None
    category: str | None = None


class KeywordRefBody(BaseModel):
    kw_id: str
    name: str | None = None
    category: str | None = None


class CitationResponse(BaseModel):
    citation_type: str | None = None
    title: str | None = None
    journal: str | None = None
    authors: list[str] | None = None
    publication_date: str | None = None
    pubmed_id: str | None = None
    doi: str | None = None
    reference_number: int | None = None
    positions: list[str] | None = None
    reference_comments: list[dict[str, object]] | None = None


class CitationBody(BaseModel):
    citation_type: str | None = None
    title: str | None = None
    journal: str | None = None
    authors: list[str] | None = None
    publication_date: str | None = None
    pubmed_id: str | None = None
    doi: str | None = None
    reference_number: int | None = None
    positions: list[str] | None = None
    reference_comments: list[dict[str, object]] | None = None


class ProteinXrefResponse(BaseModel):
    database: str
    accession: str
    curie: str | None = None
    url: str | None = None
    properties: dict[str, str] = {}


class GeneSummaryResponse(BaseModel):
    """Lightweight gene fields embedded in the protein list for at-a-glance display."""

    id: uuid.UUID
    primary_name: str
    synonyms: list[str]

    @classmethod
    def from_domain(cls, g: Gene) -> GeneSummaryResponse:
        return cls(id=g.id, primary_name=g.primary_name, synonyms=list(g.synonyms))


class ProteinStructureSummary(BaseModel):
    """3D-structure availability, distilled for at-a-glance druggability triage."""

    pdb_count: int
    has_alphafold: bool


class ProteinChemSummary(BaseModel):
    """Presence of chemical matter (known ligands / bioactivity) for a protein."""

    has_chembl: bool
    has_drugbank: bool


class ProteinListItemResponse(BaseModel):
    """Decision-oriented projection of a protein for the catalog list (target triage).

    Deliberately slimmer than :class:`ProteinResponse`: it carries only what the list
    table needs plus derived structure / chemical-matter flags, so a page of rows stays
    light instead of shipping every feature, comment and citation per row.
    """

    id: uuid.UUID
    primary_accession: str
    uniprot_url: str | None = None
    entry_name: str | None = None
    is_reviewed: bool
    recommended_name: str | None = None
    short_names: list[str] = []
    ec_numbers: list[str] = []
    gene: GeneSummaryResponse | None = None
    organism_id: uuid.UUID
    strain_id: uuid.UUID | None = None
    seq_length: int
    seq_mass: int | None = None
    protein_existence: ProteinExistence | None = None
    structure: ProteinStructureSummary
    chem: ProteinChemSummary

    @classmethod
    def from_list_item(cls, item: ProteinListItem) -> ProteinListItemResponse:
        p = item.row
        registry = IdentifierRegistry.default()
        names = p.protein_names
        return cls(
            id=p.id,
            primary_accession=p.primary_accession,
            uniprot_url=registry.resolve_url("uniprot", p.primary_accession),
            entry_name=p.entry_name,
            is_reviewed=p.is_reviewed,
            recommended_name=names.recommended,
            short_names=list(names.short_names),
            ec_numbers=list(names.ec_numbers),
            gene=GeneSummaryResponse.from_domain(item.gene) if item.gene is not None else None,
            organism_id=p.organism_id,
            strain_id=p.strain_id,
            seq_length=p.seq_length,
            seq_mass=p.seq_mass,
            protein_existence=p.protein_existence,
            structure=ProteinStructureSummary(
                pdb_count=p.pdb_count,
                has_alphafold=p.has_alphafold,
            ),
            chem=ProteinChemSummary(
                has_chembl=p.has_chembl,
                has_drugbank=p.has_drugbank,
            ),
        )


class ProteinResponse(BaseModel):
    id: uuid.UUID
    primary_accession: str
    uniprot_url: str | None = None
    secondary_accessions: list[str]
    entry_name: str | None = None
    is_reviewed: bool
    protein_names: dict[str, object]
    organism_id: uuid.UUID
    strain_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    gene: GeneSummaryResponse | None = None
    seq_length: int
    seq_mass: int | None = None
    seq_crc64: str | None = None
    protein_existence: ProteinExistence | None = None
    keywords: list[str]
    entry_version: int | None = None
    sequence_version: int | None = None
    cross_references: list[ProteinXrefResponse]
    annotation_score: int | None = None
    fragment: str | None = None
    uniparc_id: str | None = None
    features: list[FeatureResponse] = []
    comments: list[CommentResponse] = []
    isoforms: list[IsoformResponse] = []
    keyword_refs: list[KeywordRefResponse] = []
    citations: list[CitationResponse] = []
    version: int

    @classmethod
    def from_domain(cls, p: Protein, gene: Gene | None = None) -> ProteinResponse:
        registry = IdentifierRegistry.default()
        uniprot_url = registry.resolve_url("uniprot", p.primary_accession)
        protein_names = p.protein_names.to_dict()
        cross_references = [
            ProteinXrefResponse(
                database=x.database,
                accession=x.accession,
                curie=x.to_curie(),
                url=registry.resolve_url(x.database, x.accession),
                properties=dict(x.properties or {}),
            )
            for x in p.cross_references
        ]
        return cls(
            id=p.id,
            primary_accession=p.primary_accession,
            uniprot_url=uniprot_url,
            secondary_accessions=p.secondary_accessions,
            entry_name=p.entry_name,
            is_reviewed=p.is_reviewed,
            protein_names=protein_names,
            organism_id=p.organism_id,
            strain_id=p.strain_id,
            gene_id=p.gene_id,
            gene=GeneSummaryResponse.from_domain(gene) if gene is not None else None,
            seq_length=p.seq_length,
            seq_mass=p.seq_mass,
            seq_crc64=p.seq_crc64,
            protein_existence=p.protein_existence,
            keywords=p.keywords,
            entry_version=p.entry_version,
            sequence_version=p.sequence_version,
            cross_references=cross_references,
            annotation_score=p.annotation_score,
            fragment=p.fragment,
            uniparc_id=p.uniparc_id,
            features=[
                FeatureResponse(
                    feature_type=f.feature_type,
                    start=f.start,
                    end=f.end,
                    start_modifier=f.start_modifier,
                    end_modifier=f.end_modifier,
                    description=f.description,
                    feature_id=f.feature_id,
                    ligand=f.ligand,
                    alternative_sequence=f.alternative_sequence,
                    evidence=f.evidence,
                )
                for f in p.features
            ],
            comments=[
                CommentResponse(
                    comment_type=c.comment_type,
                    text=c.text,
                    payload=c.payload,
                    evidence=c.evidence,
                )
                for c in p.comments
            ],
            isoforms=[
                IsoformResponse(
                    isoform_accession=i.isoform_accession,
                    name=i.name,
                    is_displayed=i.is_displayed,
                    sequence=i.sequence,
                    event=i.event,
                    note=i.note,
                )
                for i in p.isoforms
            ],
            keyword_refs=[
                KeywordRefResponse(
                    kw_id=k.kw_id,
                    name=k.name,
                    category=k.category,
                )
                for k in p.keyword_refs
            ],
            citations=[
                CitationResponse(
                    citation_type=ct.citation_type,
                    title=ct.title,
                    journal=ct.journal,
                    authors=ct.authors,
                    publication_date=ct.publication_date,
                    pubmed_id=ct.pubmed_id,
                    doi=ct.doi,
                    reference_number=ct.reference_number,
                    positions=ct.positions,
                    reference_comments=ct.reference_comments,
                )
                for ct in p.citations
            ],
            version=p.version,
        )


class ProteinNamesBody(BaseModel):
    recommended: str | None = None
    alternative: list[str] = []
    submitted: list[str] = []
    short_names: list[str] = []
    ec_numbers: list[str] = []


class CrossReferenceBody(BaseModel):
    database: str
    accession: str
    properties: dict[str, str] | None = None
    evidence: str | None = None


class CreateProteinBody(BaseModel):
    primary_accession: str
    organism_id: uuid.UUID
    sequence: str
    is_reviewed: bool = False
    secondary_accessions: list[str] = []
    entry_name: str | None = None
    protein_names: ProteinNamesBody | None = None
    strain_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    seq_mass: int | None = None
    seq_crc64: str | None = None
    protein_existence: ProteinExistence | None = None
    keywords: list[str] = []
    entry_version: int | None = None
    sequence_version: int | None = None
    cross_references: list[CrossReferenceBody] = []

    model_config = {"extra": "forbid"}


class UpdateProteinBody(BaseModel):
    sequence: str | None = None
    is_reviewed: bool | None = None
    secondary_accessions: list[str] | None = None
    entry_name: str | None = None
    protein_names: ProteinNamesBody | None = None
    strain_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    seq_mass: int | None = None
    seq_crc64: str | None = None
    protein_existence: ProteinExistence | None = None
    keywords: list[str] | None = None
    entry_version: int | None = None
    sequence_version: int | None = None
    cross_references: list[CrossReferenceBody] | None = None

    model_config = {"extra": "forbid"}


class BulkRecordBody(BaseModel):
    primary_accession: str
    organism_id: uuid.UUID
    sequence: str
    is_reviewed: bool
    source: str
    source_release: str
    source_record_id: str
    source_record_checksum: str
    secondary_accessions: list[str] = []
    entry_name: str | None = None
    protein_names: ProteinNamesBody | None = None
    strain_id: uuid.UUID | None = None
    gene_id: uuid.UUID | None = None
    seq_mass: int | None = None
    seq_crc64: str | None = None
    protein_existence: ProteinExistence | None = None
    keywords: list[str] = []
    entry_version: int | None = None
    sequence_version: int | None = None
    cross_references: list[CrossReferenceBody] = []
    annotation_score: int | None = None
    fragment: str | None = None
    uniparc_id: str | None = None
    features: list[FeatureBody] = []
    comments: list[CommentBody] = []
    isoforms: list[IsoformBody] = []
    keyword_refs: list[KeywordRefBody] = []
    citations: list[CitationBody] = []


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


# Route ordering: /resolve/{identifier} BEFORE /{accession} to avoid path-param shadowing.


@router.get("/resolve/{identifier}", response_model=ProteinResponse)
async def resolve_protein(
    identifier: str,
    auth: AuthDep,
    use_case: ResolveProteinIdDep,
) -> ProteinResponse:
    query = ResolveProteinIdQuery(identifier=identifier)
    protein = result_to_response(await use_case(query, auth=auth))
    return ProteinResponse.from_domain(protein)


@router.get("", response_model=PaginatedResponse[ProteinListItemResponse])
async def list_proteins(
    auth: AuthDep,
    use_case: ListProteinsDep,
    organism_id: uuid.UUID | None = None,
    strain_id: uuid.UUID | None = None,
    gene_id: uuid.UUID | None = None,
    reviewed: bool | None = None,
    min_length: int | None = None,
    max_length: int | None = None,
    xref_db: str | None = None,
    has_structure: bool | None = None,
    is_enzyme: bool | None = None,
    go_term: str | None = None,
    descendants: bool = False,
    keyword: str | None = None,
    q: str | None = None,
    tags: list[uuid.UUID] | None = Query(default=None),
    tag_logic: Literal["any", "all"] = "any",
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[ProteinListItemResponse]:
    query = ListProteinsQuery(
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit, max_size=BULK_PAGE_SIZE),
        organism_id=organism_id,
        strain_id=strain_id,
        gene_id=gene_id,
        is_reviewed=reviewed,
        min_length=min_length,
        max_length=max_length,
        xref_db=xref_db,
        has_structure=has_structure,
        is_enzyme=is_enzyme,
        go_term=go_term,
        descendants=descendants,
        keyword=keyword,
        search=q.strip() if q and q.strip() else None,
        tag_ids=tuple(tags) if tags else (),
        match_all=tag_logic == "all",
    )
    page = result_to_response(await use_case(query, auth=auth))
    return PaginatedResponse(
        items=[ProteinListItemResponse.from_list_item(item) for item in page.items],
        next_cursor=page.next_cursor,
        total_count=page.total_count,
    )


@router.post("/bulk", response_model=BulkUpsertResponse)
async def bulk_upsert_proteins(
    body: BulkUpsertBody,
    auth: AuthDep,
    use_case: BulkUpsertProteinsDep,
) -> BulkUpsertResponse:
    command = BulkUpsertProteinsCommand(
        records=tuple(
            ProteinImportRecord(
                primary_accession=r.primary_accession,
                organism_id=r.organism_id,
                sequence=r.sequence,
                is_reviewed=r.is_reviewed,
                source=r.source,
                source_release=r.source_release,
                source_record_id=r.source_record_id,
                source_record_checksum=r.source_record_checksum,
                secondary_accessions=tuple(r.secondary_accessions),
                entry_name=r.entry_name,
                protein_names=(
                    ProteinNames(
                        recommended=r.protein_names.recommended,
                        alternative=tuple(r.protein_names.alternative),
                        submitted=tuple(r.protein_names.submitted),
                        short_names=tuple(r.protein_names.short_names),
                        ec_numbers=tuple(r.protein_names.ec_numbers),
                    )
                    if r.protein_names is not None
                    else None
                ),
                strain_id=r.strain_id,
                gene_id=r.gene_id,
                seq_mass=r.seq_mass,
                seq_crc64=r.seq_crc64,
                protein_existence=r.protein_existence,
                keywords=tuple(r.keywords),
                entry_version=r.entry_version,
                sequence_version=r.sequence_version,
                cross_references=tuple(
                    CrossReference(
                        database=xr.database,
                        accession=xr.accession,
                        properties=xr.properties,
                        evidence=xr.evidence,
                    )
                    for xr in r.cross_references
                ),
                annotation_score=r.annotation_score,
                fragment=r.fragment,
                uniparc_id=r.uniparc_id,
                features=tuple(
                    ProteinFeature(
                        feature_type=f.feature_type,
                        start=f.start,
                        end=f.end,
                        start_modifier=f.start_modifier,
                        end_modifier=f.end_modifier,
                        description=f.description,
                        feature_id=f.feature_id,
                        ligand=f.ligand,
                        alternative_sequence=f.alternative_sequence,
                        evidence=f.evidence,
                    )
                    for f in r.features
                ),
                comments=tuple(
                    ProteinComment(
                        comment_type=c.comment_type,
                        text=c.text,
                        payload=c.payload,
                        evidence=c.evidence,
                    )
                    for c in r.comments
                ),
                isoforms=tuple(
                    ProteinIsoform(
                        isoform_accession=i.isoform_accession,
                        name=i.name,
                        is_displayed=i.is_displayed,
                        sequence=i.sequence,
                        event=i.event,
                        note=i.note,
                    )
                    for i in r.isoforms
                ),
                keyword_refs=tuple(
                    ProteinKeyword(
                        kw_id=k.kw_id,
                        name=k.name,
                        category=k.category,
                    )
                    for k in r.keyword_refs
                ),
                citations=tuple(
                    ProteinCitation(
                        citation_type=ct.citation_type,
                        title=ct.title,
                        journal=ct.journal,
                        authors=ct.authors,
                        publication_date=ct.publication_date,
                        pubmed_id=ct.pubmed_id,
                        doi=ct.doi,
                        reference_number=ct.reference_number,
                        positions=ct.positions,
                        reference_comments=ct.reference_comments,
                    )
                    for ct in r.citations
                ),
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


@router.post("", response_model=ProteinResponse, status_code=201)
async def create_protein(
    body: CreateProteinBody,
    auth: AuthDep,
    use_case: CreateProteinDep,
) -> ProteinResponse:
    protein_names: ProteinNames | None = None
    if body.protein_names is not None:
        protein_names = ProteinNames(
            recommended=body.protein_names.recommended,
            alternative=tuple(body.protein_names.alternative),
            submitted=tuple(body.protein_names.submitted),
            short_names=tuple(body.protein_names.short_names),
            ec_numbers=tuple(body.protein_names.ec_numbers),
        )
    cross_references = [
        CrossReference(
            database=xr.database,
            accession=xr.accession,
            properties=xr.properties,
            evidence=xr.evidence,
        )
        for xr in body.cross_references
    ]
    command = CreateProteinCommand(
        primary_accession=body.primary_accession,
        organism_id=body.organism_id,
        sequence=body.sequence,
        is_reviewed=body.is_reviewed,
        secondary_accessions=body.secondary_accessions,
        entry_name=body.entry_name,
        protein_names=protein_names,
        strain_id=body.strain_id,
        gene_id=body.gene_id,
        seq_mass=body.seq_mass,
        seq_crc64=body.seq_crc64,
        protein_existence=body.protein_existence,
        keywords=body.keywords,
        entry_version=body.entry_version,
        sequence_version=body.sequence_version,
        cross_references=cross_references,
    )
    protein = result_to_response(await use_case(command, auth=auth))
    return ProteinResponse.from_domain(protein)


@router.get("/{accession}")
async def get_protein(
    accession: str,
    auth: AuthDep,
    use_case: GetProteinDep,
    format: str | None = None,
) -> Response:
    query = GetProteinQuery(accession=accession)
    protein = result_to_response(await use_case(query, auth=auth))
    if format == "fasta":
        return PlainTextResponse(protein.to_fasta(), media_type="text/x-fasta")
    return JSONResponse(content=ProteinResponse.from_domain(protein).model_dump(mode="json"))


@router.patch("/{accession}", response_model=ProteinResponse)
async def update_protein(
    accession: str,
    body: UpdateProteinBody,
    auth: AuthDep,
    use_case: UpdateProteinDep,
) -> ProteinResponse:
    provided = body.model_fields_set

    protein_names: ProteinNames | None | object = UNSET
    if "protein_names" in provided:
        if body.protein_names is not None:
            protein_names = ProteinNames(
                recommended=body.protein_names.recommended,
                alternative=tuple(body.protein_names.alternative),
                submitted=tuple(body.protein_names.submitted),
                short_names=tuple(body.protein_names.short_names),
                ec_numbers=tuple(body.protein_names.ec_numbers),
            )
        else:
            protein_names = None

    cross_references: list[CrossReference] | None = None
    if "cross_references" in provided and body.cross_references is not None:
        cross_references = [
            CrossReference(
                database=xr.database,
                accession=xr.accession,
                properties=xr.properties,
                evidence=xr.evidence,
            )
            for xr in body.cross_references
        ]

    protein_existence: ProteinExistence | None | object = UNSET
    if "protein_existence" in provided:
        protein_existence = body.protein_existence

    command = UpdateProteinCommand(
        accession=accession,
        sequence=body.sequence if "sequence" in provided else None,
        is_reviewed=body.is_reviewed if "is_reviewed" in provided else None,
        secondary_accessions=(
            body.secondary_accessions if "secondary_accessions" in provided else None
        ),
        entry_name=body.entry_name if "entry_name" in provided else UNSET,
        protein_names=protein_names,
        strain_id=body.strain_id if "strain_id" in provided else UNSET,
        gene_id=body.gene_id if "gene_id" in provided else UNSET,
        seq_mass=body.seq_mass if "seq_mass" in provided else UNSET,
        seq_crc64=body.seq_crc64 if "seq_crc64" in provided else UNSET,
        protein_existence=protein_existence,
        keywords=body.keywords if "keywords" in provided else None,
        entry_version=body.entry_version if "entry_version" in provided else UNSET,
        sequence_version=body.sequence_version if "sequence_version" in provided else UNSET,
        cross_references=cross_references,
    )
    protein = result_to_response(await use_case(command, auth=auth))
    return ProteinResponse.from_domain(protein)
