"""Unit tests for ExtensionValidator (in-memory fake repository — no DB)."""

from __future__ import annotations

import uuid

from returns.result import Failure

from protcellar.application.target_biology.extension_validator import ExtensionValidator
from protcellar.domain.workspace_config.extension_fields.field_def import (
    ExtensionFieldDef,
    ExtensionFieldType,
)

WS = uuid.uuid4()


class _FakeRepo:
    def __init__(self, defs: list[ExtensionFieldDef]) -> None:
        self._defs = defs

    async def list_for_kind(self, workspace_id: uuid.UUID, kind: str) -> list[ExtensionFieldDef]:
        return self._defs


def _validator(defs: list[ExtensionFieldDef]) -> ExtensionValidator:
    return ExtensionValidator(_FakeRepo(defs))  # type: ignore[arg-type]


def _field(
    name: str, field_type: ExtensionFieldType, options: list[str] | None = None
) -> ExtensionFieldDef:
    return ExtensionFieldDef.create(
        workspace_id=WS,
        kind="vulnerability",
        name=name,
        label=name,
        field_type=field_type,
        options=options,
        position=0,
        show_in_table=False,
    )


def _num(name: str) -> ExtensionFieldDef:
    return _field(name, ExtensionFieldType.NUMBER)


def _int(name: str) -> ExtensionFieldDef:
    return _field(name, ExtensionFieldType.INTEGER)


def _date(name: str) -> ExtensionFieldDef:
    return _field(name, ExtensionFieldType.DATE)


def _enum(name: str, options: list[str]) -> ExtensionFieldDef:
    return _field(name, ExtensionFieldType.ENUM, options)


# --- Brief's given cases -----------------------------------------------------


async def test_unknown_key_is_rejected() -> None:
    r = await _validator([_num("bin")]).validate_and_merge(WS, "vulnerability", {"nope": 1}, {})
    assert isinstance(r, Failure) and "nope" in str(r.failure().message)


async def test_wrong_type_is_rejected() -> None:
    r = await _validator([_num("bin")]).validate_and_merge(
        WS, "vulnerability", {"bin": "not a number"}, {}
    )
    assert isinstance(r, Failure)


async def test_enum_value_outside_options_is_rejected() -> None:
    r = await _validator([_enum("call", ["yes", "no"])]).validate_and_merge(
        WS, "vulnerability", {"call": "maybe"}, {}
    )
    assert isinstance(r, Failure)


async def test_undeclared_stored_values_survive_a_write() -> None:
    """Imported keys nobody declared must not be collateral damage of editing a declared one."""
    r = await _validator([_num("bin")]).validate_and_merge(
        WS, "vulnerability", {"bin": 5}, {"rank": "2398.0", "pct_of_max": "7%"}
    )
    assert r.unwrap() == {"rank": "2398.0", "pct_of_max": "7%", "bin": 5}


async def test_explicit_null_removes_a_declared_key() -> None:
    r = await _validator([_num("bin")]).validate_and_merge(
        WS, "vulnerability", {"bin": None}, {"bin": 5, "rank": "2398.0"}
    )
    assert r.unwrap() == {"rank": "2398.0"}


# --- Trap coverage: isinstance(True, int) is True in Python ------------------


async def test_integer_rejects_a_bool() -> None:
    r = await _validator([_int("count")]).validate_and_merge(
        WS, "vulnerability", {"count": True}, {}
    )
    assert isinstance(r, Failure)


async def test_number_rejects_a_bool() -> None:
    r = await _validator([_num("bin")]).validate_and_merge(WS, "vulnerability", {"bin": False}, {})
    assert isinstance(r, Failure)


async def test_integer_accepts_a_whole_float_but_rejects_a_fraction() -> None:
    validator = _validator([_int("count")])
    ok = await validator.validate_and_merge(WS, "vulnerability", {"count": 5.0}, {})
    merged = ok.unwrap()
    assert merged == {"count": 5}
    # {"count": 5.0} == {"count": 5} is also True in Python — the equality assertion
    # above can't catch a regression to `Success(value)` storing the raw float back.
    assert type(merged["count"]) is int

    bad = await validator.validate_and_merge(WS, "vulnerability", {"count": 5.5}, {})
    assert isinstance(bad, Failure)


# --- Trap coverage: JSONB cannot hold a `date` object -------------------------


async def test_date_is_validated_but_stored_as_the_original_string() -> None:
    r = await _validator([_date("observed_on")]).validate_and_merge(
        WS, "vulnerability", {"observed_on": "2026-01-15"}, {}
    )
    merged = r.unwrap()
    assert merged == {"observed_on": "2026-01-15"}
    assert isinstance(merged["observed_on"], str)  # never a `date` — JSONB can't hold one


async def test_malformed_date_is_rejected() -> None:
    r = await _validator([_date("observed_on")]).validate_and_merge(
        WS, "vulnerability", {"observed_on": "not-a-date"}, {}
    )
    assert isinstance(r, Failure)
