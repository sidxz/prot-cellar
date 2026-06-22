from __future__ import annotations

from dataclasses import dataclass

from protcellar.domain.imports.enums import ImportType
from protcellar.domain.shared.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ImportRunQueued(DomainEvent):
    import_type: ImportType


@dataclass(frozen=True, kw_only=True)
class ImportRunStarted(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class ImportRunSucceeded(DomainEvent):
    pass


@dataclass(frozen=True, kw_only=True)
class ImportRunFailed(DomainEvent):
    error: str
