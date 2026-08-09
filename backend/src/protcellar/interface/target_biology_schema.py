"""The published, self-describing write contract for target-biology records.

Derived from the ``*WriteBody`` models that the routes already validate against, so
the contract cannot drift from what the API accepts. The annotation table below
supplies only what a Pydantic model cannot know on its own: a human label, numeric
bounds, and which free-text fields carry a vocabulary worth suggesting.

Any client can build a correct form from this. Restating a field list anywhere else —
in this service or in a client — is what this endpoint exists to prevent.
"""

from __future__ import annotations

import datetime
import enum
import types
import typing
import uuid
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from protcellar.application.target_biology.crud import RecordKind
from protcellar.interface.routes.target_biology import (
    CrispriStrainWriteBody,
    EssentialityWriteBody,
    HypomorphWriteBody,
    ProteinActivityAssayWriteBody,
    ProteinProductionWriteBody,
    ProvenanceBody,
    ResistanceMutationWriteBody,
    UnpublishedStructureWriteBody,
    VulnerabilityWriteBody,
)

# The write body and parent resource for each kind. `attaches_to` tells a client which
# path a record is created under, so it does not have to hard-code the split.
_KINDS: dict[RecordKind, tuple[type[BaseModel], str, str]] = {
    RecordKind.ESSENTIALITY: (EssentialityWriteBody, "gene", "Essentiality"),
    RecordKind.VULNERABILITY: (VulnerabilityWriteBody, "gene", "Vulnerability"),
    RecordKind.HYPOMORPH: (HypomorphWriteBody, "gene", "Hypomorph"),
    RecordKind.CRISPRI_STRAIN: (CrispriStrainWriteBody, "gene", "CRISPRi strain"),
    RecordKind.RESISTANCE_MUTATION: (
        ResistanceMutationWriteBody,
        "gene",
        "Resistance mutation",
    ),
    RecordKind.PROTEIN_PRODUCTION: (
        ProteinProductionWriteBody,
        "protein",
        "Protein production",
    ),
    RecordKind.PROTEIN_ACTIVITY_ASSAY: (
        ProteinActivityAssayWriteBody,
        "protein",
        "Protein activity assay",
    ),
    RecordKind.UNPUBLISHED_STRUCTURE: (
        UnpublishedStructureWriteBody,
        "protein",
        "Unpublished structure",
    ),
}

# Nothing is read-only at the top level anymore: `extensions` was withheld until the
# declared-field registry existed to validate it against; the next task makes it a
# normal writable field.
_READ_ONLY: tuple[str, ...] = ()

# What the models cannot express. Keys are field names; values merge into the descriptor.
# `suggested_values` is filled in at request time from the stored data.
_ANNOTATIONS: dict[str, dict[str, Any]] = {
    "classification": {"label": "Classification"},
    "condition": {"label": "Condition", "vocabulary": True},
    "method": {"label": "Method", "vocabulary": True},
    "confidence": {"label": "Confidence", "min": 0.0, "max": 1.0},
    "vulnerability_score": {"label": "Vulnerability score"},
    "growth_defect": {"label": "Growth defect"},
    "growth_defect_severity": {"label": "Growth-defect severity", "vocabulary": True},
    "knockdown_strain_id": {"label": "Knockdown strain", "target": "strain"},
    "name": {"label": "Name"},
    "mutation": {"label": "Mutation"},
    "compound": {"label": "Compound", "target": "compound"},
    "mic_shift": {"label": "MIC fold-shift"},
    "parent_strain": {"label": "Parent strain"},
    "protein_coordinate": {"label": "Protein coordinate"},
    "status": {"label": "Status", "vocabulary": True},
    "expression_host": {"label": "Expression host", "vocabulary": True},
    "purity": {"label": "Purity"},
    "activity_measured": {"label": "Activity measured", "vocabulary": True},
    "readout": {"label": "Readout", "vocabulary": True},
    "throughput": {"label": "Throughput", "vocabulary": True},
    "resolution": {"label": "Resolution (Å)"},
    "is_published": {"label": "Published"},
    "is_experimental": {"label": "Experimental"},
    "ligands": {"label": "Ligands", "target": "compound"},
    "source_type": {"label": "Source type"},
    "citations": {"label": "Citations"},
    "contributor_researcher": {"label": "Contributor"},
    "observed_on": {"label": "Observed on"},
    "note": {"label": "Note"},
    "pmid": {"label": "PMID"},
    "doi": {"label": "DOI"},
    "url": {"label": "URL"},
    "label": {"label": "Label"},
}

