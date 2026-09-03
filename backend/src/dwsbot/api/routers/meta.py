"""Guild metadata the backoffice needs to render its forms, plus health."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from ...config import get_settings
from ...scheduler import scheduler
from ...schemas import ChannelOut, HealthOut, RoleOut
from ..deps import AdminUser, DbSession

router = APIRouter(tags=["meta"])


@router.get("/channels", response_model=list[ChannelOut])
async def list_channels(_: AdminUser):
    """Text channels the bot can actually post to.

    Filtered by real permissions so the backoffice cannot offer a channel that
    would fail at send time.
    """
    from ...discord_bot.bot import bot

    guild = bot.get_guild(get_settings().guild_id)
    if guild is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The bot is not connected to Discord yet"
        )

    return [
        ChannelOut(
            id=c.id,
            name=c.name,
            category=c.category.name if c.category else None,
        )
        for c in guild.text_channels
        if c.permissions_for(guild.me).send_messages
    ]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(_: AdminUser):
    from ...discord_bot.bot import bot

    guild = bot.get_guild(get_settings().guild_id)
    if guild is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The bot is not connected to Discord yet"
        )

    return [
        RoleOut(id=r.id, name=r.name, color=f"#{r.colour.value:06x}")
        for r in guild.roles
        if not r.is_default()
    ]


@router.get("/health", response_model=HealthOut, summary="Liveness and dependency check")
async def health(session: DbSession):
    """Unauthenticated on purpose — this is what the k8s probes call."""
    from ...discord_bot.bot import bot

    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return HealthOut(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        discord=bot.is_ready(),
        scheduled_jobs=len(scheduler.jobs),
        bot_user=str(bot.user) if bot.user else None,
    )
