"""obonet-based GO OBO parser → GoTerm / GoEdge records.

A thin pure layer over obonet so the runner stays I/O-only and this stays
unit-testable on fixture OBO text. ``read_obo`` sets ``ignore_obsolete=False``
so obsolete terms are retained (existing GO annotations still resolve to a name).
obonet edges are ``(child, parent, relation)`` — already our convention.
"""

from __future__ import annotations

from typing import Any

import obonet

from protcellar.domain.gene_ontology.go_term import GoEdge, GoTerm

_RELATIONS = ("is_a", "part_of")


def read_obo(source: Any) -> Any:
    """Parse an OBO source into a networkx graph, keeping obsolete terms."""
    return obonet.read_obo(source, ignore_obsolete=False)


def parse_obo(graph: Any) -> tuple[list[GoTerm], list[GoEdge], str]:
    terms: list[GoTerm] = []
    for go_id, data in graph.nodes(data=True):
        name = data.get("name")
        namespace = data.get("namespace")
        if name is None or namespace is None:
            continue  # bare placeholder node (undefined edge target); the model needs both
        replaced_by = data.get("replaced_by") or []
        terms.append(
            GoTerm(
                go_id=go_id,
                name=name,
                namespace=namespace,
                definition=data.get("def"),
                is_obsolete=data.get("is_obsolete") == "true",
                replaced_by=replaced_by[0] if replaced_by else None,
            )
        )
    edges: list[GoEdge] = []
    for child, parent, relation in graph.edges(keys=True):
        if relation in _RELATIONS:
            edges.append(GoEdge(child_go_id=child, parent_go_id=parent, relation=relation))
    return terms, edges, graph.graph.get("data-version", "")
