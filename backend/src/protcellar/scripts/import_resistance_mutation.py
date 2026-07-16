"""CLI: bulk-import ResistanceMutation records from a CSV/TSV file. See _gene_import_cli."""

from __future__ import annotations

from protcellar.application.target_biology.bulk_upsert_resistance_mutation import (
    BulkUpsertResistanceMutation,
    BulkUpsertResistanceMutationCommand,
)
from protcellar.infrastructure.ingestion.resistance_mutation_csv import (
    parse_resistance_mutation_csv,
)
from protcellar.infrastructure.persistence.sqlalchemy.target_biology.resistance_mutation_repository import (  # noqa: E501
    SQLAlchemyResistanceMutationRepository,
)
from protcellar.scripts._gene_import_cli import gene_import_main

if __name__ == "__main__":
    gene_import_main(
        description="Bulk-import ResistanceMutation records from a file.",
        parse=parse_resistance_mutation_csv,
        command_cls=BulkUpsertResistanceMutationCommand,
        use_case_cls=BulkUpsertResistanceMutation,
        record_repo_cls=SQLAlchemyResistanceMutationRepository,
    )
