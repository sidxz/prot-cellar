from protcellar.infrastructure.identifiers.registry import IdentifierRegistry


def test_validates_uniprot_accession() -> None:
    reg = IdentifierRegistry.default()
    assert reg.validate("uniprot", "P0DTC2") is True
    assert reg.validate("uniprot", "not-an-accession") is False


def test_resolves_url() -> None:
    reg = IdentifierRegistry.default()
    assert reg.resolve_url("uniprot", "P0DTC2") == "https://identifiers.org/uniprot:P0DTC2"


def test_unknown_prefix_is_invalid() -> None:
    reg = IdentifierRegistry.default()
    assert reg.validate("bogusdb", "x") is False
    assert reg.resolve_url("bogusdb", "x") is None
