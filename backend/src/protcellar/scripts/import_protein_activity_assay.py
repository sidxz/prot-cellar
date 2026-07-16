"""CLI: bulk-import ProteinActivityAssay records from a CSV/TSV file. See _protein_import_cli."""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_protein_activity_assay import (
    BulkUpsertProteinActivityAssay,
    BulkUpsertProteinActivityAssayCommand,
)
from protcellar.infrastructure.ingestion.protein_activity_assay_csv import (
    parse_protein_activity_assay_csv,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.protein_activity_assay_repository import (  # noqa: E501
    SQLAlchemyProteinActivityAssayRepository,
)
from protcellar.scripts._protein_import_cli import protein_import_main

if __name__ == "__main__":
    protein_import_main(
        description="Bulk-import ProteinActivityAssay records from a file.",
        parse=parse_protein_activity_assay_csv,
        command_cls=BulkUpsertProteinActivityAssayCommand,
        use_case_cls=BulkUpsertProteinActivityAssay,
        record_repo_cls=SQLAlchemyProteinActivityAssayRepository,
    )
