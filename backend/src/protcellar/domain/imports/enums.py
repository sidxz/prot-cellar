from __future__ import annotations

from enum import StrEnum


class ImportType(StrEnum):
    PROTEOME = "proteome"
    GENE_ENRICHMENT = "gene_enrichment"
    GO_ONTOLOGY = "go_ontology"
    PLUGIN = "plugin"


class ImportStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
