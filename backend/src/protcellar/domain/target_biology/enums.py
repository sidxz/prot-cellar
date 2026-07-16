"""Target-biology controlled vocabularies."""

from __future__ import annotations

from enum import StrEnum


class EssentialityClass(StrEnum):
    ESSENTIAL = "essential"
    GROWTH_DEFECT = "growth_defect"
    NON_ESSENTIAL = "non_essential"
    GROWTH_ADVANTAGE = "growth_advantage"
    UNCERTAIN = "uncertain"
