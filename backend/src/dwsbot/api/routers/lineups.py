"""The shared Pass Occupation War line-up.

One plan per slug, readable by any member of the alliance guild and writable by
officers. The map generator at pou-rocks.github.io/pou-pass-war is the client.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ...models import WarLineup
from ...schemas import LineupIn, LineupOut
from ..deps import AdminUser, CurrentUser, DbSession, write_audit

router = APIRouter(prefix="/lineups", tags=["lineups"])

DEFAULT_SLUG = "default"


@router.get("/{slug}", response_model=LineupOut, summary="Read the shared line-up")
async def get_lineup(slug: str, session: DbSession, _: CurrentUser) -> WarLineup:
    row = await session.get(WarLineup, slug)
    if row is None:
        # An empty plan is a valid answer: the client falls back to BGB order.
        return WarLineup(slug=slug, order=[], mercs=[], opts={})
    return row


@router.put("/{slug}", response_model=LineupOut, summary="Replace the shared line-up")
async def put_lineup(
    slug: str, payload: LineupIn, session: DbSession, user: AdminUser
) -> WarLineup:
    if len(payload.order) > 1000 or len(payload.mercs) > 200:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Line-up is too large")

    row = await session.get(WarLineup, slug)
    if row is None:
        row = WarLineup(slug=slug)
        session.add(row)
    row.order = payload.order
    row.mercs = [m.model_dump() for m in payload.mercs]
    row.opts = payload.opts
    row.updated_by_id = user.discord_id
    row.updated_by_name = user.username
    await write_audit(
        session, user, "lineup.save", "war_lineup", slug,
        {"members": len(payload.order), "mercs": len(payload.mercs)},
    )
    await session.commit()
    await session.refresh(row)
    return row


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT, summary="Clear the line-up")
async def delete_lineup(slug: str, session: DbSession, user: AdminUser) -> None:
    row = await session.get(WarLineup, slug)
    if row is not None:
        await session.delete(row)
        await write_audit(session, user, "lineup.clear", "war_lineup", slug)
        await session.commit()


@router.get("", summary="List saved line-ups")
async def list_lineups(session: DbSession, _: CurrentUser):
    rows = (await session.scalars(select(WarLineup))).all()
    return [
        {"slug": r.slug, "members": len(r.order or []), "mercs": len(r.mercs or []),
         "updated_by_name": r.updated_by_name, "updated_at": r.updated_at}
        for r in rows
    ]
