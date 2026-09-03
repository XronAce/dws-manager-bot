"""The Discord client: renders announcements and hosts the slash commands."""
from __future__ import annotations

import contextlib
import logging

import discord
from discord.ext import commands

from ..config import get_settings
from ..models import Announcement

log = logging.getLogger(__name__)

COGS = (
    "dwsbot.discord_bot.cogs.roster",
    "dwsbot.discord_bot.cogs.events",
    "dwsbot.discord_bot.cogs.admin",
)


def build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    # Privileged: enable "Server Members Intent" in the developer portal, or
    # role-based permission checks and roster sync will silently see nobody.
    intents.members = True
    return intents


class AllianceBot(commands.Bot):
    def __init__(self) -> None:
        self.settings = get_settings()
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=build_intents(),
            help_command=None,
        )

    async def setup_hook(self) -> None:
        for cog in COGS:
            try:
                await self.load_extension(cog)
            except Exception:
                log.exception("failed to load cog %s", cog)

        # Guild-scoped sync lands immediately; a global sync can take ~an hour.
        guild = discord.Object(id=self.settings.guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        log.info("synced %d slash commands to guild %s", len(synced), self.settings.guild_id)

    async def on_ready(self) -> None:
        log.info("logged in as %s (%s)", self.user, self.user.id if self.user else "?")

    # ---------------------------------------------------------------- sending

    def render(self, ann: Announcement) -> tuple[str | None, discord.Embed | None]:
        """Turn an announcement row into Discord message parts."""
        prefix = f"{ann.mention}\n" if ann.mention else ""

        if not ann.use_embed:
            title = f"**{ann.title}**\n" if ann.title else ""
            return f"{prefix}{title}{ann.body}", None

        colour = discord.Colour.blurple()
        if ann.embed_color:
            # A malformed colour must not stop the announcement going out.
            with contextlib.suppress(ValueError):
                colour = discord.Colour(int(ann.embed_color.lstrip("#"), 16))

        embed = discord.Embed(
            title=ann.title or ann.name,
            description=ann.body,
            colour=colour,
        )
        embed.set_footer(text="DWS Alliance Manager")
        # The mention must sit in `content`; mentions inside an embed do not ping.
        return (prefix or None), embed

    async def send_announcement(self, ann: Announcement) -> None:
        channel = self.get_channel(ann.channel_id) or await self.fetch_channel(ann.channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            raise RuntimeError(f"channel {ann.channel_id} is not messageable")

        content, embed = self.render(ann)
        allowed = discord.AllowedMentions(everyone=True, roles=True, users=True)
        await channel.send(content=content, embed=embed, allowed_mentions=allowed)
        log.info(
            "sent announcement %s (%s) to #%s",
            ann.id, ann.name, getattr(channel, "name", "?"),
        )


bot = AllianceBot()
