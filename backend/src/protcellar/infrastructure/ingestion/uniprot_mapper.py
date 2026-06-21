"""Map a UniProtKB JSON entry to a ``ProteinImportRecord``.

This is the anti-corruption layer between UniProt's REST/JSON shape and the
application's bulk-import command. It is a pure function (no I/O) so it can be
unit-tested against fixture entries without touching the network.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from protcellar.application.protein_catalog.bulk_upsert_genes import GeneImportRecord
from protcellar.application.protein_catalog.bulk_upsert_proteins import ProteinImportRecord
from protcellar.domain.protein_catalog.enums import ProteinExistence
from protcellar.domain.protein_catalog.value_objects import (
    ProteinCitation,
    ProteinComment,
    ProteinFeature,
    ProteinIsoform,
    ProteinKeyword,
    ProteinNames,
)
from protcellar.domain.shared.cross_reference import CrossReference


def map_uniprot_entry(
    entry: dict[str, Any],
    *,
    organism_id: uuid.UUID,
    source: str = "uniprot",
    source_release: str = "",
) -> ProteinImportRecord:
    """Translate one UniProtKB JSON entry into a ``ProteinImportRecord``.

    ``organism_id`` is resolved by the caller (the runner) from the entry's
    ``organism.taxonId`` before mapping, so the mapper stays pure.
    """
    seq = entry.get("sequence") or {}
    audit = entry.get("entryAudit") or {}
    isoforms, comments = _comments_and_isoforms(entry)

    return ProteinImportRecord(
        primary_accession=entry["primaryAccession"],
        organism_id=organism_id,
        sequence=seq.get("value", ""),
        is_reviewed=str(entry.get("entryType", "")).startswith("UniProtKB reviewed"),
        source=source,
        source_release=source_release,
        source_record_id=entry["primaryAccession"],
        source_record_checksum=_checksum(audit),
        secondary_accessions=tuple(entry.get("secondaryAccessions") or []),
        entry_name=entry.get("uniProtkbId"),
        protein_names=_names(entry.get("proteinDescription") or {}),
        seq_mass=seq.get("molWeight"),
        seq_crc64=seq.get("crc64"),
        protein_existence=_existence(entry.get("proteinExistence")),
        keywords=tuple(k.get("name") for k in entry.get("keywords") or [] if k.get("name")),
        entry_version=audit.get("entryVersion"),
        sequence_version=audit.get("sequenceVersion"),
        annotation_score=_int_or_none(entry.get("annotationScore")),
        fragment=_fragment(entry.get("proteinDescription") or {}),
        uniparc_id=(entry.get("extraAttributes") or {}).get("uniParcId"),
        cross_references=_cross_references(entry.get("uniProtKBCrossReferences") or []),
        features=tuple(_feature(f) for f in entry.get("features") or []),
        comments=tuple(comments),
        isoforms=tuple(isoforms),
        keyword_refs=_keyword_refs(entry.get("keywords") or []),
        citations=_citations(entry.get("references") or []),
    )


def _checksum(audit: dict[str, Any]) -> str:
    """Stable per-entry checksum for idempotent re-sync (changes on any update)."""
    return f"e{audit.get('entryVersion')}s{audit.get('sequenceVersion')}"


def _int_or_none(value: Any) -> int | None:
    return int(value) if value is not None else None


def _existence(value: Any) -> ProteinExistence | None:
    if not value:
        return None
    try:
        return ProteinExistence.from_level(int(str(value).split(":")[0].strip()))
    except (ValueError, KeyError):
        return None


def _names(desc: dict[str, Any]) -> ProteinNames:
    rec = desc.get("recommendedName") or {}
    recommended = (rec.get("fullName") or {}).get("value")
    short_names = list(_values(rec.get("shortNames")))
    ec_numbers = list(_values(rec.get("ecNumbers")))
    alternative: list[str] = []
    for alt in desc.get("alternativeNames") or []:
        full = (alt.get("fullName") or {}).get("value")
        if full:
            alternative.append(full)
        short_names.extend(_values(alt.get("shortNames")))
        ec_numbers.extend(_values(alt.get("ecNumbers")))
    submitted: list[str] = []
    for sub in desc.get("submissionNames") or []:
        full = (sub.get("fullName") or {}).get("value")
        if full:
            submitted.append(full)
    return ProteinNames(
        recommended=recommended,
        alternative=tuple(alternative),
        submitted=tuple(submitted),
        short_names=tuple(short_names),
        ec_numbers=tuple(ec_numbers),
    )


def _values(items: Any) -> tuple[str, ...]:
    return tuple(i.get("value") for i in items or [] if i.get("value"))


def _fragment(desc: dict[str, Any]) -> str | None:
    flag = desc.get("flag")
    if isinstance(flag, str) and "ragment" in flag:
        return flag
    return None


def _feature(f: dict[str, Any]) -> ProteinFeature:
    loc = f.get("location") or {}
    start = loc.get("start") or {}
    end = loc.get("end") or {}
    return ProteinFeature(
        feature_type=f.get("type", ""),
        start=start.get("value"),
        end=end.get("value"),
        start_modifier=start.get("modifier"),
        end_modifier=end.get("modifier"),
        description=f.get("description"),
        feature_id=f.get("featureId"),
        ligand=f.get("ligand"),
        alternative_sequence=_alt_sequence(f.get("alternativeSequence")),
        evidence=f.get("evidences"),
    )


def _alt_sequence(alt: Any) -> str | None:
    if not isinstance(alt, dict):
        return None
    originals = alt.get("originalSequence")
    variations = alt.get("alternativeSequences") or []
    if originals or variations:
        return f"{originals or ''}->{','.join(variations)}"
    return None


def _comments_and_isoforms(
    entry: dict[str, Any],
) -> tuple[list[ProteinIsoform], list[ProteinComment]]:
    isoforms: list[ProteinIsoform] = []
    comments: list[ProteinComment] = []
    for c in entry.get("comments") or []:
        ctype = c.get("commentType", "")
        if ctype == "ALTERNATIVE PRODUCTS":
            event = ", ".join(c.get("events") or []) or None
            for iso in c.get("isoforms") or []:
                ids = iso.get("isoformIds") or []
                isoforms.append(
                    ProteinIsoform(
                        isoform_accession=ids[0] if ids else "",
                        name=(iso.get("name") or {}).get("value"),
                        is_displayed=iso.get("isoformSequenceStatus") == "Displayed",
                        event=event,
                    )
                )
            continue
        texts = c.get("texts") or []
        payload = {k: v for k, v in c.items() if k not in ("commentType", "texts")} or None
        comments.append(
            ProteinComment(
                comment_type=ctype,
                text=texts[0].get("value") if texts else None,
                payload=payload,
                evidence=texts[0].get("evidences") if texts else None,
            )
        )
    return isoforms, comments


def _keyword_refs(keywords: list[dict[str, Any]]) -> tuple[ProteinKeyword, ...]:
    return tuple(
        ProteinKeyword(kw_id=k["id"], name=k.get("name"), category=k.get("category"))
        for k in keywords
        if k.get("id")
    )


def _citations(references: list[dict[str, Any]]) -> tuple[ProteinCitation, ...]:
    out: list[ProteinCitation] = []
    for ref in references:
        cit = ref.get("citation") or {}
        xrefs = cit.get("citationCrossReferences") or []
        out.append(
            ProteinCitation(
                citation_type=cit.get("citationType"),
                title=cit.get("title"),
                journal=cit.get("journal"),
                authors=cit.get("authors"),
                publication_date=cit.get("publicationDate"),
                pubmed_id=_xref_id(xrefs, "PubMed"),
                doi=_xref_id(xrefs, "DOI"),
                reference_number=ref.get("referenceNumber"),
                positions=ref.get("referencePositions"),
                reference_comments=ref.get("referenceComments"),
            )
        )
    return tuple(out)


def _xref_id(xrefs: list[dict[str, Any]], database: str) -> str | None:
    return next((x.get("id") for x in xrefs if x.get("database") == database), None)


def _cross_references(xrefs: list[dict[str, Any]]) -> tuple[CrossReference, ...]:
    out: list[CrossReference] = []
    for x in xrefs:
        props = {p["key"]: p.get("value") for p in x.get("properties") or [] if p.get("key")}
        out.append(
            CrossReference(
                database=x.get("database", ""),
                accession=x.get("id", ""),
                properties=props or None,
                evidence=None,
            )
        )
    return tuple(out)


def map_uniprot_genes(
    entry: dict[str, Any],
    *,
    organism_id: uuid.UUID,
    tax_id: int | str,
    source: str = "uniprot",
    source_release: str = "",
) -> list[GeneImportRecord]:
    """Extract one GeneImportRecord per usable gene block on a UniProtKB entry."""
    out: list[GeneImportRecord] = []
    for gene in entry.get("genes") or []:
        primary = _gene_primary_name(gene)
        basis = _gene_key_basis(gene)
        if primary is None or basis is None:
            continue
        ncbi = _ncbi_gene_id(entry)
        synonyms = _gene_synonyms(gene, primary)
        out.append(
            GeneImportRecord(
                primary_name=primary,
                organism_id=organism_id,
                source=source,
                source_release=source_release,
                source_record_id=f"{tax_id}:{basis}",
                source_record_checksum=_gene_checksum(primary, synonyms, ncbi),
                synonyms=synonyms,
                ncbi_gene_id=ncbi,
            )
        )
    return out


def gene_key_for_entry(entry: dict[str, Any], *, tax_id: int | str) -> str | None:
    """source_record_id of the entry's primary (first) gene — used to link the protein."""
    genes = entry.get("genes") or []
    if not genes:
        return None
    basis = _gene_key_basis(genes[0])
    return f"{tax_id}:{basis}" if basis else None


