"""Unit tests for the pure DeJesus 2017 essentiality-table parser (no I/O)."""

from __future__ import annotations

from protcellar.infrastructure.ingestion.dejesus_essentiality import (
    parse_dejesus_essentiality,
)

# DeJesus 2017 (mBio, PMID:28096490) style table: ORF / Name / Final Call,
# tab-separated, with the four-letter HMM calls (ES/GD/NE/GA) plus ESD and U.
_TSV = """ORF	Name	Final Call
Rv0667	rpoB	ES
Rv0668	rpoC	GD
Rv0669	-	NE
Rv0670	-	GA
Rv0671	-	ESD
Rv0672	-	U
"""

_CSV = """ORF,Name,Final Call
Rv0667,rpoB,ES
Rv0668,rpoC,GD
"""


def test_normalizes_four_hmm_calls() -> None:
    calls = parse_dejesus_essentiality(_TSV)
    assert calls["Rv0667"] == "essential"
    assert calls["Rv0668"] == "growth-defect"
    assert calls["Rv0669"] == "non-essential"
    assert calls["Rv0670"] == "growth-advantage"


def test_esd_maps_to_essential_and_unknown_maps_to_uncertain() -> None:
    calls = parse_dejesus_essentiality(_TSV)
    assert calls["Rv0671"] == "essential"  # ESD = essential domain
    assert calls["Rv0672"] == "uncertain"  # U / anything unrecognized


def test_parses_csv_as_well_as_tsv() -> None:
    calls = parse_dejesus_essentiality(_CSV)
    assert calls == {"Rv0667": "essential", "Rv0668": "growth-defect"}


def test_returns_locus_to_call_mapping() -> None:
    calls = parse_dejesus_essentiality(_TSV)
    assert set(calls) == {
        "Rv0667",
        "Rv0668",
        "Rv0669",
        "Rv0670",
        "Rv0671",
        "Rv0672",
    }


def test_ignores_blank_lines_and_is_call_case_insensitive() -> None:
    text = "ORF\tCall\nRv0667\tes\n\nRv0668\tGd\n"
    calls = parse_dejesus_essentiality(text)
    assert calls == {"Rv0667": "essential", "Rv0668": "growth-defect"}


def test_detects_locus_and_call_columns_by_header_aliases() -> None:
    # Header uses "Rv ID" / "Essentiality" rather than ORF / Final Call.
    text = "Rv ID\tEssentiality\nRv0667\tES\n"
    calls = parse_dejesus_essentiality(text)
    assert calls == {"Rv0667": "essential"}
