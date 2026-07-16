"""Denormalized reference to a chem-cellar molecule (self-contained id, no FK).

Cross-cellar links are daikon-owned; prot-cellar stores a portable compound id
(+ optional display name) that daikon's link map resolves to chem-cellar. Mirrors
chem-cellar's ``TargetRef`` (denormalized id + name, no foreign key).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CompoundRef:
    compound_id: uuid.UUID
    name: str | None = None
