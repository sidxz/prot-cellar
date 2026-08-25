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


def component_label(protein: Protein, gene: Gene | None) -> str:
    """Short display name for one component: ``pptT`` -> ``PptT``."""
    if gene is not None and gene.primary_name:
        name = gene.primary_name
        return name[:1].upper() + name[1:]
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
