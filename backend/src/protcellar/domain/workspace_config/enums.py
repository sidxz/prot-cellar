"""Workspace configuration enums."""

from enum import StrEnum

__all__ = ["OrganizationType"]


class OrganizationType(StrEnum):
    """Classification of organizations participating in the protein lifecycle."""

    INTERNAL = "internal"
    PHARMA_PARTNER = "pharma_partner"
    CRO = "cro"
    ACADEMIC = "academic"
    VENDOR = "vendor"
    GOVERNMENT = "government"
