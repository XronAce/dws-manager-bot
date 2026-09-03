"""Event schedule and signups."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...db import SessionLocal
from ...models import EventDefinition, EventInstance, Member, Signup, SignupStatus
from ...recurrence import next_occurrences

STATUS_STYLE = {
    SignupStatus.YES: ("Going", discord.ButtonStyle.success),
    SignupStatus.MAYBE: ("Maybe", discord.ButtonStyle.secondary),
    SignupStatus.NO: ("Can't make it", discord.ButtonStyle.danger),
}


class SignupView(discord.ui.View):
    """Persistent signup buttons.

    `timeout=None` plus stable custom_ids let the view keep working after a bot
    restart, once re-registered in setup_hook via add_view.
    """

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Going", style=discord.ButtonStyle.success, custom_id="signup:yes")
    async def yes(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._record(interaction, SignupStatus.YES)

    @discord.ui.button(label="Maybe", style=discord.ButtonStyle.secondary, custom_id="signup:maybe")
    async def maybe(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._record(interaction, SignupStatus.MAYBE)

    @discord.ui.button(
        label="Can't make it", style=discord.ButtonStyle.danger, custom_id="signup:no"
    )
    async def no(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._record(interaction, SignupStatus.NO)

    async def _record(self, interaction: discord.Interaction, status: SignupStatus) -> None:
        async with SessionLocal() as session:
            instance = await session.scalar(
                select(EventInstance)
                .where(EventInstance.message_id == interaction.message.id)
                .options(selectinload(EventInstance.definition))
            )
            if instance is None:
                await interaction.response.send_message(
                    "This event is no longer tracked.", ephemeral=True
                )
                return

            member = await session.scalar(
                select(Member).where(Member.discord_id == interaction.user.id)
            )
            if member is None:
                member = Member(
                    discord_id=interaction.user.id, discord_name=str(interaction.user)
                )
                session.add(member)
                await session.flush()

            signup = await session.scalar(
                select(Signup).where(
                    Signup.instance_id == instance.id, Signup.member_id == member.id
                )
            )
            if signup is None:
                signup = Signup(instance_id=instance.id, member_id=member.id, status=status)
                session.add(signup)
            else:
                signup.status = status
            await session.commit()

            embed = await build_event_embed(session, instance.id)

        await interaction.response.edit_message(embed=embed, view=self)


async def build_event_embed(session, instance_id: int) -> discord.Embed:
    instance = await session.scalar(
        select(EventInstance)
        .where(EventInstance.id == instance_id)
        .options(
            selectinload(EventInstance.definition),
            selectinload(EventInstance.signups).selectinload(Signup.member),
        )
    )
    defn = instance.definition
    embed = discord.Embed(
        title=defn.name,
        description=defn.description or None,
        colour=discord.Colour.blurple(),
    )
    # Discord renders <t:...:F> in each viewer's own timezone, which matters for
    # an alliance spread across several of them.
    ts = int(instance.starts_at.timestamp())
    embed.add_field(name="Starts", value=f"<t:{ts}:F>\n<t:{ts}:R>", inline=False)

    for status in (SignupStatus.YES, SignupStatus.MAYBE, SignupStatus.NO):
        people = [s.member for s in instance.signups if s.status is status]
        label, _ = STATUS_STYLE[status]
        value = "\n".join(m.game_name or m.discord_name or "?" for m in people) or "—"
        embed.add_field(name=f"{label} ({len(people)})", value=value, inline=True)
    return embed


class Events(commands.Cog):
    group = app_commands.Group(name="events", description="Alliance events")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @group.command(name="next", description="Show upcoming alliance events")
    async def next_events(self, interaction: discord.Interaction) -> None:
        async with SessionLocal() as session:
            defs = (
                await session.scalars(
                    select(EventDefinition).where(EventDefinition.enabled.is_(True))
                )
            ).all()

        upcoming: list[tuple] = []
        for defn in defs:
            for dt in next_occurrences(defn, count=2):
                upcoming.append((dt, defn))
        upcoming.sort(key=lambda pair: pair[0])

        if not upcoming:
            await interaction.response.send_message(
                "No events are configured yet.", ephemeral=True
            )
            return

        lines = [
            f"<t:{int(dt.timestamp())}:F> — **{defn.name}** (<t:{int(dt.timestamp())}:R>)"
            for dt, defn in upcoming[:10]
        ]
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Upcoming events",
                description="\n".join(lines),
                colour=discord.Colour.blurple(),
            )
        )

    @group.command(name="post", description="Post a signup sheet for the next occurrence")
    @app_commands.describe(key="Event key, as configured in the backoffice")
    async def post(self, interaction: discord.Interaction, key: str) -> None:
        await interaction.response.defer()
        async with SessionLocal() as session:
            defn = await session.scalar(
                select(EventDefinition).where(EventDefinition.key == key)
            )
            if defn is None:
                await interaction.followup.send(f"No event with key `{key}`.", ephemeral=True)
                return

            occurrences = next_occurrences(defn, count=1)
            if not occurrences:
                await interaction.followup.send(
                    "That event has no upcoming occurrence.", ephemeral=True
                )
                return

            starts_at = occurrences[0]
            instance = await session.scalar(
                select(EventInstance).where(
                    EventInstance.definition_id == defn.id,
                    EventInstance.starts_at == starts_at,
                )
            )
            if instance is None:
                instance = EventInstance(definition_id=defn.id, starts_at=starts_at)
                session.add(instance)
                await session.flush()

            embed = await build_event_embed(session, instance.id)
            message = await interaction.followup.send(embed=embed, view=SignupView(), wait=True)

            instance.channel_id = message.channel.id
            instance.message_id = message.id
            await session.commit()


async def setup(bot: commands.Bot) -> None:
    bot.add_view(SignupView())     # re-arm buttons on already-posted messages
    await bot.add_cog(Events(bot))
