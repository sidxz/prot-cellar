from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from protcellar.domain.shared.provenance import GenerationMethod


class ParamType(StrEnum):
    STRING = "string"
    NUMBER = "number"
    ENUM = "enum"
    ORGANISM = "organism"  # renders the organism combobox on the FE
    FILE_UPLOAD = "file_upload"  # reuses POST /api/v1/imports/uploads -> upload_ref
    # ponytail: the FE uploads every file_upload field through the essentiality
    # endpoint (runs essentiality_upload_to_tsv). Fine while DeJesus is the only
    # file plugin; make the upload endpoint/hook per-record-type before a 2nd
    # file-based plugin, or its file gets normalized as an essentiality table.
    BOOL = "bool"


@dataclass(frozen=True, kw_only=True)
class ParamField:
    """A constrained param descriptor the FE renders without a schema-form library."""

    key: str
    label: str
    type: ParamType
    required: bool = False
    default: object | None = None
    options: tuple[str, ...] = ()  # for ENUM
    help: str | None = None


@dataclass(frozen=True, kw_only=True)
class PluginManifest:
    """Declarative plugin identity — drives the FE catalog + param validation."""

    id: str
    version: str
    name: str
    description: str
    target_records: tuple[str, ...]
    default_generation_method: GenerationMethod
    params: tuple[ParamField, ...] = ()
    requires_secrets: tuple[str, ...] = ()
