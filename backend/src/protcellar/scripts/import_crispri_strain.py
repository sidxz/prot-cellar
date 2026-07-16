"""CLI: bulk-import CrispriStrain records from a CSV/TSV file. See _gene_import_cli."""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_crispri_strain import (
    BulkUpsertCrispriStrain,
    BulkUpsertCrispriStrainCommand,
)
from protcellar.infrastructure.ingestion.crispri_strain_csv import parse_crispri_strain_csv
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.crispri_strain_repository import (  # noqa: E501
    SQLAlchemyCrispriStrainRepository,
)
from protcellar.scripts._gene_import_cli import gene_import_main

if __name__ == "__main__":
    gene_import_main(
        description="Bulk-import CrispriStrain records from a file.",
        parse=parse_crispri_strain_csv,
        command_cls=BulkUpsertCrispriStrainCommand,
        use_case_cls=BulkUpsertCrispriStrain,
        record_repo_cls=SQLAlchemyCrispriStrainRepository,
    )