# Field names whose value is a reference to something this service does not resolve.
_REFERENCE_FIELDS = frozenset({"compound", "ligands", "knockdown_strain_id"})


def describe_write_surface(
    suggested: dict[tuple[str, str], list[str]],
    declared: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Build the descriptor. ``suggested`` is keyed by ``(kind, field)``; ``declared`` is
    keyed by kind value and holds that workspace's admin-defined extension fields.
    """
    return {
        "provenance": {"fields": _describe_model(ProvenanceBody, kind=None, suggested={})},
        # PATCH bodies aren't modeled above (every field on them is optional), but all
        # eight carry this same optimistic-concurrency field — name it once here so a
        # client can discover it instead of hardcoding "version".
        "concurrency": {"field": "version"},
        "kinds": {
            kind.value: {
                "label": label,
                "attaches_to": parent,
                "fields": _describe_model(body, kind=kind.value, suggested=suggested),
                "read_only": list(_READ_ONLY),
                "extension_fields": [
                    _describe_declared(d)
                    # Sort here, once, rather than trust the caller's order: two
                    # declarations sharing a position must still come out the same
                    # way every time, not in whatever order they happened to arrive.
                    for d in sorted(
                        declared.get(kind.value, []), key=lambda d: (d["position"], d["name"])
                    )
                ],
            }
            for kind, (body, parent, label) in _KINDS.items()
        },
    }


def _describe_declared(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": d["name"],
        "label": d["label"],
        "type": d["type"],
        "required": False,  # spec: `required` is deliberately out of scope
        "show_in_table": bool(d["show_in_table"]),
    }
    if d.get("options"):
        out["options"] = list(d["options"])
    return out


def _describe_model(
    model: type[BaseModel],
    *,
    kind: str | None,
    suggested: dict[tuple[str, str], list[str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, field in model.model_fields.items():
        # Provenance is described once at the top level, not repeated inside every kind.
        if name == "provenance":
            continue
        out.append(_describe_field(name, field, kind=kind, suggested=suggested))
    return out


def _describe_field(
    name: str,
    field: FieldInfo,
    *,
    kind: str | None,
    suggested: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    annotation = _ANNOTATIONS.get(name, {})
    inner, is_list = _unwrap(field.annotation)
    descriptor: dict[str, Any] = {
        "name": name,
        "label": annotation.get("label", name.replace("_", " ").capitalize()),
        "type": "list" if is_list else _scalar_type(name, inner),
        "required": field.is_required(),
    }
    if is_list:
        if name in _REFERENCE_FIELDS:
            descriptor["item_type"] = "reference"
        elif isinstance(inner, type) and issubclass(inner, BaseModel):
            descriptor["item_type"] = "object"
            descriptor["item_fields"] = _describe_model(inner, kind=kind, suggested={})
        else:
            descriptor["item_type"] = _scalar_type(name, inner)
    if isinstance(inner, type) and issubclass(inner, enum.Enum):
        descriptor["options"] = [member.value for member in inner]
    if "target" in annotation:
        descriptor["target"] = annotation["target"]
    for bound in ("min", "max"):
        if bound in annotation:
            descriptor[bound] = annotation[bound]
    if annotation.get("vocabulary") and kind is not None:
        descriptor["suggested_values"] = suggested.get((kind, name), [])
    return descriptor


def _unwrap(annotation: Any) -> tuple[Any, bool]:
    """Strip Optional and detect a list, returning (inner type, is_list)."""
    args = [a for a in typing.get_args(annotation) if a is not type(None)]
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType) and args:
        annotation = args[0]
        origin = typing.get_origin(annotation)
        args = list(typing.get_args(annotation))
    if origin is list:
        return (args[0] if args else str), True
    return annotation, False


def _scalar_type(name: str, annotation: Any) -> str:
    if name in _REFERENCE_FIELDS:
        return "reference"
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum):
            return "enum"
        if issubclass(annotation, bool):
            return "boolean"
        if issubclass(annotation, int):
            return "integer"
        if issubclass(annotation, float):
            return "number"
        if issubclass(annotation, datetime.date):
            return "date"
        if issubclass(annotation, uuid.UUID):
            return "string"
        if issubclass(annotation, BaseModel):
            return "object"
    if name == "note":
        return "text"
    return "string"
