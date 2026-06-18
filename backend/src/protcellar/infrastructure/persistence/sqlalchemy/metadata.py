"""Central model aggregator for Alembic autogenerate.

Import all SQLAlchemy model modules here so that Base.metadata includes
every table when alembic --autogenerate inspects the schema.

Tasks 9, 10, and the taxonomy plan append model-module imports below.
"""

import protcellar.infrastructure.persistence.sqlalchemy.audit_compliance.models  # noqa: F401
from protcellar.infrastructure.persistence.sqlalchemy.base import Base  # noqa: F401

# --- model module imports (appended by Tasks 9, 10, taxonomy plan) ---
