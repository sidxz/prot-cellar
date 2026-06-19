import uuid

import pytest

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.events import ProteinCreated
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.protein_catalog.value_objects import ProteinNames
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.shared.global_workspace import GLOBAL_WORKSPACE_ID


def test_create_protein_derives_length_and_workspace() -> None:
    organism = uuid.uuid4()
    p = Protein.create(
        primary_accession="P0DTC2",
        organism_id=organism,
        sequence="MFVFLVLLPLVSSQ",
        is_reviewed=True,
        protein_names=ProteinNames(recommended="Spike glycoprotein"),
        protein_existence=ProteinExistence.PROTEIN_LEVEL,
    )
    assert p.primary_accession == "P0DTC2"
    assert p.seq_length == len("MFVFLVLLPLVSSQ")
    assert p.workspace_id == GLOBAL_WORKSPACE_ID
    assert p.version == 1
    events = p.collect_events()
    assert len(events) == 1 and isinstance(events[0], ProteinCreated)


def test_create_rejects_invalid_accession() -> None:
    with pytest.raises(ValidationError):
        Protein.create(
            primary_accession="NOT-AN-ACCESSION",
            organism_id=uuid.uuid4(),
            sequence="MKT",
            is_reviewed=False,
        )


def test_create_rejects_empty_sequence() -> None:
    with pytest.raises(ValidationError):
        Protein.create(
            primary_accession="P12345",
            organism_id=uuid.uuid4(),
            sequence="   ",
            is_reviewed=True,
        )


def test_to_fasta_header_and_wrapping() -> None:
    p = Protein.create(
        primary_accession="P12345",
        organism_id=uuid.uuid4(),
        sequence="M" * 130,
        is_reviewed=True,
        entry_name="TEST_HUMAN",
        protein_names=ProteinNames(recommended="Test protein"),
        sequence_version=2,
        protein_existence=ProteinExistence.PROTEIN_LEVEL,
    )
    fasta = p.to_fasta()
    lines = fasta.splitlines()
    assert lines[0].startswith(">sp|P12345|TEST_HUMAN Test protein")
    assert "PE=1" in lines[0] and "SV=2" in lines[0]
    # sequence wrapped at 60 chars
    assert len(lines[1]) == 60
    assert "".join(lines[1:]) == "M" * 130


def test_unreviewed_protein_uses_tr_prefix() -> None:
    p = Protein.create(
        primary_accession="A0A0A0",
        organism_id=uuid.uuid4(),
        sequence="MKT",
        is_reviewed=False,
    )
    assert p.to_fasta().startswith(">tr|A0A0A0|")
