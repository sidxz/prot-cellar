"""Duar auth integration — SDK initialization and FastAPI wiring."""

from __future__ import annotations

from duar_auth import Duar

from protcellar.infrastructure.duar.settings import DuarSettings
from protcellar.infrastructure.logging import get_logger

logger = get_logger(__name__)

# Service actions registered with Duar on startup.
# These correspond to RBAC permissions that can be granted to roles.
SERVICE_ACTIONS = [
    {"action": "protcellar:read", "description": "Read catalog entities"},
    {"action": "protcellar:write", "description": "Create/update catalog entities"},
    {"action": "protcellar:bulk_import", "description": "Bulk-import reference data"},
    {"action": "protcellar:admin_config", "description": "Modify workspace settings"},
]


async def register_service_actions(duar: Duar) -> bool:
    """Register this service's RBAC actions, best-effort, at startup.

    Action definitions change rarely and are not needed to serve requests, so a
    transient Duar slowdown/outage must never block boot. On failure we log
    and continue; a later successful startup re-registers. Returns ``True`` iff
    registration succeeded.
    """
    try:
        await duar.roles.register_actions(SERVICE_ACTIONS)
    except Exception:
        logger.exception("duar.actions_register_failed", action_count=len(SERVICE_ACTIONS))
        return False
    logger.info("duar.actions_registered", action_count=len(SERVICE_ACTIONS))
    return True


def create_duar(settings: DuarSettings | None = None) -> Duar:
    """Create and configure a new Duar instance.

    The returned object provides:
    - ``duar.lifespan`` — FastAPI lifespan (fetches the JWKS signing key)
    - ``duar.protect(app)`` — adds auth middleware
    - ``duar.get_auth`` — FastAPI dependency returning ``RequestAuth``
    - ``duar.require_user`` — FastAPI dependency returning ``AuthenticatedUser``

    Note: ``actions`` is intentionally NOT passed here. The SDK lifespan would
    register them synchronously and treat any failure as fatal, so a slow/locked
    Duar turns a rarely-changing housekeeping call into a hard boot blocker.
    ``app.py`` registers ``SERVICE_ACTIONS`` best-effort instead (see
    ``register_service_actions``); the JWKS fetch stays fatal, as auth genuinely
    cannot work without the signing key.
    """
    if settings is None:
        settings = DuarSettings()

    return Duar(
        base_url=settings.url,
        service_name=settings.service_name,
        service_key=settings.service_key,
        mode="authz",
        idp_jwks_url=settings.idp_jwks_url,
        idp_audience=settings.idp_audience,
        idp_issuer=settings.idp_issuer or None,
        cache_ttl=settings.cache_ttl,
    )


def get_duar(settings: DuarSettings | None = None) -> Duar:
    """Create and return a new Duar instance.

    The caller (``create_app`` in ``app.py``) is expected to call this once
    during application startup and hold the reference.
    """
    return create_duar(settings)
