"""Unit tests for the UniProtKB JSON → ProteinImportRecord mapper."""

from __future__ import annotations

import uuid

from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.infrastructure.ingestion.uniprot_mapper import (
    gene_key_for_entry,
    map_uniprot_entry,
    map_uniprot_genes,
)

_ENTRY: dict = {
    "primaryAccession": "P9WIE5",
    "secondaryAccessions": ["P0A5X8", "Q10781"],
    "uniProtkbId": "KATG_MYCTU",
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "annotationScore": 5.0,
    "proteinExistence": "1: Evidence at protein level",
    "extraAttributes": {"uniParcId": "UPI000012706D"},
    "organism": {"scientificName": "Mycobacterium tuberculosis", "taxonId": 83332},
    "proteinDescription": {
        "recommendedName": {
            "fullName": {"value": "Catalase-peroxidase"},
            "shortNames": [{"value": "CP"}],
            "ecNumbers": [{"value": "1.11.1.21"}],
        },
        "alternativeNames": [{"fullName": {"value": "Peroxidase/catalase"}}],
    },
    "genes": [{"geneName": {"value": "katG"}, "orderedLocusNames": [{"value": "Rv1908c"}]}],
    "comments": [
        {"commentType": "FUNCTION", "texts": [{"value": "Bifunctional enzyme."}]},
        {
            "commentType": "CATALYTIC ACTIVITY",
            "reaction": {"name": "2 H2O2 = O2 + 2 H2O", "ecNumber": "1.11.1.21"},
        },
        {
            "commentType": "ALTERNATIVE PRODUCTS",
            "isoforms": [
                {
                    "isoformIds": ["P9WIE5-1"],
                    "name": {"value": "Alpha"},
                    "isoformSequenceStatus": "Displayed",
                },
                {
                    "isoformIds": ["P9WIE5-2"],
                    "name": {"value": "Beta"},
                    "isoformSequenceStatus": "Described",
                },
            ],
        },
    ],
    "features": [
        {
            "type": "Active site",
            "location": {
                "start": {"value": 281, "modifier": "EXACT"},
                "end": {"value": 281, "modifier": "EXACT"},
            },
            "description": "Proton acceptor",
            "featureId": "ACT_SITE_1",
            "evidences": [{"evidenceCode": "ECO:0000255"}],
        }
    ],
    "keywords": [
        {"id": "KW-0560", "category": "Molecular function", "name": "Oxidoreductase"},
        {"id": "KW-1185", "category": "Technical term", "name": "Reference proteome"},
    ],
    "references": [
        {
            "referenceNumber": 1,
            "citation": {
                "citationType": "journal article",
                "title": "Deciphering the biology of M. tuberculosis.",
                "journal": "Nature",
                "authors": ["Cole S.T.", "Brosch R."],
                "publicationDate": "1998",
                "citationCrossReferences": [
                    {"database": "PubMed", "id": "9634230"},
                    {"database": "DOI", "id": "10.1038/31159"},
                ],
            },
            "referencePositions": ["NUCLEOTIDE SEQUENCE"],
        }
    ],
    "uniProtKBCrossReferences": [
        {
            "database": "PDB",
            "id": "1SJ2",
            "properties": [
                {"key": "Method", "value": "X-ray"},
                {"key": "Resolution", "value": "2.40 A"},
            ],
        },
        {
            "database": "GO",
            "id": "GO:0004096",
            "properties": [{"key": "GoTerm", "value": "F:catalase activity"}],
        },
    ],
    "sequence": {
        "value": "MPEQHPPITETTTGAASNGCPV",
        "length": 22,
        "molWeight": 80605,
        "crc64": "B43C033B533CDD89",
    },
    "entryAudit": {"sequenceVersion": 1, "entryVersion": 47},
}


def _rec(organism_id: uuid.UUID | None = None):
    return map_uniprot_entry(
        _ENTRY,
        organism_id=organism_id or uuid.uuid4(),
        source="uniprot",
        source_release="2026_02",
    )


def test_maps_identity_and_provenance() -> None:
    org = uuid.uuid4()
    rec = _rec(org)
    assert rec.primary_accession == "P9WIE5"
    assert rec.secondary_accessions == ("P0A5X8", "Q10781")
    assert rec.entry_name == "KATG_MYCTU"
    assert rec.is_reviewed is True
    assert rec.organism_id == org
    assert rec.source == "uniprot"
    assert rec.source_record_id == "P9WIE5"
    assert rec.source_record_checksum  # non-empty, derived from versions


