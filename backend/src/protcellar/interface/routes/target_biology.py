"""Target-biology read endpoints — typed records bundled per gene / per protein."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from protcellar.application.protein_catalog.get_gene import GetGeneQuery
from protcellar.application.target_biology.crud import RecordKind
from protcellar.application.target_biology.get_gene_target_biology import (
    GetGeneTargetBiologyQuery,
)
from protcellar.application.target_biology.get_protein_target_biology import (
    GetProteinTargetBiologyQuery,
)
from protcellar.application.target_biology.list_records import ListTargetBiologyRecordsQuery
from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.errors import NotFoundError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.shared.provenance import (
    Citation,
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.hypomorph import Hypomorph
from protcellar.domain.target_biology.protein_activity_assay import ProteinActivityAssay
from protcellar.domain.target_biology.protein_production import ProteinProduction
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure
from protcellar.domain.target_biology.vulnerability import Vulnerability
from protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.protein_repository import (
    SQLAlchemyProteinRepository,
)
from protcellar.interface.dependencies import (
    AuthDep,
    CreateTargetBiologyRecordDep,
    DeleteTargetBiologyRecordDep,
    GetGeneDep,
    GetGeneTargetBiologyDep,
    GetProteinTargetBiologyDep,
    ListTargetBiologyRecordsDep,
    SuggestedValuesReaderDep,
    UoWDep,
    UpdateTargetBiologyRecordDep,
)
from protcellar.interface.error_handlers import result_to_response
from protcellar.interface.pagination import (
    BULK_PAGE_SIZE,
    PaginatedResponse,
    clamp_limit,
    parse_cursor,
)

router = APIRouter(prefix="/api/v1", tags=["target-biology"])


# --- Shared value-object responses -----------------------------------------


class ProvenanceCitationResponse(BaseModel):
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    label: str | None = None


class ProvenanceResponse(BaseModel):
    source_type: str
    generation_method: GenerationMethod
    citations: list[ProvenanceCitationResponse]
    contributor_researcher: str | None = None
    contributor_organization_id: uuid.UUID | None = None
    observed_on: date | None = None
    note: str | None = None

    @classmethod
    def from_domain(cls, p: Provenance) -> ProvenanceResponse:
        return cls(
            source_type=p.source_type.value,
            generation_method=p.generation_method,
            citations=[
                ProvenanceCitationResponse(pmid=c.pmid, doi=c.doi, url=c.url, label=c.label)
                for c in p.citations
            ],
            contributor_researcher=p.contributor_researcher,
            contributor_organization_id=p.contributor_organization_id,
            observed_on=p.observed_on,
            note=p.note,
        )


class CompoundRefResponse(BaseModel):
    compound_id: uuid.UUID
    name: str | None = None

    @classmethod
    def from_domain(cls, c: CompoundRef) -> CompoundRefResponse:
        return cls(compound_id=c.compound_id, name=c.name)


# --- Gene-side record responses --------------------------------------------


class EssentialityResponse(BaseModel):
    id: uuid.UUID
    gene_id: uuid.UUID
    classification: str
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int
    is_shared: bool

    @classmethod
    def from_domain(cls, e: Essentiality) -> EssentialityResponse:
        return cls(
            id=e.id,
            gene_id=e.gene_id,
            classification=e.classification.value,
            condition=e.condition,
            method=e.method,
            confidence=e.confidence,
            provenance=ProvenanceResponse.from_domain(e.provenance),
            extensions=e.extensions,
            version=e.version,
            is_shared=(e.workspace_id == SHARED_WORKSPACE_ID),
        )


class VulnerabilityResponse(BaseModel):
    id: uuid.UUID
    gene_id: uuid.UUID
    vulnerability_score: float | None = None
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int
    is_shared: bool

    @classmethod
    def from_domain(cls, v: Vulnerability) -> VulnerabilityResponse:
        return cls(
            id=v.id,
            gene_id=v.gene_id,
            vulnerability_score=v.vulnerability_score,
            condition=v.condition,
            method=v.method,
            confidence=v.confidence,
            provenance=ProvenanceResponse.from_domain(v.provenance),
            extensions=v.extensions,
            version=v.version,
            is_shared=(v.workspace_id == SHARED_WORKSPACE_ID),
        )


class HypomorphResponse(BaseModel):
    id: uuid.UUID
    gene_id: uuid.UUID
    growth_defect: bool
    growth_defect_severity: str | None = None
    knockdown_strain_id: uuid.UUID | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int
    is_shared: bool

    @classmethod
    def from_domain(cls, h: Hypomorph) -> HypomorphResponse:
        return cls(
            id=h.id,
            gene_id=h.gene_id,
            growth_defect=h.growth_defect,
            growth_defect_severity=h.growth_defect_severity,
            knockdown_strain_id=h.knockdown_strain_id,
            condition=h.condition,
            method=h.method,
            provenance=ProvenanceResponse.from_domain(h.provenance),
            extensions=h.extensions,
            version=h.version,
            is_shared=(h.workspace_id == SHARED_WORKSPACE_ID),
        )


class CrispriStrainResponse(BaseModel):
    id: uuid.UUID
    name: str
    target_gene_id: uuid.UUID
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int
    is_shared: bool

    @classmethod
    def from_domain(cls, s: CrispriStrain) -> CrispriStrainResponse:
        return cls(
            id=s.id,
            name=s.name,
            target_gene_id=s.target_gene_id,
            provenance=ProvenanceResponse.from_domain(s.provenance),
            extensions=s.extensions,
            version=s.version,
            is_shared=(s.workspace_id == SHARED_WORKSPACE_ID),
        )


class ResistanceMutationResponse(BaseModel):
    id: uuid.UUID
    gene_id: uuid.UUID
    mutation: str
    compound: CompoundRefResponse | None = None
    mic_shift: float | None = None
    parent_strain: str | None = None
    protein_coordinate: str | None = None
    method: str | None = None
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int
    is_shared: bool

    @classmethod
    def from_domain(cls, m: ResistanceMutation) -> ResistanceMutationResponse:
        return cls(
            id=m.id,
            gene_id=m.gene_id,
            mutation=m.mutation,
            compound=CompoundRefResponse.from_domain(m.compound) if m.compound else None,
            mic_shift=m.mic_shift,
            parent_strain=m.parent_strain,
            protein_coordinate=m.protein_coordinate,
            method=m.method,
            provenance=ProvenanceResponse.from_domain(m.provenance),
            extensions=m.extensions,
            version=m.version,
            is_shared=(m.workspace_id == SHARED_WORKSPACE_ID),
        )


# --- Protein-side record responses -----------------------------------------


class ProteinProductionResponse(BaseModel):
    id: uuid.UUID
    protein_id: uuid.UUID
    status: str
    expression_host: str | None = None
    purity: float | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int
    is_shared: bool

    @classmethod
    def from_domain(cls, p: ProteinProduction) -> ProteinProductionResponse:
        return cls(
            id=p.id,
            protein_id=p.protein_id,
            status=p.status,
            expression_host=p.expression_host,
            purity=p.purity,
            condition=p.condition,
            method=p.method,
            provenance=ProvenanceResponse.from_domain(p.provenance),
            extensions=p.extensions,
            version=p.version,
            is_shared=(p.workspace_id == SHARED_WORKSPACE_ID),
        )


class ProteinActivityAssayResponse(BaseModel):
    id: uuid.UUID
    protein_id: uuid.UUID
    activity_measured: str
    readout: str | None = None
    throughput: str | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int
    is_shared: bool

    @classmethod
    def from_domain(cls, a: ProteinActivityAssay) -> ProteinActivityAssayResponse:
        return cls(
            id=a.id,
            protein_id=a.protein_id,
            activity_measured=a.activity_measured,
            readout=a.readout,
            throughput=a.throughput,
            condition=a.condition,
            method=a.method,
            provenance=ProvenanceResponse.from_domain(a.provenance),
            extensions=a.extensions,
            version=a.version,
            is_shared=(a.workspace_id == SHARED_WORKSPACE_ID),
        )


class UnpublishedStructureResponse(BaseModel):
    id: uuid.UUID
    protein_id: uuid.UUID
    method: str | None = None
    resolution: float | None = None
    ligands: list[CompoundRefResponse]
    is_published: bool
    is_experimental: bool
    provenance: ProvenanceResponse
    extensions: dict[str, Any]
    version: int
    is_shared: bool

    @classmethod
    def from_domain(cls, s: UnpublishedStructure) -> UnpublishedStructureResponse:
        return cls(
            id=s.id,
            protein_id=s.protein_id,
            method=s.method,
            resolution=s.resolution,
            ligands=[CompoundRefResponse.from_domain(lig) for lig in s.ligands],
            is_published=s.is_published,
            is_experimental=s.is_experimental,
            provenance=ProvenanceResponse.from_domain(s.provenance),
            extensions=s.extensions,
            version=s.version,
            is_shared=(s.workspace_id == SHARED_WORKSPACE_ID),
        )


# --- Bundles ----------------------------------------------------------------


class GeneTargetBiologyResponse(BaseModel):
    essentiality: list[EssentialityResponse]
    vulnerability: list[VulnerabilityResponse]
    hypomorph: list[HypomorphResponse]
    crispri_strain: list[CrispriStrainResponse]
    resistance_mutation: list[ResistanceMutationResponse]


class ProteinTargetBiologyResponse(BaseModel):
    protein_production: list[ProteinProductionResponse]
    protein_activity_assay: list[ProteinActivityAssayResponse]
    unpublished_structure: list[UnpublishedStructureResponse]


# The bulk list route (``GET /target-biology/{kind}``) returns one of these eight
# per item, depending on ``kind`` — see ``_to_list_item`` below.
TargetBiologyListItem = (
    EssentialityResponse
    | VulnerabilityResponse
    | HypomorphResponse
    | CrispriStrainResponse
    | ResistanceMutationResponse
    | ProteinProductionResponse
    | ProteinActivityAssayResponse
    | UnpublishedStructureResponse
)


# --- Inbound write bodies ---------------------------------------------------


class ProvenanceCitationBody(BaseModel):
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    label: str | None = None


# NOTE: no `generation_method` here — an edit submitted through the form must
# re-attribute the row to a human (to_domain() defaults it to MANUAL). See Plan A.
class ProvenanceBody(BaseModel):
    source_type: ProvenanceSourceType
    citations: list[ProvenanceCitationBody] = []
    contributor_researcher: str | None = None
    observed_on: date | None = None
    note: str | None = None

    def to_domain(self) -> Provenance:
        cites = tuple(
            Citation(
                pmid=c.pmid or None,
                doi=c.doi or None,
                url=c.url or None,
                label=c.label or None,
            )
            for c in self.citations
            if any((c.pmid, c.doi, c.url, c.label))
        )
        return Provenance(
            source_type=self.source_type,
            citations=cites,
            contributor_researcher=self.contributor_researcher or None,
            observed_on=self.observed_on,
            note=self.note or None,
        )


class CompoundRefBody(BaseModel):
    """Inbound reference to a compound held in a chemistry catalog.

    This service does not resolve the id — it stores the caller's pair verbatim, the
    same self-contained reference `CompoundRef` already models. `name` is a
    denormalized label for display; `compound_id` is the identity.
    """

    compound_id: uuid.UUID
    name: str | None = None

    def to_domain(self) -> CompoundRef:
        return CompoundRef(compound_id=self.compound_id, name=self.name or None)


class EssentialityWriteBody(BaseModel):
    classification: EssentialityClass
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceBody


class EssentialityPatchBody(BaseModel):
    classification: EssentialityClass | None = None
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceBody | None = None
    version: int | None = None

    model_config = {"extra": "forbid"}


class VulnerabilityWriteBody(BaseModel):
    vulnerability_score: float | None = None
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceBody


class VulnerabilityPatchBody(BaseModel):
    vulnerability_score: float | None = None
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceBody | None = None
    version: int | None = None

    model_config = {"extra": "forbid"}


class HypomorphWriteBody(BaseModel):
    growth_defect: bool
    growth_defect_severity: str | None = None
    knockdown_strain_id: uuid.UUID | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody


class HypomorphPatchBody(BaseModel):
    growth_defect: bool | None = None
    growth_defect_severity: str | None = None
    knockdown_strain_id: uuid.UUID | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody | None = None
    version: int | None = None

    model_config = {"extra": "forbid"}


class CrispriStrainWriteBody(BaseModel):
    name: str
    provenance: ProvenanceBody


class CrispriStrainPatchBody(BaseModel):
    name: str | None = None
    provenance: ProvenanceBody | None = None
    version: int | None = None

    model_config = {"extra": "forbid"}


class ResistanceMutationWriteBody(BaseModel):
    mutation: str
    compound: CompoundRefBody | None = None
    mic_shift: float | None = None
    parent_strain: str | None = None
    protein_coordinate: str | None = None
    method: str | None = None
    provenance: ProvenanceBody


class ResistanceMutationPatchBody(BaseModel):
    mutation: str | None = None
    compound: CompoundRefBody | None = None
    mic_shift: float | None = None
    parent_strain: str | None = None
    protein_coordinate: str | None = None
    method: str | None = None
    provenance: ProvenanceBody | None = None
    version: int | None = None

    model_config = {"extra": "forbid"}


class ProteinProductionWriteBody(BaseModel):
    status: str
    expression_host: str | None = None
    purity: float | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody


class ProteinProductionPatchBody(BaseModel):
    status: str | None = None
    expression_host: str | None = None
    purity: float | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody | None = None
    version: int | None = None

    model_config = {"extra": "forbid"}


class ProteinActivityAssayWriteBody(BaseModel):
    activity_measured: str
    readout: str | None = None
    throughput: str | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody


class ProteinActivityAssayPatchBody(BaseModel):
    activity_measured: str | None = None
    readout: str | None = None
    throughput: str | None = None
    condition: str | None = None
    method: str | None = None
    provenance: ProvenanceBody | None = None
    version: int | None = None

    model_config = {"extra": "forbid"}


class UnpublishedStructureWriteBody(BaseModel):
    method: str | None = None
    resolution: float | None = None
    ligands: list[CompoundRefBody] = []
    is_published: bool = False
    is_experimental: bool = True
    provenance: ProvenanceBody


class UnpublishedStructurePatchBody(BaseModel):
    method: str | None = None
    resolution: float | None = None
    ligands: list[CompoundRefBody] | None = None
    is_published: bool | None = None
    is_experimental: bool | None = None
    provenance: ProvenanceBody | None = None
    version: int | None = None

    model_config = {"extra": "forbid"}


# Value-object fields whose patch bodies must be converted to domain objects.
# model_dump() would leave them as plain dicts, which the aggregates would store verbatim.
_VALUE_OBJECT_FIELDS = frozenset({"provenance", "compound", "ligands"})


def _patch_updates(body: BaseModel) -> dict[str, Any]:
    """Build the partial-update dict from only the fields the caller actually sent.

    The aggregates already guard every assignment with ``if "x" in fields``, so an
    absent key means "leave it alone". This is what keeps an edit to one field from
    re-stamping ``generation_method`` — provenance is only re-attributed when the
    caller submits it.

    ``version`` is stripped: it is the caller's concurrency expectation, not a field.
    """
    updates: dict[str, Any] = body.model_dump(exclude_unset=True)
    updates.pop("version", None)
    for name in _VALUE_OBJECT_FIELDS & set(updates):
        value = getattr(body, name)
        if value is None:
            # provenance is domain-required and ligands' clear idiom is []:
            # a null means "leave alone". compound is nullable — null clears it.
            if name != "compound":
                updates.pop(name)
        elif isinstance(value, list):
            updates[name] = [item.to_domain() for item in value]
        else:
            updates[name] = value.to_domain()
    return updates


# --- Endpoints --------------------------------------------------------------

# Registered first (and its literal path is only two segments) so it is never
# shadowed by the parameterized /target-biology/{kind}/... routes below it.


@router.get("/target-biology/schema")
async def get_target_biology_schema(
    auth: AuthDep,
    reader: SuggestedValuesReaderDep,
) -> dict[str, Any]:
    """The published write contract: what each record kind accepts, and the values
    already in use for its vocabulary fields. Requires a caller, so the write surface
    is not enumerable anonymously."""
    # Deferred import: target_biology_schema imports the *WriteBody classes from this
    # module, so importing it back at module level here would be circular.
    from protcellar.interface.target_biology_schema import describe_write_surface

    return describe_write_surface(await reader.for_all_kinds(auth.workspace_id))


def _to_list_item(kind: RecordKind, record: Any) -> TargetBiologyListItem:
    """Dispatch a bulk-list row to its per-kind response — the ``kind`` path
    param fixes which of the eight domain types ``record`` actually is.
    """
    match kind:
        case RecordKind.ESSENTIALITY:
            return EssentialityResponse.from_domain(record)
        case RecordKind.VULNERABILITY:
            return VulnerabilityResponse.from_domain(record)
        case RecordKind.HYPOMORPH:
            return HypomorphResponse.from_domain(record)
        case RecordKind.CRISPRI_STRAIN:
            return CrispriStrainResponse.from_domain(record)
        case RecordKind.RESISTANCE_MUTATION:
            return ResistanceMutationResponse.from_domain(record)
        case RecordKind.PROTEIN_PRODUCTION:
            return ProteinProductionResponse.from_domain(record)
        case RecordKind.PROTEIN_ACTIVITY_ASSAY:
            return ProteinActivityAssayResponse.from_domain(record)
        case RecordKind.UNPUBLISHED_STRUCTURE:
            return UnpublishedStructureResponse.from_domain(record)
        case _:  # pragma: no cover — RecordKind's 8 members are all matched above
            raise AssertionError(f"unhandled RecordKind: {kind!r}")


# Registered after /target-biology/schema (above) and before the parameterized
# write routes (below): {kind} would otherwise shadow the literal "schema" path
# segment, since both are two-segment GETs under /target-biology/.
@router.get("/target-biology/{kind}", response_model=PaginatedResponse[TargetBiologyListItem])
async def list_target_biology(
    kind: RecordKind,
    auth: AuthDep,
    use_case: ListTargetBiologyRecordsDep,
    organism_id: uuid.UUID | None = None,
    strain_id: uuid.UUID | None = None,
    gene_id: list[uuid.UUID] | None = Query(default=None),
    protein_id: list[uuid.UUID] | None = Query(default=None),
    cursor: str | None = None,
    limit: int | None = None,
) -> PaginatedResponse[TargetBiologyListItem]:
    """Every record of one kind, across genes/proteins — not just one gene's
    bundle. ``kind`` is validated against ``RecordKind`` by FastAPI before this
    body runs, so an unknown kind 422s with no database round trip.
    """
    query = ListTargetBiologyRecordsQuery(
        kind=kind,
        cursor_id=parse_cursor(cursor),
        limit=clamp_limit(limit, max_size=BULK_PAGE_SIZE),
        gene_ids=tuple(gene_id) if gene_id else (),
        protein_ids=tuple(protein_id) if protein_id else (),
        organism_id=organism_id,
        strain_id=strain_id,
    )
    page = result_to_response(await use_case(query, auth=auth))
    return PaginatedResponse(
        items=[_to_list_item(kind, record) for record in page.items],
        next_cursor=page.next_cursor,
    )


@router.get("/genes/{gene_id}/target-biology", response_model=GeneTargetBiologyResponse)
async def get_gene_target_biology(
    gene_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetGeneTargetBiologyDep,
) -> GeneTargetBiologyResponse:
    bundle = result_to_response(
        await use_case(GetGeneTargetBiologyQuery(gene_id=gene_id), auth=auth)
    )
    return GeneTargetBiologyResponse(
        essentiality=[EssentialityResponse.from_domain(x) for x in bundle.essentiality],
        vulnerability=[VulnerabilityResponse.from_domain(x) for x in bundle.vulnerability],
        hypomorph=[HypomorphResponse.from_domain(x) for x in bundle.hypomorph],
        crispri_strain=[CrispriStrainResponse.from_domain(x) for x in bundle.crispri_strain],
        resistance_mutation=[
            ResistanceMutationResponse.from_domain(x) for x in bundle.resistance_mutation
        ],
    )


@router.get("/proteins/{protein_id}/target-biology", response_model=ProteinTargetBiologyResponse)
async def get_protein_target_biology(
    protein_id: uuid.UUID,
    auth: AuthDep,
    use_case: GetProteinTargetBiologyDep,
) -> ProteinTargetBiologyResponse:
    bundle = result_to_response(
        await use_case(GetProteinTargetBiologyQuery(protein_id=protein_id), auth=auth)
    )
    return ProteinTargetBiologyResponse(
        protein_production=[
            ProteinProductionResponse.from_domain(x) for x in bundle.protein_production
        ],
        protein_activity_assay=[
            ProteinActivityAssayResponse.from_domain(x) for x in bundle.protein_activity_assay
        ],
        unpublished_structure=[
            UnpublishedStructureResponse.from_domain(x) for x in bundle.unpublished_structure
        ],
    )


# --- Write endpoints (admin-only) -------------------------------------------
# Create is nested under the owning gene/protein; update is by record id; a
# single generic delete covers every record kind.


async def _require_readable_gene(gene_id: uuid.UUID, auth: AuthDep, get_gene: GetGeneDep) -> None:
    """Parent-validation guard for the five gene-side creates below: 404s
    (never 403s) when ``gene_id`` doesn't exist or belongs to a workspace the
    caller cannot see. A 403 would confirm the row exists to a caller who may
    not see it — precisely the cross-tenant probe this guard closes.

    Reuses the existing ``GetGene`` query use case (already ``find_readable``
    + ``NotFoundError``, already wired as ``GetGeneDep``) rather than touching
    a repository directly; the fetched ``Gene`` is discarded on success.
    """
    result_to_response(await get_gene(GetGeneQuery(gene_id=gene_id), auth=auth))


async def _require_readable_protein(protein_id: uuid.UUID, auth: AuthDep, uow: UoWDep) -> None:
    """Same guard, protein side.

    Scoped exception: unlike ``GeneRepository``, the application-layer
    ``ProteinRepository`` Protocol (``domain/protein_catalog/repository.py``)
    has no id-based ``find_readable``/``find_owned`` — proteins are addressed
    by accession everywhere else in the API (``GetProtein`` takes
    ``accession: str``). The concrete ``SQLAlchemyProteinRepository`` has
    ``find_readable`` via ``SQLAlchemyRepository``, so this reaches past the
    use-case layer to it directly rather than duplicating a fix for that gap
    here. Remove this by widening the Protocol and adding a
    ``GetProteinById``-shaped query use case, DI registration and Dep alias
    (~5 files) — out of scope for this task.
    """
    async with uow:
        protein = await SQLAlchemyProteinRepository(uow).find_readable(
            auth.workspace_id, protein_id
        )
    if protein is None:
        raise NotFoundError("Protein", str(protein_id))


ExistingGeneDep = Annotated[None, Depends(_require_readable_gene)]
ExistingProteinDep = Annotated[None, Depends(_require_readable_protein)]


@router.post(
    "/genes/{gene_id}/target-biology/essentiality",
    response_model=EssentialityResponse,
    status_code=201,
)
async def create_essentiality(
    gene_id: uuid.UUID,
    body: EssentialityWriteBody,
    auth: AuthDep,
    use_case: CreateTargetBiologyRecordDep,
    _gene: ExistingGeneDep,
) -> EssentialityResponse:
    record = Essentiality.create(
        workspace_id=auth.workspace_id,
        gene_id=gene_id,
        classification=body.classification,
        provenance=body.provenance.to_domain(),
        condition=body.condition,
        method=body.method,
        confidence=body.confidence,
    )
    result = result_to_response(await use_case(RecordKind.ESSENTIALITY, record, auth=auth))
    return EssentialityResponse.from_domain(result)


@router.patch("/target-biology/essentiality/{record_id}", response_model=EssentialityResponse)
async def update_essentiality(
    record_id: uuid.UUID,
    body: EssentialityPatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> EssentialityResponse:
    result = result_to_response(
        await use_case(
            RecordKind.ESSENTIALITY,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
    return EssentialityResponse.from_domain(result)


@router.post(
    "/genes/{gene_id}/target-biology/vulnerability",
    response_model=VulnerabilityResponse,
    status_code=201,
)
async def create_vulnerability(
    gene_id: uuid.UUID,
    body: VulnerabilityWriteBody,
    auth: AuthDep,
    use_case: CreateTargetBiologyRecordDep,
    _gene: ExistingGeneDep,
) -> VulnerabilityResponse:
    record = Vulnerability.create(
        workspace_id=auth.workspace_id,
        gene_id=gene_id,
        provenance=body.provenance.to_domain(),
        vulnerability_score=body.vulnerability_score,
        condition=body.condition,
        method=body.method,
        confidence=body.confidence,
    )
    result = result_to_response(await use_case(RecordKind.VULNERABILITY, record, auth=auth))
    return VulnerabilityResponse.from_domain(result)


@router.patch("/target-biology/vulnerability/{record_id}", response_model=VulnerabilityResponse)
async def update_vulnerability(
    record_id: uuid.UUID,
    body: VulnerabilityPatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> VulnerabilityResponse:
    result = result_to_response(
        await use_case(
            RecordKind.VULNERABILITY,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
    return VulnerabilityResponse.from_domain(result)


@router.post(
    "/genes/{gene_id}/target-biology/hypomorph",
    response_model=HypomorphResponse,
    status_code=201,
)
async def create_hypomorph(
    gene_id: uuid.UUID,
    body: HypomorphWriteBody,
    auth: AuthDep,
    use_case: CreateTargetBiologyRecordDep,
    _gene: ExistingGeneDep,
) -> HypomorphResponse:
    record = Hypomorph.create(
        workspace_id=auth.workspace_id,
        gene_id=gene_id,
        growth_defect=body.growth_defect,
        provenance=body.provenance.to_domain(),
        growth_defect_severity=body.growth_defect_severity,
        knockdown_strain_id=body.knockdown_strain_id,
        condition=body.condition,
        method=body.method,
    )
    result = result_to_response(await use_case(RecordKind.HYPOMORPH, record, auth=auth))
    return HypomorphResponse.from_domain(result)


@router.patch("/target-biology/hypomorph/{record_id}", response_model=HypomorphResponse)
async def update_hypomorph(
    record_id: uuid.UUID,
    body: HypomorphPatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> HypomorphResponse:
    result = result_to_response(
        await use_case(
            RecordKind.HYPOMORPH,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
    return HypomorphResponse.from_domain(result)


@router.post(
    "/genes/{gene_id}/target-biology/crispri_strain",
    response_model=CrispriStrainResponse,
    status_code=201,
)
async def create_crispri_strain(
    gene_id: uuid.UUID,
    body: CrispriStrainWriteBody,
    auth: AuthDep,
    use_case: CreateTargetBiologyRecordDep,
    _gene: ExistingGeneDep,
) -> CrispriStrainResponse:
    record = CrispriStrain.create(
        workspace_id=auth.workspace_id,
        name=body.name,
        target_gene_id=gene_id,
        provenance=body.provenance.to_domain(),
    )
    result = result_to_response(await use_case(RecordKind.CRISPRI_STRAIN, record, auth=auth))
    return CrispriStrainResponse.from_domain(result)


@router.patch("/target-biology/crispri_strain/{record_id}", response_model=CrispriStrainResponse)
async def update_crispri_strain(
    record_id: uuid.UUID,
    body: CrispriStrainPatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> CrispriStrainResponse:
    result = result_to_response(
        await use_case(
            RecordKind.CRISPRI_STRAIN,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
    return CrispriStrainResponse.from_domain(result)


@router.post(
    "/genes/{gene_id}/target-biology/resistance_mutation",
    response_model=ResistanceMutationResponse,
    status_code=201,
)
async def create_resistance_mutation(
    gene_id: uuid.UUID,
    body: ResistanceMutationWriteBody,
    auth: AuthDep,
    use_case: CreateTargetBiologyRecordDep,
    _gene: ExistingGeneDep,
) -> ResistanceMutationResponse:
    record = ResistanceMutation.create(
        workspace_id=auth.workspace_id,
        gene_id=gene_id,
        mutation=body.mutation,
        provenance=body.provenance.to_domain(),
        compound=body.compound.to_domain() if body.compound else None,
        mic_shift=body.mic_shift,
        parent_strain=body.parent_strain,
        protein_coordinate=body.protein_coordinate,
        method=body.method,
    )
    result = result_to_response(await use_case(RecordKind.RESISTANCE_MUTATION, record, auth=auth))
    return ResistanceMutationResponse.from_domain(result)


@router.patch(
    "/target-biology/resistance_mutation/{record_id}",
    response_model=ResistanceMutationResponse,
)
async def update_resistance_mutation(
    record_id: uuid.UUID,
    body: ResistanceMutationPatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> ResistanceMutationResponse:
    result = result_to_response(
        await use_case(
            RecordKind.RESISTANCE_MUTATION,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
    return ResistanceMutationResponse.from_domain(result)


@router.post(
    "/proteins/{protein_id}/target-biology/protein_production",
    response_model=ProteinProductionResponse,
    status_code=201,
)
async def create_protein_production(
    protein_id: uuid.UUID,
    body: ProteinProductionWriteBody,
    auth: AuthDep,
    use_case: CreateTargetBiologyRecordDep,
    _protein: ExistingProteinDep,
) -> ProteinProductionResponse:
    record = ProteinProduction.create(
        workspace_id=auth.workspace_id,
        protein_id=protein_id,
        status=body.status,
        provenance=body.provenance.to_domain(),
        expression_host=body.expression_host,
        purity=body.purity,
        condition=body.condition,
        method=body.method,
    )
    result = result_to_response(await use_case(RecordKind.PROTEIN_PRODUCTION, record, auth=auth))
    return ProteinProductionResponse.from_domain(result)


@router.patch(
    "/target-biology/protein_production/{record_id}",
    response_model=ProteinProductionResponse,
)
async def update_protein_production(
    record_id: uuid.UUID,
    body: ProteinProductionPatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> ProteinProductionResponse:
    result = result_to_response(
        await use_case(
            RecordKind.PROTEIN_PRODUCTION,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
    return ProteinProductionResponse.from_domain(result)


@router.post(
    "/proteins/{protein_id}/target-biology/protein_activity_assay",
    response_model=ProteinActivityAssayResponse,
    status_code=201,
)
async def create_protein_activity_assay(
    protein_id: uuid.UUID,
    body: ProteinActivityAssayWriteBody,
    auth: AuthDep,
    use_case: CreateTargetBiologyRecordDep,
    _protein: ExistingProteinDep,
) -> ProteinActivityAssayResponse:
    record = ProteinActivityAssay.create(
        workspace_id=auth.workspace_id,
        protein_id=protein_id,
        activity_measured=body.activity_measured,
        provenance=body.provenance.to_domain(),
        readout=body.readout,
        throughput=body.throughput,
        condition=body.condition,
        method=body.method,
    )
    result = result_to_response(
        await use_case(RecordKind.PROTEIN_ACTIVITY_ASSAY, record, auth=auth)
    )
    return ProteinActivityAssayResponse.from_domain(result)


@router.patch(
    "/target-biology/protein_activity_assay/{record_id}",
    response_model=ProteinActivityAssayResponse,
)
async def update_protein_activity_assay(
    record_id: uuid.UUID,
    body: ProteinActivityAssayPatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> ProteinActivityAssayResponse:
    result = result_to_response(
        await use_case(
            RecordKind.PROTEIN_ACTIVITY_ASSAY,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
    return ProteinActivityAssayResponse.from_domain(result)


@router.post(
    "/proteins/{protein_id}/target-biology/unpublished_structure",
    response_model=UnpublishedStructureResponse,
    status_code=201,
)
async def create_unpublished_structure(
    protein_id: uuid.UUID,
    body: UnpublishedStructureWriteBody,
    auth: AuthDep,
    use_case: CreateTargetBiologyRecordDep,
    _protein: ExistingProteinDep,
) -> UnpublishedStructureResponse:
    record = UnpublishedStructure.create(
        workspace_id=auth.workspace_id,
        protein_id=protein_id,
        provenance=body.provenance.to_domain(),
        method=body.method,
        resolution=body.resolution,
        ligands=tuple(lig.to_domain() for lig in body.ligands),
        is_published=body.is_published,
        is_experimental=body.is_experimental,
    )
    result = result_to_response(
        await use_case(RecordKind.UNPUBLISHED_STRUCTURE, record, auth=auth)
    )
    return UnpublishedStructureResponse.from_domain(result)


@router.patch(
    "/target-biology/unpublished_structure/{record_id}",
    response_model=UnpublishedStructureResponse,
)
async def update_unpublished_structure(
    record_id: uuid.UUID,
    body: UnpublishedStructurePatchBody,
    auth: AuthDep,
    use_case: UpdateTargetBiologyRecordDep,
) -> UnpublishedStructureResponse:
    result = result_to_response(
        await use_case(
            RecordKind.UNPUBLISHED_STRUCTURE,
            record_id,
            _patch_updates(body),
            auth=auth,
            expected_version=body.version,
        )
    )
    return UnpublishedStructureResponse.from_domain(result)


@router.delete("/target-biology/{kind}/{record_id}", status_code=204)
async def delete_target_biology_record(
    kind: RecordKind,
    record_id: uuid.UUID,
    auth: AuthDep,
    use_case: DeleteTargetBiologyRecordDep,
) -> None:
    result_to_response(await use_case(kind, record_id, auth=auth))
