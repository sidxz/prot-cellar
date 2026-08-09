"""CLI: bulk-import Hypomorph records from a CSV/TSV file. See _gene_import_cli."""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_hypomorph import (
    BulkUpsertHypomorph,
    BulkUpsertHypomorphCommand,
)
from protcellar.infrastructure.ingestion.hypomorph_csv import parse_hypomorph_csv
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.crispri_strain_repository import (  # noqa: E501
    SQLAlchemyCrispriStrainRepository,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.hypomorph_repository import (
    SQLAlchemyHypomorphRepository,
)
from protcellar.scripts._gene_import_cli import gene_import_main

if __name__ == "__main__":
    gene_import_main(
        description="Bulk-import Hypomorph records from a file.",
        parse=parse_hypomorph_csv,
        command_cls=BulkUpsertHypomorphCommand,
        use_case_cls=BulkUpsertHypomorph,
        record_repo_cls=SQLAlchemyHypomorphRepository,
        extra_repo_cls=SQLAlchemyCrispriStrainRepository,
    )
