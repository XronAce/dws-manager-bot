"""Dark War Survival server time.

The game runs on a single clock that every server event is announced against,
two hours behind UTC. The alliance's anchor for it is 00:00 ST = 11:00 KST,
which is the same statement: KST is UTC+9, so ST is UTC+9-11 = UTC-2.

POSIX inverts the sign in the Etc zones, so "Etc/GMT+2" *is* UTC-02:00. It has
no daylight saving, which matches the game.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

SERVER_TZ_NAME = "Etc/GMT+2"
SERVER_TZ = ZoneInfo(SERVER_TZ_NAME)

#: Shown wherever the zone is offered as a choice.
SERVER_TZ_LABEL = "Game server time (ST)"


def to_server(moment: datetime) -> datetime:
    """Convert any aware datetime into server time."""
    return moment.astimezone(SERVER_TZ)


def format_server(moment: datetime, *, with_date: bool = True) -> str:
    """Render a moment as the alliance would say it: "13:30 ST" or with a date."""
    st = to_server(moment)
    return st.strftime("%d %b %H:%M ST") if with_date else st.strftime("%H:%M ST")
