"""Shared tag-filter subquery builder, reused by the search composer and the
per-entity list repositories. Returns a Select of entity ids that carry the
given tags (``match_all=False`` = any of them; ``match_all=True`` = all of them).

``workspace_id`` is required: a link is only counted if its ``tag_id`` actually
belongs to the caller's workspace, so a foreign tag id passed by a caller (e.g.
guessed or copy-pasted from another workspace) is silently ignored rather than
leaking entities. Mirrors the same guard in ``SQLAlchemyTagBrowseRepository``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import distinct, func, select
from sqlalchemy.sql import Select

from protcellar.infrastructure.persistence.sqlalchemy.tagging.models import TagModel


def tag_filter_subquery(
    link_model: type,
    entity_id_attr: str,
    tag_ids: list[uuid.UUID],
    *,
    workspace_id: uuid.UUID,
    match_all: bool,
) -> Select:
    col = getattr(link_model, entity_id_attr)
    unique_ids = list(dict.fromkeys(tag_ids))  # dedup, preserve order
    stmt = (
        select(col)
        .join(TagModel, TagModel.id == link_model.tag_id)
        .where(TagModel.workspace_id == workspace_id, link_model.tag_id.in_(unique_ids))
    )
    if match_all:
        stmt = stmt.group_by(col).having(
            func.count(distinct(link_model.tag_id)) == len(unique_ids)
        )
    else:
        stmt = stmt.distinct()
    return stmt
