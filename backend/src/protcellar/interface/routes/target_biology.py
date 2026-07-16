"""Target-biology read endpoints — typed records bundled per gene / per protein."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from protcellar.application.target_biology.crud_essentiality import (
    CreateEssentialityCommand,
    DeleteEssentialityCommand,
    UpdateEssentialityCommand,
)
from protcellar.application.target_biology.get_gene_target_biology import (
    GetGeneTargetBiologyQuery,
)
from protcellar.application.target_biology.get_protein_target_biology import (
    GetProteinTargetBiologyQuery,
)
from protcellar.domain.shared.compound_ref import CompoundRef
from protcellar.domain.shared.provenance import Citation, Provenance, ProvenanceSourceType
from protcellar.domain.target_biology.crispri_strain import CrispriStrain
from protcellar.domain.target_biology.enums import EssentialityClass
from protcellar.domain.target_biology.essentiality import Essentiality
from protcellar.domain.target_biology.hypomorph import Hypomorph
from protcellar.domain.target_biology.protein_activity_assay import ProteinActivityAssay
from protcellar.domain.target_biology.protein_production import ProteinProduction
from protcellar.domain.target_biology.resistance_mutation import ResistanceMutation
from protcellar.domain.target_biology.unpublished_structure import UnpublishedStructure
from protcellar.domain.target_biology.vulnerability import Vulnerability
from protcellar.interface.dependencies import (
    AuthDep,
    CreateEssentialityDep,
    DeleteEssentialityDep,
    GetGeneTargetBiologyDep,
    GetProteinTargetBiologyDep,
    UpdateEssentialityDep,
)
from protcellar.interface.error_handlers import result_to_response

router = APIRouter(prefix="/api/v1", tags=["target-biology"])


# --- Shared value-object responses -----------------------------------------


class ProvenanceCitationResponse(BaseModel):
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    label: str | None = None


class ProvenanceResponse(BaseModel):
    source_type: str
    citations: list[ProvenanceCitationResponse]
    contributor_researcher: str | None = None
    contributor_organization_id: uuid.UUID | None = None
    observed_on: date | None = None
    note: str | None = None

    @classmethod
    def from_domain(cls, p: Provenance) -> ProvenanceResponse:
        return cls(
            source_type=p.source_type.value,
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
        )


class CrispriStrainResponse(BaseModel):
    id: uuid.UUID
    name: str
    target_gene_id: uuid.UUID
    provenance: ProvenanceResponse
    extensions: dict[str, Any]

    @classmethod
    def from_domain(cls, s: CrispriStrain) -> CrispriStrainResponse:
        return cls(
            id=s.id,
            name=s.name,
            target_gene_id=s.target_gene_id,
            provenance=ProvenanceResponse.from_domain(s.provenance),
            extensions=s.extensions,
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


# --- Inbound write bodies ---------------------------------------------------


class ProvenanceCitationBody(BaseModel):
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    label: str | None = None


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


class EssentialityWriteBody(BaseModel):
    classification: EssentialityClass
    condition: str | None = None
    method: str | None = None
    confidence: float | None = None
    provenance: ProvenanceBody


# --- Endpoints --------------------------------------------------------------


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


# --- Essentiality write endpoints (admin-only) ------------------------------


@router.post(
    "/genes/{gene_id}/target-biology/essentiality",
    response_model=EssentialityResponse,
    status_code=201,
)
async def create_essentiality(
    gene_id: uuid.UUID,
    body: EssentialityWriteBody,
    auth: AuthDep,
    use_case: CreateEssentialityDep,
) -> EssentialityResponse:
    command = CreateEssentialityCommand(
        gene_id=gene_id,
        classification=body.classification,
        provenance=body.provenance.to_domain(),
        condition=body.condition,
        method=body.method,
        confidence=body.confidence,
    )
    record = result_to_response(await use_case(command, auth=auth))
    return EssentialityResponse.from_domain(record)


@router.patch(
    "/target-biology/essentiality/{record_id}", response_model=EssentialityResponse
)
async def update_essentiality(
    record_id: uuid.UUID,
    body: EssentialityWriteBody,
    auth: AuthDep,
    use_case: UpdateEssentialityDep,
) -> EssentialityResponse:
    command = UpdateEssentialityCommand(
        id=record_id,
        classification=body.classification,
        provenance=body.provenance.to_domain(),
        condition=body.condition,
        method=body.method,
        confidence=body.confidence,
    )
    record = result_to_response(await use_case(command, auth=auth))
    return EssentialityResponse.from_domain(record)


@router.delete("/target-biology/essentiality/{record_id}", status_code=204)
async def delete_essentiality(
    record_id: uuid.UUID,
    auth: AuthDep,
    use_case: DeleteEssentialityDep,
) -> None:
    result_to_response(await use_case(DeleteEssentialityCommand(id=record_id), auth=auth))
