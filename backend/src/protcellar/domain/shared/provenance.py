"""Shared scientific-provenance value objects (who observed a fact, cited where).

Distinct from the persistence-layer ``ProvenanceMixin`` (import lineage:
source/release/checksum). A typed record may carry both.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from protcellar.domain.shared.errors import ValidationError


class ProvenanceSourceType(StrEnum):
    PUBLISHED = "published"
    PREPRINT = "preprint"
    PRIVATE_COMM = "private_comm"
    INTERNAL = "internal"
    PATENT = "patent"


@dataclass(frozen=True, kw_only=True)
class Citation:
    """A literature reference. At least one identifier must be present."""

    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        if not any((self.pmid, self.doi, self.url, self.label)):
            raise ValidationError("Citation requires at least one of pmid/doi/url/label")


@dataclass(frozen=True, kw_only=True)
class Provenance:
    """Where a target-biology fact came from — the shared provenance envelope."""

    source_type: ProvenanceSourceType
    citations: tuple[Citation, ...] = ()
    contributor_researcher: str | None = None
    contributor_organization_id: uuid.UUID | None = None
    observed_on: date | None = None
    note: str | None = None