def _gene_primary_name(gene: dict[str, Any]) -> str | None:
    """Human-friendly name: geneName, else first ordered-locus name, else first ORF name."""
    name: str | None = (gene.get("geneName") or {}).get("value")
    if name:
        return name
    for key in ("orderedLocusNames", "orfNames"):
        vals = _values(gene.get(key))
        if vals:
            return vals[0]
    return None


def _gene_key_basis(gene: dict[str, Any]) -> str | None:
    """Stable identity: prefer the immutable ordered-locus name (locus tag)."""
    oln = _values(gene.get("orderedLocusNames"))
    if oln:
        return oln[0]
    name: str | None = (gene.get("geneName") or {}).get("value")
    if name:
        return name
    orf = _values(gene.get("orfNames"))
    return orf[0] if orf else None


def _gene_synonyms(gene: dict[str, Any], primary_name: str) -> tuple[str, ...]:
    pool: list[str] = []
    name = (gene.get("geneName") or {}).get("value")
    if name:
        pool.append(name)
    pool.extend(_values(gene.get("synonyms")))
    pool.extend(_values(gene.get("orderedLocusNames")))
    pool.extend(_values(gene.get("orfNames")))
    seen: set[str] = set()
    result: list[str] = []
    for n in pool:
        if n and n != primary_name and n not in seen:
            seen.add(n)
            result.append(n)
    return tuple(result)


def _ncbi_gene_id(entry: dict[str, Any]) -> str | None:
    """The NCBI GeneID xref id, but only when exactly one is present (avoid mis-attribution)."""
    ids = [
        x.get("id")
        for x in entry.get("uniProtKBCrossReferences") or []
        if x.get("database") == "GeneID" and x.get("id")
    ]
    return ids[0] if len(ids) == 1 else None


def _gene_checksum(primary_name: str, synonyms: tuple[str, ...], ncbi_gene_id: str | None) -> str:
    basis = "|".join([primary_name, ",".join(sorted(synonyms)), ncbi_gene_id or ""])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
