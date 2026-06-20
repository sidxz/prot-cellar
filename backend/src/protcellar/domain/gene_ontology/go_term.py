"""Gene Ontology domain records (lightweight reference data — not UoW aggregates)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GoTerm:
    """A single GO term."""

    go_id: str
    name: str
    namespace: str  # biological_process | molecular_function | cellular_component
    definition: str | None = None
    is_obsolete: bool = False
    replaced_by: str | None = None


@dataclass(frozen=True, kw_only=True)
class GoEdge:
    """A directed relation in the GO DAG: `child` is_a / part_of `parent`."""

    child_go_id: str
    parent_go_id: str
    relation: str  # is_a | part_of