def test_maps_sequence_and_scalars() -> None:
    rec = _rec()
    assert rec.sequence == "MPEQHPPITETTTGAASNGCPV"
    assert rec.seq_mass == 80605
    assert rec.seq_crc64 == "B43C033B533CDD89"
    assert rec.sequence_version == 1
    assert rec.entry_version == 47
    assert rec.annotation_score == 5
    assert rec.uniparc_id == "UPI000012706D"
    assert rec.protein_existence is ProteinExistence.PROTEIN_LEVEL


def test_maps_names_with_short_and_ec() -> None:
    rec = _rec()
    assert rec.protein_names is not None
    assert rec.protein_names.recommended == "Catalase-peroxidase"
    assert rec.protein_names.short_names == ("CP",)
    assert rec.protein_names.ec_numbers == ("1.11.1.21",)
    assert rec.protein_names.alternative == ("Peroxidase/catalase",)


def test_maps_features() -> None:
    rec = _rec()
    assert len(rec.features) == 1
    f = rec.features[0]
    assert f.feature_type == "Active site"
    assert f.start == 281
    assert f.end == 281
    assert f.feature_id == "ACT_SITE_1"
    assert f.evidence == [{"evidenceCode": "ECO:0000255"}]


def test_maps_comments_text_and_structured_payload() -> None:
    rec = _rec()
    types = {c.comment_type for c in rec.comments}
    assert {"FUNCTION", "CATALYTIC ACTIVITY"} <= types
    func = next(c for c in rec.comments if c.comment_type == "FUNCTION")
    assert func.text == "Bifunctional enzyme."
    cat = next(c for c in rec.comments if c.comment_type == "CATALYTIC ACTIVITY")
    assert cat.payload is not None and cat.payload["reaction"]["ecNumber"] == "1.11.1.21"


def test_maps_isoforms_from_alternative_products() -> None:
    rec = _rec()
    accs = {i.isoform_accession for i in rec.isoforms}
    assert accs == {"P9WIE5-1", "P9WIE5-2"}
    displayed = next(i for i in rec.isoforms if i.is_displayed)
    assert displayed.isoform_accession == "P9WIE5-1"


def test_maps_keywords_citations_xrefs() -> None:
    rec = _rec()
    assert {k.kw_id for k in rec.keyword_refs} == {"KW-0560", "KW-1185"}
    assert ("Oxidoreductase" in rec.keywords) and ("Reference proteome" in rec.keywords)
    assert len(rec.citations) == 1
    assert rec.citations[0].pubmed_id == "9634230"
    assert rec.citations[0].doi == "10.1038/31159"
    dbs = {x.database for x in rec.cross_references}
    assert {"PDB", "GO"} <= dbs
    pdb = next(x for x in rec.cross_references if x.database == "PDB")
    assert pdb.accession == "1SJ2"
    assert pdb.properties is not None and pdb.properties.get("Method") == "X-ray"


def test_extracts_gene_with_name_and_locus() -> None:
    org = uuid.uuid4()
    genes = map_uniprot_genes(
        _ENTRY, organism_id=org, tax_id=83332, source="uniprot", source_release="2026_02"
    )
    assert len(genes) == 1
    g = genes[0]
    assert g.primary_name == "katG"
    assert g.source_record_id == "83332:Rv1908c"  # locus tag is the stable key
    assert "Rv1908c" in g.synonyms
    assert g.organism_id == org
    assert g.source == "uniprot"
    assert g.source_record_checksum  # non-empty content hash


def test_gene_key_for_entry_matches_record() -> None:
    assert gene_key_for_entry(_ENTRY, tax_id=83332) == "83332:Rv1908c"


def test_locus_only_entry_uses_locus_as_primary_name() -> None:
    entry = {"genes": [{"orderedLocusNames": [{"value": "Rv0001"}]}]}
    genes = map_uniprot_genes(entry, organism_id=uuid.uuid4(), tax_id=83332)
    assert genes[0].primary_name == "Rv0001"
    assert genes[0].source_record_id == "83332:Rv0001"
    assert genes[0].synonyms == ()


def test_entry_without_genes_yields_nothing() -> None:
    assert (
        map_uniprot_genes({"primaryAccession": "X"}, organism_id=uuid.uuid4(), tax_id=83332) == []
    )
    assert gene_key_for_entry({"primaryAccession": "X"}, tax_id=83332) is None


def test_ncbi_gene_id_from_single_geneid_xref() -> None:
    entry = {
        "genes": [{"geneName": {"value": "katG"}}],
        "uniProtKBCrossReferences": [{"database": "GeneID", "id": "888090"}],
    }
    g = map_uniprot_genes(entry, organism_id=uuid.uuid4(), tax_id=83332)[0]
    assert g.ncbi_gene_id == "888090"
    assert g.source_record_id == "83332:katG"  # no locus tag -> geneName is the key
