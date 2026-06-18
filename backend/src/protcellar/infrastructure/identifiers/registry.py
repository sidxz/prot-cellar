"""Embedded Bioregistry-style identifier registry: validation + URL resolution."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _Prefix:
    pattern: re.Pattern[str]
    uri_template: str  # {acc} substitution


_DEFAULT_PREFIXES: dict[str, tuple[str, str]] = {
    # prefix: (regex, uri_template using {curie})
    "uniprot": (
        r"^([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2})$",
        "https://identifiers.org/uniprot:{acc}",
    ),
    "ncbitaxon": (r"^\d+$", "https://identifiers.org/taxonomy:{acc}"),
    "ncbigene": (r"^\d+$", "https://identifiers.org/ncbigene:{acc}"),
    "refseq": (
        r"^(((AC|AP|NC|NG|NM|NP|NR|NT|NW|WP|XM|XP|XR|YP|ZP)_\d+)|(NZ_[A-Z]{2,4}\d+))(\.\d+)?$",
        "https://identifiers.org/refseq:{acc}",
    ),
    "ensembl": (r"^ENS[FPTG]\d{11}(\.\d+)?$", "https://identifiers.org/ensembl:{acc}"),
    "pdb": (r"^([0-9][A-Za-z0-9]{3}|pdb_[a-z0-9]{8})$", "https://identifiers.org/pdb:{acc}"),
    "interpro": (r"^IPR\d{6}$", "https://identifiers.org/interpro:{acc}"),
    "pfam": (r"^PF\d{5}$", "https://identifiers.org/pfam:{acc}"),
    "go": (r"^GO:\d{7}$", "https://identifiers.org/go:{acc}"),
    "ec": (r"^\d+\.(\d+|-)\.(\d+|-)\.(n?\d+|-)$", "https://identifiers.org/ec-code:{acc}"),
    "chembl.target": (r"^CHEMBL\d+$", "https://identifiers.org/chembl.target:{acc}"),
    "proteome": (r"^UP\d{9}$", "https://www.uniprot.org/proteomes/{acc}"),
}


class IdentifierRegistry:
    def __init__(self, prefixes: dict[str, _Prefix]) -> None:
        self._prefixes = prefixes

    @classmethod
    def default(cls) -> IdentifierRegistry:
        return cls(
            {
                prefix: _Prefix(re.compile(rx), uri)
                for prefix, (rx, uri) in _DEFAULT_PREFIXES.items()
            }
        )

    def validate(self, prefix: str, accession: str) -> bool:
        entry = self._prefixes.get(prefix)
        return bool(entry and entry.pattern.match(accession))

    def resolve_url(self, prefix: str, accession: str) -> str | None:
        entry = self._prefixes.get(prefix)
        if entry is None or not entry.pattern.match(accession):
            return None
        return entry.uri_template.format(acc=accession)
