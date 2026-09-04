"""Who changed what, and when.

Reads the audit log the mutating endpoints already write to, so nothing here
needs the writers to cooperate — a new action shows up automatically.
"""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from ...models import AuditLog
from ...names import guild_display_name
from ...schemas import AuditOut
from ..deps import AdminUser, DbSession

router = APIRouter(prefix="/history", tags=["history"])

# Actions that only record a read or a test send would drown the useful ones.
NOISE = {"announcement.test"}


@router.get("", response_model=list[AuditOut])
async def list_history(
    session: DbSession,
    _: AdminUser,
    limit: int = Query(60, ge=1, le=300),
    entity: str | None = Query(None, description="Filter to 'announcement' or 'event'"),
    include_tests: bool = False,
):
    stmt = select(AuditLog).order_by(AuditLog.at.desc()).limit(limit)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if not include_tests:
        stmt = stmt.where(AuditLog.action.not_in(NOISE))
    rows = list(await session.scalars(stmt))
    return [
        AuditOut(
            id=r.id, at=r.at, action=r.action, entity=r.entity,
            entity_id=r.entity_id, detail=r.detail,
            # Live, so history reads in today's names rather than whatever the
            # person happened to be called at the time.
            actor_name=guild_display_name(r.actor_discord_id, r.actor_name),
        )
        for r in rows
    ]
