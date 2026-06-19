import uuid

import pytest

from protcellar.domain.protein_catalog.events import GeneCreated
from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


def test_create_gene() -> None:
    organism = uuid.uuid4()
    gene = Gene.create(primary_name="TP53", organism_id=organism, synonyms=["P53", "LFS1"])
    assert gene.primary_name == "TP53"
    assert gene.organism_id == organism
    assert gene.synonyms == ["P53", "LFS1"]
    assert gene.workspace_id == GLOBAL_WORKSPACE_ID
    assert gene.version == 1
    events = gene.collect_events()
    assert len(events) == 1 and isinstance(events[0], GeneCreated)


def test_create_requires_primary_name() -> None:
    with pytest.raises(ValidationError):
        Gene.create(primary_name="   ", organism_id=uuid.uuid4())


def test_update_gene_fields() -> None:
    gene = Gene.create(primary_name="TP53", organism_id=uuid.uuid4())
    gene.update(ncbi_gene_id="7157", ensembl_gene_id="ENSG00000141510")
    assert gene.ncbi_gene_id == "7157"
    assert gene.ensembl_gene_id == "ENSG00000141510"
