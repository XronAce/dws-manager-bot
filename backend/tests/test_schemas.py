"""Validation guards that keep unschedulable rows out of the database."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from dwsbot.models import ScheduleKind
from dwsbot.schemas import AnnouncementCreate, EventCreate

BASE = dict(name="Daily reset", channel_id=123456789012345678, body="Reset is here")


def test_cron_announcement_is_accepted():
    ann = AnnouncementCreate(**BASE, kind=ScheduleKind.CRON, cron_expr="0 9 * * *")
    assert ann.cron_expr == "0 9 * * *"


def test_cron_kind_requires_an_expression():
    with pytest.raises(ValidationError, match="cron_expr is required"):
        AnnouncementCreate(**BASE, kind=ScheduleKind.CRON)


def test_malformed_cron_is_rejected_before_it_reaches_the_scheduler():
    with pytest.raises(ValidationError, match="invalid cron expression"):
        AnnouncementCreate(**BASE, kind=ScheduleKind.CRON, cron_expr="99 99 * * *")


def test_interval_kind_requires_minutes():
    with pytest.raises(ValidationError, match="interval_minutes is required"):
        AnnouncementCreate(**BASE, kind=ScheduleKind.INTERVAL)


def test_event_kind_requires_an_event():
    with pytest.raises(ValidationError, match="event_id is required"):
        AnnouncementCreate(**BASE, kind=ScheduleKind.EVENT)


def test_unknown_timezone_is_rejected():
    with pytest.raises(ValidationError, match="unknown timezone"):
        AnnouncementCreate(
            **BASE, kind=ScheduleKind.CRON, cron_expr="0 9 * * *", timezone="Mars/Olympus"
        )


def test_embed_colour_must_be_a_hex_triplet():
    with pytest.raises(ValidationError):
        AnnouncementCreate(
            **BASE, kind=ScheduleKind.CRON, cron_expr="0 9 * * *", embed_color="red"
        )


def test_weekly_event_requires_weekdays():
    with pytest.raises(ValidationError, match="weekdays is required"):
        EventCreate(key="duel", name="Alliance Duel", schedule_type="weekly")


def test_rotation_event_requires_reference_date():
    with pytest.raises(ValidationError, match="reference_date"):
        EventCreate(key="duel", name="Alliance Duel", schedule_type="rotation", rotation_days=5)


def test_event_key_must_be_url_safe():
    with pytest.raises(ValidationError):
        EventCreate(key="Alliance Duel!", name="x", schedule_type="weekly", weekdays=[0])


def test_weekday_range_is_enforced():
    with pytest.raises(ValidationError, match="0 \\(Monday\\) through 6"):
        EventCreate(key="duel", name="x", schedule_type="weekly", weekdays=[7])
