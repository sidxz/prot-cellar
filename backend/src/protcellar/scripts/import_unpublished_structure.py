"""CLI: bulk-import UnpublishedStructure records from a CSV/TSV file. See _protein_import_cli."""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_unpublished_structure import (
    BulkUpsertUnpublishedStructure,
    BulkUpsertUnpublishedStructureCommand,
)
from protcellar.infrastructure.ingestion.unpublished_structure_csv import (
    parse_unpublished_structure_csv,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.unpublished_structure_repository import (  # noqa: E501
    SQLAlchemyUnpublishedStructureRepository,
)
from protcellar.scripts._protein_import_cli import protein_import_main

if __name__ == "__main__":
    protein_import_main(
        description="Bulk-import UnpublishedStructure records from a file.",
        parse=parse_unpublished_structure_csv,
        command_cls=BulkUpsertUnpublishedStructureCommand,
        use_case_cls=BulkUpsertUnpublishedStructure,
        record_repo_cls=SQLAlchemyUnpublishedStructureRepository,
    )
