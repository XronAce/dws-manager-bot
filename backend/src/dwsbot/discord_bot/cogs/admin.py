"""Officer-only commands for inspecting and testing the schedule."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from ...db import SessionLocal
from ...models import Announcement
from ...permissions import admin_only
from ...scheduler import scheduler


class Admin(commands.Cog):
    group = app_commands.Group(name="admin", description="Alliance bot administration")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @group.command(name="announcements", description="List configured announcements")
    @admin_only()
    async def list_announcements(self, interaction: discord.Interaction) -> None:
        async with SessionLocal() as session:
            rows = (
                await session.scalars(select(Announcement).order_by(Announcement.id))
            ).all()

        if not rows:
            await interaction.response.send_message(
                "Nothing configured yet — use the backoffice.", ephemeral=True
            )
            return

        next_runs = {
            job.id: getattr(job, "next_run_time", None) for job in scheduler.jobs
        }
        lines = []
        for a in rows:
            mark = "🟢" if a.enabled else "⚪"
            nxt = next_runs.get(f"ann:{a.id}")
            when = f"<t:{int(nxt.timestamp())}:R>" if nxt else "—"
            lines.append(f"{mark} `{a.id}` **{a.name}** · {a.kind.value} · next {when}")
            if a.last_error:
                lines.append(f"　　⚠️ {a.last_error[:120]}")

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Announcements",
                description="\n".join(lines)[:4000],
                colour=discord.Colour.blurple(),
            ),
            ephemeral=True,
        )

    @group.command(name="test", description="Send one announcement right now")
    @app_commands.describe(announcement_id="ID from /admin announcements")
    @admin_only()
    async def test(self, interaction: discord.Interaction, announcement_id: int) -> None:
        await interaction.response.defer(ephemeral=True)
        async with SessionLocal() as session:
            ann = await session.get(Announcement, announcement_id)
            if ann is None:
                await interaction.followup.send("No such announcement.", ephemeral=True)
                return
            try:
                await self.bot.send_announcement(ann)
            except Exception as exc:
                await interaction.followup.send(f"Failed: `{exc}`", ephemeral=True)
                return
        await interaction.followup.send(f"Sent **{ann.name}**.", ephemeral=True)

    @group.command(name="reload", description="Rebuild the schedule from the database")
    @admin_only()
    async def reload(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        count = await scheduler.reload()
        await interaction.followup.send(f"Reloaded — {count} active.", ephemeral=True)

    @group.command(name="channels", description="List channel IDs for the backoffice")
    @admin_only()
    async def channels(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Run this in the server.", ephemeral=True)
            return
        lines = [
            f"`{c.id}` #{c.name}"
            for c in guild.text_channels
            if c.permissions_for(guild.me).send_messages
        ]
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Channels the bot can post to",
                description="\n".join(lines)[:4000] or "None.",
                colour=discord.Colour.blurple(),
            ),
            ephemeral=True,
        )

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            msg = str(error) or "You are not allowed to run this."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return
        raise error


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
