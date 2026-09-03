"""Shared authorisation rules for both the bot and the API."""
from __future__ import annotations

import discord

from .config import get_settings


def member_is_admin(member: discord.Member | None) -> bool:
    """True when the member holds one of the configured admin roles.

    Guild administrators always qualify, so the alliance leader is never locked
    out by a role rename.
    """
    if member is None:
        return False
    if member.guild_permissions.administrator:
        return True
    allowed = {r.casefold() for r in get_settings().admin_roles}
    return any(role.name.casefold() in allowed for role in member.roles)


def admin_only():
    """Slash-command check restricting a command to alliance officers."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if not member_is_admin(
            interaction.user if isinstance(interaction.user, discord.Member) else None
        ):
            raise discord.app_commands.CheckFailure(
                "This command is limited to alliance officers."
            )
        return True

    return discord.app_commands.check(predicate)
