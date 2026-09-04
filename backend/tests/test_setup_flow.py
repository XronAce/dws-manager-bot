"""The guided flow's payload shape.

Its announcement half cannot carry an event_id — the event does not exist yet
— so it must not be validated as a standalone AnnouncementCreate, which
insists on one.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from dwsbot.models import ScheduleKind
from dwsbot.schemas import AnnouncementBase, AnnouncementCreate

GUIDED = dict(
    name="Frankenstein Round 1",
    channel_id="1500145086481170482",
    kind=ScheduleKind.EVENT,
    lead_minutes=30,
    body="Rally up!",
    timezone="Asia/Seoul",
)


def test_the_guided_half_is_accepted_without_an_event_id():
    ann = AnnouncementBase(**GUIDED)

    assert ann.event_id is None
    assert ann.kind == ScheduleKind.EVENT
    # The snowflake still survives the round trip.
    assert ann.channel_id == 1500145086481170482


def test_the_standalone_form_still_demands_one():
    """Relaxing the guided path must not relax the direct one."""
    with pytest.raises(ValidationError, match="event_id is required"):
        AnnouncementCreate(**GUIDED)


def test_the_guided_half_still_validates_what_it_can():
    with pytest.raises(ValidationError, match="unknown timezone"):
        AnnouncementBase(**{**GUIDED, "timezone": "Mars/Olympus"})


def test_a_body_is_still_required():
    with pytest.raises(ValidationError):
        AnnouncementBase(**{**GUIDED, "body": ""})
