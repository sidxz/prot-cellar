"""(De)serialise the shared Provenance VO to/from a JSON column.

Mirrors protein_catalog/_annotation_json.py — keeps repositories free of
mapping boilerplate.
"""

from __future__ import annotations

import uuid
from datetime import date

from protcellar.domain.shared.provenance import Citation, Provenance, ProvenanceSourceType


def provenance_to_json(p: Provenance) -> dict[str, object]:
    return {
        "source_type": p.source_type.value,
        "citations": [
            {"pmid": c.pmid, "doi": c.doi, "url": c.url, "label": c.label} for c in p.citations
        ],
        "contributor_researcher": p.contributor_researcher,
        "contributor_organization_id": (
            str(p.contributor_organization_id) if p.contributor_organization_id else None
        ),
        "observed_on": p.observed_on.isoformat() if p.observed_on else None,
        "note": p.note,
    }


def provenance_from_json(data: dict[str, object] | None) -> Provenance | None:
    if not data:
        return None
    org = data.get("contributor_organization_id")
    observed = data.get("observed_on")
    citations_raw: list[dict[str, object]] = data.get("citations") or []  # type: ignore[assignment]
    return Provenance(
        source_type=ProvenanceSourceType(str(data["source_type"])),
        citations=tuple(
            Citation(
                pmid=_opt(c.get("pmid")),
                doi=_opt(c.get("doi")),
                url=_opt(c.get("url")),
                label=_opt(c.get("label")),
            )
            for c in citations_raw
        ),
        contributor_researcher=_opt(data.get("contributor_researcher")),
        contributor_organization_id=uuid.UUID(str(org)) if org else None,
        observed_on=date.fromisoformat(str(observed)) if observed else None,
        note=_opt(data.get("note")),
    )


def _opt(value: object) -> str | None:
    return str(value) if value is not None else None
