from __future__ import annotations

from typing import Any

from protcellar.application.plugins.manifest import ParamField, ParamType, PluginManifest
from protcellar.domain.shared.errors import ValidationError as DomainValidationError


def validate_against_manifest(manifest: PluginManifest, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate + coerce a raw param dict against a manifest's ParamField descriptor.

    Only keys declared on the manifest survive. Raises DomainValidationError on a
    missing required field or a bad value.
    """
    out: dict[str, Any] = {}
    for pf in manifest.params:
        raw_value = raw.get(pf.key)
        present = raw_value is not None and raw_value != ""
        if not present:
            if pf.required:
                raise DomainValidationError(f"missing required param '{pf.key}'")
            if pf.default is not None:
                out[pf.key] = pf.default
            continue
        out[pf.key] = _coerce(pf, raw_value)
    return out


def _coerce(pf: ParamField, value: Any) -> Any:
    if pf.type is ParamType.NUMBER:
        text = str(value)
        try:
            return float(text) if "." in text else int(text)
        except ValueError as e:
            raise DomainValidationError(f"param '{pf.key}' must be a number") from e
    if pf.type is ParamType.BOOL:
        return str(value).strip().lower() not in {"false", "0", "no", "off", ""}
    if pf.type is ParamType.ENUM:
        if str(value) not in pf.options:
            raise DomainValidationError(f"param '{pf.key}' must be one of {list(pf.options)}")
        return str(value)
    # STRING, ORGANISM, FILE_UPLOAD — pass through as string.
    return str(value)
