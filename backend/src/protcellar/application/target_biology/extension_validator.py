"""Validates a target-biology record's proposed ``extensions`` bag against the
workspace's declared field definitions, and merges the result onto the
record's existing bag.

The registry (``ExtensionFieldDefRepository``) is the only thing that says what
may live in ``extensions`` — every submitted key must be declared for that
record kind, and its value must match the declared type. The merge against
``existing`` is what keeps an edit to one declared field from wiping out
imported values nobody declared: see ``ExtensionValidator.validate_and_merge``.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from returns.result import Failure, Result, Success

from protcellar.domain.shared.errors import DomainError, ValidationError
from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)
from protcellar.domain.workspace_config.extension_fields.repository import (
    ExtensionFieldDefRepository,
)


def _typecheck(field: ExtensionFieldDef, value: Any) -> Result[Any, DomainError]:
    """Validate ``value`` against ``field``'s declared type.

    Coercion is minimal and deliberate: a whole-number float is accepted for
    ``integer`` (JSON has no distinct int type, so ``5.0`` over the wire is a
    legitimate integer) and normalized to ``int``; a ``date`` value is parsed
    only to *validate* the string, never converted — JSONB cannot hold a
    ``date``/``datetime`` object, so the original string goes back unchanged.
    """
    name = field.name
    match field.field_type:
        case ExtensionFieldType.STRING | ExtensionFieldType.TEXT:
            if not isinstance(value, str):
                return Failure(ValidationError(f"{name!r} must be a string"))
            return Success(value)
        case ExtensionFieldType.BOOLEAN:
            if not isinstance(value, bool):
                return Failure(ValidationError(f"{name!r} must be a boolean"))
            return Success(value)
        case ExtensionFieldType.INTEGER:
            # isinstance(True, int) is True in Python — bool must be rejected explicitly.
            if isinstance(value, bool) or not isinstance(value, int | float):
                return Failure(ValidationError(f"{name!r} must be an integer"))
            if isinstance(value, float) and not value.is_integer():
                return Failure(ValidationError(f"{name!r} must be an integer"))
            return Success(int(value))
        case ExtensionFieldType.NUMBER:
            if isinstance(value, bool) or not isinstance(value, int | float):
                return Failure(ValidationError(f"{name!r} must be a number"))
            return Success(value)
        case ExtensionFieldType.DATE:
            if not isinstance(value, str):
                return Failure(ValidationError(f"{name!r} must be an ISO-8601 date string"))
            try:
                date.fromisoformat(value)
            except ValueError:
                return Failure(
                    ValidationError(f"{name!r} must be an ISO-8601 date string, got {value!r}")
                )
            return Success(value)  # store the original string — JSONB can't hold a `date`
        case ExtensionFieldType.ENUM:
            if value not in (field.options or ()):
                return Failure(ValidationError(f"{name!r} must be one of {field.options}"))
            return Success(value)
        case _:  # pragma: no cover — ExtensionFieldType's 7 members are all matched above
            raise AssertionError(f"unhandled ExtensionFieldType: {field.field_type!r}")


class ExtensionValidator:
    """One public method: validate a submitted ``extensions`` bag and merge it
    onto a record's existing one."""

    def __init__(self, repo: ExtensionFieldDefRepository) -> None:
        self._repo = repo

    async def validate_and_merge(
        self,
        workspace_id: uuid.UUID,
        kind: str,
        submitted: dict[str, Any],
        existing: dict[str, Any],
    ) -> Result[dict[str, Any], DomainError]:
        """Every key in ``submitted`` must be declared for ``kind``, else this
        fails with a ``ValidationError`` naming the offending key. A ``None``
        value removes that key from the result — the per-key idiom for
        clearing a declared field. Keys ``existing`` carries that ``submitted``
        never mentions survive untouched, so an edit to one declared field
        cannot collateral-damage values the workspace never declared (e.g.
        imported data).
        """
        declared = {d.name: d for d in await self._repo.list_for_kind(workspace_id, kind)}
        merged = dict(existing)
        for key, value in submitted.items():
            field = declared.get(key)
            if field is None:
                return Failure(
                    ValidationError(f"{key!r} is not a declared extension field for {kind!r}")
                )
            if value is None:
                merged.pop(key, None)
                continue
            match _typecheck(field, value):
                case Failure(error):
                    return Failure(error)
                case Success(checked):
                    merged[key] = checked
        return Success(merged)
