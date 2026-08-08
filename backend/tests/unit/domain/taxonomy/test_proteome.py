"""Domain unit tests for the Proteome aggregate."""

from __future__ import annotations

import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import SHARED_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import ProteomeType
from protcellar.domain.taxonomy.proteome import Proteome


def test_create_reference_proteome() -> None:
    org = uuid.uuid4()
    p = Proteome.create(
        uniprot_proteome_id="UP000005640",
        organism_id=org,
        proteome_type=ProteomeType.REFERENCE,
        is_reference=True,
    )
    assert p.workspace_id == SHARED_WORKSPACE_ID
    assert p.uniprot_proteome_id == "UP000005640"


def test_invalid_proteome_id_rejected() -> None:
    with pytest.raises(ValidationError):
        Proteome.create(
            uniprot_proteome_id="NOTAPROTEOME",
            organism_id=uuid.uuid4(),
            proteome_type=ProteomeType.REFERENCE,
            is_reference=True,
        )
