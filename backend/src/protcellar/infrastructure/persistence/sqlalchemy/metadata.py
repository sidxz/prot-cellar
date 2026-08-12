"""Central model aggregator for Alembic autogenerate.

Import all SQLAlchemy model modules here so that Base.metadata includes
every table when alembic --autogenerate inspects the schema.

Tasks 9, 10, and the taxonomy plan append model-module imports below.
"""

import protcellar.infrastructure.persistence.sqlalchemy.audit_compliance.models

# --- model module imports (appended by Tasks 9, 10, taxonomy plan) ---
import protcellar.infrastructure.persistence.sqlalchemy.gene_ontology.models
import protcellar.infrastructure.persistence.sqlalchemy.imports.models
import protcellar.infrastructure.persistence.sqlalchemy.plugins.models
import protcellar.infrastructure.persistence.sqlalchemy.protein_catalog.models
import protcellar.infrastructure.persistence.sqlalchemy.tagging.models
import protcellar.infrastructure.persistence.sqlalchemy.target.models
import protcellar.infrastructure.persistence.sqlalchemy.target_biology.models
import protcellar.infrastructure.persistence.sqlalchemy.taxonomy.models
import protcellar.infrastructure.persistence.sqlalchemy.workspace_config.models  # noqa: F401
from protcellar.infrastructure.persistence.sqlalchemy.base import Base  # noqa: F401
