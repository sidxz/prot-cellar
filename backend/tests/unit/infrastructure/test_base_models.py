from protcellar.infrastructure.persistence.sqlalchemy.base import (
    EntityModelMixin,
    VersionMixin,
    WorkspaceIdMixin,
)


def test_mixins_declare_expected_columns() -> None:
    assert hasattr(EntityModelMixin, "id")
    assert hasattr(WorkspaceIdMixin, "workspace_id")
    assert hasattr(VersionMixin, "version")
