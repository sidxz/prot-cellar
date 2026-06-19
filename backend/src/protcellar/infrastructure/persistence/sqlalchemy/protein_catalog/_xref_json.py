"""Shared JSON serialisation helpers for CrossReference lists.

Both ``gene_repository`` and ``protein_repository`` persist cross-references as
JSON arrays.  Keeping the helpers in this module prevents duplicated logic and
any repo-to-repo import.
"""

from __future__ import annotations

from protcellar.domain.shared.cross_reference import CrossReference


def xrefs_to_json(xrefs: list[CrossReference]) -> list[dict[str, object]]:
    return [
        {
            "database": x.database,
            "accession": x.accession,
            "properties": x.properties,
            "evidence": x.evidence,
        }
        for x in xrefs
    ]


def xrefs_from_json(data: list[dict[str, object]] | None) -> list[CrossReference]:
    if not data:
        return []
    result: list[CrossReference] = []
    for d in data:
        props = d.get("properties")
        evidence = d.get("evidence")
        result.append(
            CrossReference(
                database=str(d["database"]),
                accession=str(d["accession"]),
                properties=props if isinstance(props, dict) else None,
                evidence=evidence if isinstance(evidence, str) else None,
            )
        )
    return result
