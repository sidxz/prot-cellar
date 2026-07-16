"""CLI: bulk-import Essentiality records from a CSV/TSV file. See _gene_import_cli."""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_essentiality import (
    BulkUpsertEssentiality,
    BulkUpsertEssentialityCommand,
)
from protcellar.infrastructure.ingestion.essentiality_csv import parse_essentiality_csv
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.essentiality_repository import (  # noqa: E501
    SQLAlchemyEssentialityRepository,
)
from protcellar.scripts._gene_import_cli import gene_import_main

if __name__ == "__main__":
    gene_import_main(
        description="Bulk-import Essentiality records from a file.",
        parse=parse_essentiality_csv,
        command_cls=BulkUpsertEssentialityCommand,
        use_case_cls=BulkUpsertEssentiality,
        record_repo_cls=SQLAlchemyEssentialityRepository,
    )
