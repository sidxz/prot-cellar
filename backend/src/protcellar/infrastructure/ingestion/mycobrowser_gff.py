"""Pure GFF3 parser for the Mycobrowser H37Rv genome annotation.

Yields one :class:`GffGeneRecord` per locus tag, coalescing a locus's ``gene``
and ``CDS`` features so coordinates (typically on the ``gene`` line) and
functional category / product (typically on the ``CDS`` line) end up on one
record. Tolerant of both Mycobrowser's native attribute vocabulary
(``Locus``/``Name``/``Functional_Category``/``Product``) and standard
NCBI/RefSeq keys (``locus_tag``/``gene``/``product``). No I/O — the client
fetches the text and hands it here, so this stays unit-testable on fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from urllib.parse import unquote

# Attribute aliases (case-insensitive), most-specific first.
_LOCUS_KEYS = ("locus", "locus_tag", "gene_id")
_NAME_KEYS = ("name", "gene", "gene_name")
_CATEGORY_KEYS = ("functional_category", "category")
_PRODUCT_KEYS = ("product", "description")


@dataclass(frozen=True, kw_only=True)
class GffGeneRecord:
    """A single gene's location + descriptive attributes from a GFF3 file."""

    locus_tag: str
    seqid: str
    start: int
    end: int
    strand: str
    gene_name: str | None = None
    product: str | None = None
    functional_category: str | None = None


def parse_mycobrowser_gff(text: str) -> list[GffGeneRecord]:
    """Parse GFF3 text into one coalesced :class:`GffGeneRecord` per locus tag."""
    by_locus: dict[str, GffGeneRecord] = {}
    order: list[str] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 9:
            continue
        attrs = _parse_attributes(cols[8])
        locus = _first(attrs, _LOCUS_KEYS)
        if not locus:
            continue
        record = GffGeneRecord(
            locus_tag=locus,
            seqid=cols[0],
            start=int(cols[3]),
            end=int(cols[4]),
            strand=cols[6],
            gene_name=_first(attrs, _NAME_KEYS),
            product=_first(attrs, _PRODUCT_KEYS),
            functional_category=_first(attrs, _CATEGORY_KEYS),
        )
        if locus in by_locus:
            by_locus[locus] = _coalesce(by_locus[locus], record)
        else:
            by_locus[locus] = record
            order.append(locus)
    return [by_locus[locus] for locus in order]


def _parse_attributes(field: str) -> dict[str, str]:
    """``key=value;key=value`` → lower-cased-key dict, URL-decoded values."""
    out: dict[str, str] = {}
    for pair in field.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        out[key.strip().lower()] = unquote(value.strip())
    return out


def _first(attrs: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = attrs.get(key)
        if value:
            return value
    return None


def _coalesce(base: GffGeneRecord, other: GffGeneRecord) -> GffGeneRecord:
    """Merge two features of the same locus, filling gaps; keep ``gene``-line coords.

    A later ``gene`` feature overwrites coordinates (it owns the gene span); the
    first non-null descriptive value wins for name/product/functional_category.
    """
    return replace(
        base,
        gene_name=base.gene_name or other.gene_name,
        product=base.product or other.product,
        functional_category=base.functional_category or other.functional_category,
    )
