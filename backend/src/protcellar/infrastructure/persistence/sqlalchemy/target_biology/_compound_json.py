"""(De)serialise cross-cellar CompoundRef VOs to/from JSON columns."""

from __future__ import annotations

import uuid

from protcellar.domain.shared.compound_ref import CompoundRef


def compound_to_json(ref: CompoundRef | None) -> dict[str, object] | None:
    if ref is None:
        return None
    return {"compound_id": str(ref.compound_id), "name": ref.name}


def compound_from_json(data: dict[str, object] | None) -> CompoundRef | None:
    if not data:
        return None
    name = data.get("name")
    return CompoundRef(
        compound_id=uuid.UUID(str(data["compound_id"])),
        name=str(name) if name is not None else None,
    )


def ligands_to_json(ligands: tuple[CompoundRef, ...]) -> list[dict[str, object]] | None:
    return [{"compound_id": str(c.compound_id), "name": c.name} for c in ligands] or None


def ligands_from_json(data: list[dict[str, object]] | None) -> tuple[CompoundRef, ...]:
    if not data:
        return ()
    return tuple(
        CompoundRef(
            compound_id=uuid.UUID(str(d["compound_id"])),
            name=str(d["name"]) if d.get("name") is not None else None,
        )
        for d in data
    )
