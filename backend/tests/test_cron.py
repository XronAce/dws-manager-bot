"""Cron expressions must mean what crontab says they mean.

APScheduler numbers day-of-week 0 = Monday; crontab uses 0 = Sunday. Passing a
crontab string straight to from_crontab therefore shifts every weekday by one,
silently. These pin the translation that prevents it.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from croniter import croniter

from dwsbot.cron import cron_trigger, describe, translate_day_of_week

ST = ZoneInfo("Etc/GMT+2")
NOW = datetime(2026, 9, 1, 0, 0, tzinfo=ST)   # a Tuesday


@pytest.mark.parametrize(
    "field,expected",
    [
        ("*", "*"),
        ("0", "sun"),
        ("5", "fri"),
        ("7", "sun"),          # crontab allows 7 for Sunday
        ("1-5", "mon-fri"),
        ("0,6", "sun,sat"),
        ("fri", "fri"),        # already unambiguous
        ("MON", "mon"),
    ],
)
def test_day_of_week_translation(field, expected):
    assert translate_day_of_week(field) == expected


@pytest.mark.parametrize(
    "expr,weekday",
    [
        ("0 12 * * 0", "Sunday"),
        ("0 12 * * 1", "Monday"),
        ("0 12 * * 5", "Friday"),     # the reported case
        ("0 12 * * 6", "Saturday"),
    ],
)
def test_every_weekday_number_lands_on_the_crontab_day(expr, weekday):
    fire = cron_trigger(expr, ST).get_next_fire_time(None, NOW)
    assert fire.strftime("%A") == weekday


def test_it_agrees_with_croniter_which_validates_the_input():
    """The validator and the scheduler must not disagree about the same string."""
    for expr in ("0 12 * * 5", "0 9 * * 1", "30 20 * * 0", "0 9 * * 1-5"):
        ours = cron_trigger(expr, ST).get_next_fire_time(None, NOW)
        theirs = croniter(expr, NOW).get_next(datetime)
        assert ours == theirs, expr


def test_the_reported_announcement_fires_on_friday():
    """'0 12 * * 5' in server time, as the alliance actually configured it."""
    fires = []
    t = cron_trigger("0 12 * * 5", ST)
    when = NOW
    for _ in range(3):
        when = t.get_next_fire_time(fires[-1] if fires else None, when)
        fires.append(when)

    assert [f.strftime("%A") for f in fires] == ["Friday"] * 3
    assert [f.strftime("%H:%M") for f in fires] == ["12:00"] * 3
    # Three *different* Fridays, a week apart. Without this the assertions
    # above pass on the same date repeated three times.
    assert len({f.date() for f in fires}) == 3
    assert (fires[1] - fires[0]).days == 7
    assert (fires[2] - fires[1]).days == 7


def test_a_malformed_expression_is_rejected_not_guessed():
    with pytest.raises(ValueError, match="needs 5 fields"):
        cron_trigger("0 12 * *", ST)


@pytest.mark.parametrize(
    "expr,text",
    [
        ("0 9 * * *", "Every day at 09:00"),
        ("0 12 * * 5", "Every Friday at 12:00"),
        ("0 9 * * 1-5", "Every weekday at 09:00"),
        ("30 20 * * 0,6", "Every weekend day at 20:30"),
        ("0 12 1 * *", "On day 1 of every month at 12:00"),
    ],
)
def test_plain_language_description(expr, text):
    assert describe(expr) == text


def test_description_falls_back_rather_than_guessing():
    assert describe("*/7 3 * 2 1#2") == "*/7 3 * 2 1#2"
