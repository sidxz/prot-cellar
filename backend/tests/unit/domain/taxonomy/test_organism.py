import uuid

import pytest

from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID
from protcellar.domain.taxonomy.enums import NameClass, OrganismSource
from protcellar.domain.taxonomy.events import OrganismCreated
from protcellar.domain.taxonomy.organism import Organism


def test_create_human_node() -> None:
    org = Organism.create(
        ncbi_tax_id=9606, rank="species", scientific_name="Homo sapiens",
        source=OrganismSource.NCBI,
    )
    assert org.ncbi_tax_id == 9606
    assert org.workspace_id == GLOBAL_WORKSPACE_ID
    assert org.version == 1
    # scientific name is auto-added as a name row
    assert any(n.name_class == NameClass.SCIENTIFIC_NAME and n.name == "Homo sapiens"
               for n in org.names)
    events = org.collect_events()
    assert len(events) == 1 and isinstance(events[0], OrganismCreated)


def test_create_requires_scientific_name() -> None:
    with pytest.raises(ValidationError):
        Organism.create(ncbi_tax_id=1, rank="no rank", scientific_name="  ",
                        source=OrganismSource.NCBI)


def test_add_common_name() -> None:
    org = Organism.create(ncbi_tax_id=9606, rank="species", scientific_name="Homo sapiens",
                          source=OrganismSource.NCBI)
    org.add_name("human", NameClass.COMMON_NAME)
    assert any(n.name == "human" and n.name_class == NameClass.COMMON_NAME for n in org.names)


def test_mark_merged_into_redirect() -> None:
    org = Organism.create(ncbi_tax_id=12345, rank="species", scientific_name="Old name",
                          source=OrganismSource.NCBI)
    target = uuid.uuid4()
    org.mark_merged_into(target)
    assert org.is_merged is True
    assert org.merged_into_id == target


def test_update_blank_rank_raises() -> None:
    org = Organism.create(ncbi_tax_id=9606, rank="species", scientific_name="Homo sapiens",
                          source=OrganismSource.NCBI)
    with pytest.raises(ValidationError):
        org.update(rank="  ")
