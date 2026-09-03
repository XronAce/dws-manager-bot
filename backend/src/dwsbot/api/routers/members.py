"""Roster management from the backoffice."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ...models import Member
from ...schemas import MemberOut, MemberUpdate
from ..deps import AdminUser, DbSession, write_audit

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberOut])
async def list_members(session: DbSession, _: AdminUser, include_inactive: bool = False):
    stmt = select(Member).order_by(Member.rank.desc().nullslast(), Member.power.desc().nullslast())
    if not include_inactive:
        stmt = stmt.where(Member.active.is_(True))
    return list(await session.scalars(stmt))


@router.put("/{member_id}", response_model=MemberOut)
async def update_member(
    member_id: int, payload: MemberUpdate, session: DbSession, user: AdminUser
):
    member = await session.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such member")
    # exclude_unset so a partial edit does not blank the untouched columns.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    await write_audit(
        session, user, "member.update", "member", member.id, {"name": member.game_name}
    )
    await session.commit()
    return member


@router.post("/sync", summary="Import guild members that are not on the roster yet")
async def sync_from_guild(session: DbSession, user: AdminUser):
    from ...config import get_settings
    from ...discord_bot.bot import bot

    guild = bot.get_guild(get_settings().guild_id)
    if guild is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The bot is not connected to Discord yet"
        )

    existing = set(await session.scalars(select(Member.discord_id)))
    added = 0
    for m in guild.members:
        if m.bot or m.id in existing:
            continue
        session.add(Member(discord_id=m.id, discord_name=str(m), game_name=m.display_name))
        added += 1

    await write_audit(session, user, "member.sync", "member", None, {"added": added})
    await session.commit()
    return {"added": added, "guild_members": len(guild.members)}
