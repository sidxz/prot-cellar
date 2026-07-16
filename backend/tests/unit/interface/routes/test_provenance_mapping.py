"""Provenance ↔ API mapping: the read model exposes generation_method; the write
model does not, so an edit through the form re-attributes the row to a human."""

from protcellar.domain.shared.provenance import (
    GenerationMethod,
    Provenance,
    ProvenanceSourceType,
)
from protcellar.interface.routes.target_biology import ProvenanceBody, ProvenanceResponse


def test_response_exposes_generation_method() -> None:
    prov = Provenance(
        source_type=ProvenanceSourceType.PUBLISHED,
        generation_method=GenerationMethod.IMPORTED,
    )
    resp = ProvenanceResponse.from_domain(prov)
    assert resp.generation_method is GenerationMethod.IMPORTED


def test_body_to_domain_is_always_manual() -> None:
    # The honesty rule: the inbound edit payload carries no generation_method,
    # so a human edit routes through to_domain() and re-defaults to manual.
    body = ProvenanceBody(source_type=ProvenanceSourceType.PUBLISHED)
    assert body.to_domain().generation_method is GenerationMethod.MANUAL
