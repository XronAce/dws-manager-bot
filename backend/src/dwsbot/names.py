"""Resolving what to call someone, at read time rather than write time.

A name written into a row is frozen: change your server nickname and every
byline you ever created still shows the old one. Discord IDs do not change,
so rows store the id and the display name is looked up when it is shown.

The lookup is the bot's in-memory guild cache — no API call, no await.
"""
from __future__ import annotations

from .config import get_settings


def guild_display_name(discord_id: int | None, fallback: str | None = None) -> str | None:
    """The member's server nickname, else their Discord name, else `fallback`.

    Falls back whenever the bot is not connected or the person has left the
    guild, so a byline never disappears just because someone is gone.
    """
    if discord_id is None:
        return fallback

    try:
        from .discord_bot.bot import bot

        guild = bot.get_guild(get_settings().guild_id)
        member = guild.get_member(discord_id) if guild else None
    except Exception:
        return fallback

    if member is None:
        return fallback
    for candidate in (member.nick, member.global_name, member.name):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return fallback
