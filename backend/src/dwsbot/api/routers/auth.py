"""Discord OAuth2 login for the backoffice."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from ...config import get_settings
from ...models import AppUser
from ...schemas import MeOut
from ...security import (
    authorize_url,
    exchange_code,
    fetch_identity,
    issue_token,
    make_state,
    verify_state,
)
from ..deps import CurrentUser, DbSession

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", summary="Begin Discord OAuth2 login")
async def login(app: str = Query("backoffice")) -> RedirectResponse:
    settings = get_settings()
    if not settings.oauth_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "OAuth is not configured — set DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET",
        )
    return RedirectResponse(authorize_url(make_state(app)))


@router.get("/callback", summary="OAuth2 redirect target")
async def callback(session: DbSession, code: str = Query(...), state: str = Query(...)):
    settings = get_settings()
    app = verify_state(state)
    if app is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Login state expired or invalid")
    back = settings.frontend_url if app == "backoffice" else settings.passwar_url

    access_token = await exchange_code(code)
    user, role_ids, in_guild = await fetch_identity(access_token)

    # OAuth gives role IDs; the config names roles. Resolve via the live guild
    # so officers can rename roles without editing environment variables.
    from ...discord_bot.bot import bot

    is_admin = False
    guild = bot.get_guild(settings.guild_id)
    if guild is not None:
        allowed = {r.casefold() for r in settings.admin_roles}
        for rid in role_ids:
            role = guild.get_role(int(rid))
            if role and role.name.casefold() in allowed:
                is_admin = True
                break
        if not is_admin and guild.owner_id == int(user["id"]):
            is_admin = True
    else:
        log.warning("guild %s not in cache; cannot verify roles", settings.guild_id)

    discord_id = int(user["id"])
    row = await session.scalar(select(AppUser).where(AppUser.discord_id == discord_id))
    if row is None:
        row = AppUser(discord_id=discord_id)
        session.add(row)
    row.username = user.get("global_name") or user.get("username")
    row.avatar = user.get("avatar")
    row.is_admin = is_admin       # refreshed from live roles on every login
    row.last_login_at = datetime.now(UTC)
    await session.commit()

    # The backoffice is officers-only. The map generator admits any member of the
    # guild and lets the token's is_admin decide who may save the shared plan.
    permitted = is_admin if app == "backoffice" else in_guild
    if not permitted:
        # Bounce back with a reason rather than handing out a useless token.
        reason = "not_authorised" if app == "backoffice" else "not_in_guild"
        return RedirectResponse(f"{back}/#" + urlencode({"error": reason}))

    token = issue_token(
        discord_id=discord_id, username=row.username or "?", is_admin=is_admin
    )
    # Fragment, not query string: it never reaches a server log or a Referer header.
    return RedirectResponse(f"{back}/#" + urlencode({"token": token}))


@router.get("/me", response_model=MeOut, summary="Who am I")
async def me(user: CurrentUser) -> MeOut:
    return user
