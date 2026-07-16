"""CLI: bulk-import ProteinProduction records from a CSV/TSV file. See _protein_import_cli."""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_protein_production import (
    BulkUpsertProteinProduction,
    BulkUpsertProteinProductionCommand,
)
from protcellar.infrastructure.ingestion.protein_production_csv import (
    parse_protein_production_csv,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.protein_production_repository import (  # noqa: E501
    SQLAlchemyProteinProductionRepository,
)
from protcellar.scripts._protein_import_cli import protein_import_main

if __name__ == "__main__":
    protein_import_main(
        description="Bulk-import ProteinProduction records from a file.",
        parse=parse_protein_production_csv,
        command_cls=BulkUpsertProteinProductionCommand,
        use_case_cls=BulkUpsertProteinProduction,
        record_repo_cls=SQLAlchemyProteinProductionRepository,
    )
