import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.taxonomy.strain import Strain


def test_create_requires_species_anchor_and_name() -> None:
    ws, species = uuid.uuid4(), uuid.uuid4()
    strain = Strain.create(workspace_id=ws, species_organism_id=species, name="K-12 MG1655")
    assert strain.species_organism_id == species
    assert strain.workspace_id == ws
    assert strain.version == 1
    with pytest.raises(ValidationError):
        Strain.create(workspace_id=ws, species_organism_id=species, name="  ")
