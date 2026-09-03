"""Rotation and weekday maths for event schedules."""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from dwsbot.recurrence import next_occurrences, occurrence_dates

SEOUL = ZoneInfo("Asia/Seoul")


def test_weekly_picks_only_listed_weekdays():
    # 2026-09-07 is a Monday.
    got = occurrence_dates(
        schedule_type="weekly",
        after=date(2026, 9, 7),
        horizon_days=13,
        weekdays=[0, 3],          # Monday, Thursday
    )
    assert got == [
        date(2026, 9, 7), date(2026, 9, 10),
        date(2026, 9, 14), date(2026, 9, 17),
    ]


def test_rotation_counts_from_reference_date():
    got = occurrence_dates(
        schedule_type="rotation",
        after=date(2026, 9, 3),
        horizon_days=12,
        rotation_days=5,
        reference_date=date(2026, 9, 3),
    )
    assert got == [date(2026, 9, 3), date(2026, 9, 8), date(2026, 9, 13)]


def test_rotation_works_before_the_reference_date():
    """A reference date in the future must not break the modulo."""
    got = occurrence_dates(
        schedule_type="rotation",
        after=date(2026, 9, 1),
        horizon_days=6,
        rotation_days=3,
        reference_date=date(2026, 12, 25),
    )
    # Sep 1 -> Dec 25 is 115 days and -115 % 3 == 2, so the rotation
    # boundary falls on Sep 2 and Sep 5 within this window.
    assert got == [date(2026, 9, 2), date(2026, 9, 5)]


def test_fixed_dates_are_filtered_to_the_window():
    got = occurrence_dates(
        schedule_type="fixed",
        after=date(2026, 9, 3),
        horizon_days=5,
        fixed_dates=["2026-09-04", "2026-09-30"],
    )
    assert got == [date(2026, 9, 4)]


def test_unknown_schedule_type_yields_nothing():
    assert occurrence_dates(schedule_type="nonsense", after=date(2026, 9, 3), horizon_days=5) == []


@pytest.mark.parametrize("missing", ["rotation_days", "reference_date"])
def test_incomplete_rotation_yields_nothing(missing):
    kwargs = {"rotation_days": 3, "reference_date": date(2026, 9, 1)}
    kwargs[missing] = None
    assert occurrence_dates(
        schedule_type="rotation", after=date(2026, 9, 3), horizon_days=10, **kwargs
    ) == []


def _defn(**over):
    base = dict(
        schedule_type="weekly",
        weekdays=[0, 3],
        rotation_days=None,
        reference_date=None,
        fixed_dates=None,
        start_time="20:30",
        timezone="Asia/Seoul",
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_next_occurrences_applies_start_time_and_timezone():
    now = datetime(2026, 9, 7, 12, 0, tzinfo=SEOUL)     # Monday noon
    got = next_occurrences(_defn(), now=now, count=2)

    assert got[0] == datetime(2026, 9, 7, 20, 30, tzinfo=SEOUL)
    assert got[1] == datetime(2026, 9, 10, 20, 30, tzinfo=SEOUL)


def test_next_occurrences_skips_todays_slot_once_it_has_passed():
    now = datetime(2026, 9, 7, 21, 0, tzinfo=SEOUL)     # Monday, after 20:30
    got = next_occurrences(_defn(), now=now, count=1)

    assert got[0] == datetime(2026, 9, 10, 20, 30, tzinfo=SEOUL)


def test_next_occurrences_respects_count():
    now = datetime(2026, 9, 7, 0, 0, tzinfo=SEOUL)
    assert len(next_occurrences(_defn(), now=now, count=3)) == 3


def test_missing_start_time_defaults_to_midnight():
    now = datetime(2026, 9, 6, 23, 0, tzinfo=SEOUL)     # Sunday night
    got = next_occurrences(_defn(start_time=None), now=now, count=1)
    assert got[0] == datetime(2026, 9, 7, 0, 0, tzinfo=SEOUL)
