"""Alliance roster: link Discord accounts to in-game identities."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from ...db import SessionLocal
from ...models import Member
from ...permissions import admin_only


class Roster(commands.Cog):
    group = app_commands.Group(name="roster", description="Alliance roster")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @group.command(name="register", description="Link your Discord account to your in-game name")
    @app_commands.describe(
        game_name="Your exact in-game name",
        rank="Alliance rank 1-5 (R5 = leader)",
        power="Your current power, digits only",
        timezone="IANA timezone, e.g. Asia/Seoul",
    )
    async def register(
        self,
        interaction: discord.Interaction,
        game_name: str,
        rank: app_commands.Range[int, 1, 5] | None = None,
        power: int | None = None,
        timezone: str | None = None,
    ) -> None:
        async with SessionLocal() as session:
            member = await session.scalar(
                select(Member).where(Member.discord_id == interaction.user.id)
            )
            if member is None:
                member = Member(discord_id=interaction.user.id)
                session.add(member)

            member.discord_name = str(interaction.user)
            member.game_name = game_name
            if rank is not None:
                member.rank = rank
            if power is not None:
                member.power = power
            if timezone is not None:
                member.timezone = timezone
            member.active = True
            await session.commit()

        await interaction.response.send_message(
            f"Registered **{game_name}**" + (f" (R{rank})" if rank else "") + ".",
            ephemeral=True,
        )

    @group.command(name="list", description="Show the alliance roster")
    async def list_members(self, interaction: discord.Interaction) -> None:
        async with SessionLocal() as session:
            members = (
                await session.scalars(
                    select(Member)
                    .where(Member.active.is_(True))
                    .order_by(Member.rank.desc().nullslast(), Member.power.desc().nullslast())
                )
            ).all()

        if not members:
            await interaction.response.send_message(
                "No one has registered yet — try `/roster register`.", ephemeral=True
            )
            return

        lines = [
            f"`R{m.rank or '?'}` **{m.game_name or m.discord_name}**"
            + (f" — {m.power:,}" if m.power else "")
            for m in members[:50]
        ]
        embed = discord.Embed(
            title=f"Alliance roster ({len(members)})",
            description="\n".join(lines),
            colour=discord.Colour.blurple(),
        )
        if len(members) > 50:
            embed.set_footer(text=f"showing 50 of {len(members)}")
        await interaction.response.send_message(embed=embed)

    @group.command(name="remove", description="Remove someone from the roster (officers only)")
    @admin_only()
    async def remove(self, interaction: discord.Interaction, user: discord.User) -> None:
        async with SessionLocal() as session:
            member = await session.scalar(select(Member).where(Member.discord_id == user.id))
            if member is None:
                await interaction.response.send_message("Not on the roster.", ephemeral=True)
                return
            member.active = False
            await session.commit()
        await interaction.response.send_message(f"Removed {user.mention}.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Roster(bot))
