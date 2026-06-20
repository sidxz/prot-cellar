"""Unit tests for the obonet-based GO OBO parser (no network / DB)."""

from __future__ import annotations

import io

from protcellar.infrastructure.ingestion.go_obo import parse_obo, read_obo

_FIXTURE = """format-version: 1.2
data-version: releases/2026-05-19
ontology: go

[Term]
id: GO:0000001
name: term one
namespace: molecular_function
def: "first term." [PMID:1]
is_a: GO:0000002 ! term two

[Term]
id: GO:0000002
name: term two
namespace: molecular_function
relationship: part_of GO:0000004 ! term four

[Term]
id: GO:0000004
name: term four
namespace: cellular_component

[Term]
id: GO:0000003
name: term three
namespace: molecular_function
is_obsolete: true
replaced_by: GO:0000002
"""


def test_parse_obo_terms_edges_version() -> None:
    terms, edges, version = parse_obo(read_obo(io.StringIO(_FIXTURE)))

    assert version == "releases/2026-05-19"

    by_id = {t.go_id: t for t in terms}
    assert set(by_id) == {"GO:0000001", "GO:0000002", "GO:0000003", "GO:0000004"}
    assert by_id["GO:0000001"].namespace == "molecular_function"
    assert by_id["GO:0000001"].is_obsolete is False
    defn = by_id["GO:0000001"].definition
    assert defn is not None and "first term" in defn
    # obsolete terms are kept (so existing annotations still resolve to a name)
    assert by_id["GO:0000003"].is_obsolete is True
    assert by_id["GO:0000003"].replaced_by == "GO:0000002"

    edge_set = {(e.child_go_id, e.parent_go_id, e.relation) for e in edges}
    assert ("GO:0000001", "GO:0000002", "is_a") in edge_set
    assert ("GO:0000002", "GO:0000004", "part_of") in edge_set
