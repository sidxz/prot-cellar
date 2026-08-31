"""Default a Target's pref_name from its component proteins.

Curators name targets by the short gene-derived form (``PptT``, ``Pks13``,
``GyrA``) rather than the UniProt recommended name, so that is what we derive.
An explicit pref_name always wins; this only fills the blank.
"""

from __future__ import annotations

from protcellar.domain.protein_catalog.gene import Gene
from protcellar.domain.protein_catalog.protein import Protein
from protcellar.domain.shared.errors import ValidationError
from protcellar.domain.target.enums import TargetType


def protein_case(name: str) -> str:
    """Bacterial protein-name casing: the gene symbol ``pptT`` names the protein ``PptT``.

    Only the initial is touched. The internal capitals carry meaning (``mmpL3`` -> ``MmpL3``,
    ``glfT2`` -> ``GlfT2``), so a blanket ``.title()`` or ``.capitalize()`` would destroy them.

    Exported because the curated importers need the same rule: they pass an explicit
    pref_name, which by design skips ``default_pref_name`` entirely, and a hand-written
    source that misses the convention is exactly how the catalog acquired 14 gene-cased
    target names (``rho``, ``dnaA``) sitting beside 112 correct ones.
    """
    return name[:1].upper() + name[1:]


def component_label(protein: Protein, gene: Gene | None) -> str:
    """Short display name for one component: ``pptT`` -> ``PptT``."""
    if gene is not None and gene.primary_name:
        return protein_case(gene.primary_name)
    return protein.protein_names.recommended or protein.primary_accession


def default_pref_name(target_type: TargetType, labels: list[str]) -> str:
    if not labels:
        raise ValidationError(
            f"pref_name is required for a {target_type.value} target with no resolvable components"
        )
    if target_type is TargetType.DOMAIN:
        return f"{labels[0]} domain"
    if target_type is TargetType.SINGLE_PROTEIN:
        return labels[0]
    return "/".join(labels)
