"""Pass Occupation War line-ups: per-officer drafts plus one published plan.

Every officer keeps a draft nobody else can overwrite. Publishing copies a draft
into the shared "official" plan, so picking a final does not consume anyone's
work — the draft it came from is left exactly where it was.

Any member of the guild may read. Only officers write, and only their own draft.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ...models import WarLineup
from ...schemas import LineupIn, LineupOut, LineupSummary
from ..deps import AdminUser, CurrentUser, DbSession, write_audit

router = APIRouter(prefix="/lineups", tags=["lineups"])

OFFICIAL = "official"
DRAFT_PREFIX = "draft:"


def draft_slug(discord_id: int) -> str:
    return f"{DRAFT_PREFIX}{discord_id}"


def _empty(slug: str) -> WarLineup:
    # An absent plan reads as an empty one; the client falls back to BGB order.
    return WarLineup(slug=slug, order=[], mercs=[], opts={})


@router.get("", response_model=list[LineupSummary], summary="List the published plan and every draft")
async def list_lineups(session: DbSession, _: CurrentUser) -> list[LineupSummary]:
    rows = (await session.scalars(select(WarLineup))).all()
    out = [
        LineupSummary(
            slug=r.slug, title=r.title, owner_id=r.owner_id, owner_name=r.owner_name,
            updated_by_name=r.updated_by_name, updated_at=r.updated_at,
            members=len(r.order or []), mercs=len(r.mercs or []),
        )
        for r in rows
    ]
    # Published first, then most recently touched drafts.
    out.sort(key=lambda r: (r.slug != OFFICIAL, -(r.updated_at.timestamp() if r.updated_at else 0)))
    return out


@router.get("/{slug}", response_model=LineupOut, summary="Read one plan")
async def get_lineup(slug: str, session: DbSession, _: CurrentUser) -> WarLineup:
    return await session.get(WarLineup, slug) or _empty(slug)


@router.put("/{slug}", response_model=LineupOut, summary="Save the published plan or your own draft")
async def put_lineup(
    slug: str, payload: LineupIn, session: DbSession, user: AdminUser
) -> WarLineup:
    if len(payload.order) > 1000 or len(payload.mercs) > 200:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Line-up is too large")

    row = await session.get(WarLineup, slug)
    if slug != OFFICIAL:
        # A draft is one officer's. Claiming a free slug is fine; taking someone
        # else's is not — that is the whole point of separating drafts.
        if row is not None and row.owner_id not in (None, user.discord_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"That draft belongs to {row.owner_name or 'another officer'}",
            )
        if slug != draft_slug(user.discord_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Save to your own draft")

    if row is None:
        row = WarLineup(slug=slug)
        session.add(row)
    row.order = payload.order
    row.mercs = [m.model_dump() for m in payload.mercs]
    row.opts = payload.opts
    row.title = payload.title
    row.updated_by_id = user.discord_id
    row.updated_by_name = user.username
    if slug != OFFICIAL:
        row.owner_id = user.discord_id
        row.owner_name = user.username
    await write_audit(
        session, user, "lineup.save", "war_lineup", slug,
        {"members": len(payload.order), "mercs": len(payload.mercs)},
    )
    await session.commit()
    await session.refresh(row)
    return row


@router.post("/{slug}/publish", response_model=LineupOut, summary="Publish a plan as the official one")
async def publish(slug: str, session: DbSession, user: AdminUser) -> WarLineup:
    src = await session.get(WarLineup, slug)
    if src is None or not src.order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That plan is empty or does not exist")

    official = await session.get(WarLineup, OFFICIAL)
    if official is None:
        official = WarLineup(slug=OFFICIAL)
        session.add(official)
    # Copy, never move: the draft stays put so its author keeps working on it.
    official.order = list(src.order or [])
    official.mercs = list(src.mercs or [])
    official.opts = dict(src.opts or {})
    official.title = src.title
    official.owner_id = None
    official.owner_name = None
    official.updated_by_id = user.discord_id
    official.updated_by_name = user.username
    await write_audit(session, user, "lineup.publish", "war_lineup", OFFICIAL, {"from": slug})
    await session.commit()
    await session.refresh(official)
    return official


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete your draft")
async def delete_lineup(slug: str, session: DbSession, user: AdminUser) -> None:
    row = await session.get(WarLineup, slug)
    if row is None:
        return
    if slug != OFFICIAL and row.owner_id not in (None, user.discord_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That draft belongs to another officer")
    await session.delete(row)
    await write_audit(session, user, "lineup.delete", "war_lineup", slug)
    await session.commit()
