"""Occurrences after a single date has been moved or skipped.

The rule stays untouched: postponing one night must not shift the rotation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from dwsbot.occurrences import resolve_occurrences

SEOUL = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")


class FakeSession:
    """Stands in for the one query resolve_occurrences makes."""

    def __init__(self, rows=()):
        self._rows = list(rows)

    async def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: self._rows)


def frankenstein(**over):
    """The real event: every 3 days at 22:00 KST, from 5 Sep 2026."""
    base = dict(
        id=1,
        enabled=True,
        schedule_type="rotation",
        weekdays=None,
        rotation_days=3,
        reference_date=datetime(2026, 9, 5, tzinfo=SEOUL),
        fixed_dates=None,
        start_time="22:00",
        timezone="Asia/Seoul",
    )
    base.update(over)
    return SimpleNamespace(**base)


def override(original, *, moved_to=None, cancelled=False, note=None, id=1):
    """An event_instances row as the database would return it, in UTC."""
    return SimpleNamespace(
        id=id,
        original_starts_at=original.astimezone(UTC),
        starts_at=(moved_to or original).astimezone(UTC),
        cancelled=cancelled,
        override_note=note,
    )


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=SEOUL)


async def test_without_overrides_it_matches_the_rule():
    got = await resolve_occurrences(FakeSession(), frankenstein(), now=NOW, count=3)

    assert [o.starts_at for o in got] == [
        datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL),
        datetime(2026, 9, 8, 22, 0, tzinfo=SEOUL),
        datetime(2026, 9, 11, 22, 0, tzinfo=SEOUL),
    ]
    assert not any(o.moved for o in got)


async def test_postponing_one_night_leaves_the_rotation_alone():
    """The reported case: 5 Sep 22:00 KST pushed to 00:30 the next morning."""
    original = datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL)
    moved_to = datetime(2026, 9, 6, 0, 30, tzinfo=SEOUL)

    got = await resolve_occurrences(
        FakeSession([override(original, moved_to=moved_to, note="clashes with SvS")]),
        frankenstein(), now=NOW, count=3,
    )

    assert got[0].starts_at == moved_to
    assert got[0].original_starts_at == original
    assert got[0].moved is True
    assert got[0].note == "clashes with SvS"

    # Everything after it is untouched — the rule did not move.
    assert [o.starts_at for o in got[1:]] == [
        datetime(2026, 9, 8, 22, 0, tzinfo=SEOUL),
        datetime(2026, 9, 11, 22, 0, tzinfo=SEOUL),
    ]
    assert not any(o.moved for o in got[1:])


async def test_a_skipped_date_disappears_and_the_rest_remain():
    got = await resolve_occurrences(
        FakeSession([override(datetime(2026, 9, 8, 22, 0, tzinfo=SEOUL), cancelled=True)]),
        frankenstein(), now=NOW, count=3,
    )

    assert [o.starts_at for o in got] == [
        datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL),
        datetime(2026, 9, 11, 22, 0, tzinfo=SEOUL),
        datetime(2026, 9, 14, 22, 0, tzinfo=SEOUL),
    ]


async def test_moving_a_date_later_reorders_correctly():
    """Pushed past the following occurrence, it must sort into its new place."""
    original = datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL)
    moved_to = datetime(2026, 9, 9, 22, 0, tzinfo=SEOUL)   # after the 8th

    got = await resolve_occurrences(
        FakeSession([override(original, moved_to=moved_to)]),
        frankenstein(), now=NOW, count=3,
    )

    assert [o.starts_at for o in got] == [
        datetime(2026, 9, 8, 22, 0, tzinfo=SEOUL),
        moved_to,
        datetime(2026, 9, 11, 22, 0, tzinfo=SEOUL),
    ]


async def test_an_occurrence_moved_past_its_own_slot_survives():
    """Its rule date has gone, but the event has not happened yet.

    Tonight's 22:00 is pushed to 00:30; by 23:00 the rule no longer produces
    the original date, so a naive implementation loses the event entirely
    half an hour before it starts.
    """
    original = datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL)
    moved_to = datetime(2026, 9, 6, 0, 30, tzinfo=SEOUL)
    late = datetime(2026, 9, 5, 23, 0, tzinfo=SEOUL)      # after the old slot

    got = await resolve_occurrences(
        FakeSession([override(original, moved_to=moved_to)]),
        frankenstein(), now=late, count=2,
    )

    assert got[0].starts_at == moved_to
    assert got[0].moved is True


async def test_a_cancelled_date_whose_slot_has_passed_stays_gone():
    original = datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL)
    late = datetime(2026, 9, 5, 23, 0, tzinfo=SEOUL)

    got = await resolve_occurrences(
        FakeSession([override(original, cancelled=True)]),
        frankenstein(), now=late, count=2,
    )

    assert got[0].starts_at == datetime(2026, 9, 8, 22, 0, tzinfo=SEOUL)


async def test_overrides_for_other_dates_do_not_leak():
    """An override is keyed to one specific date, not to the event."""
    got = await resolve_occurrences(
        FakeSession([override(datetime(2026, 9, 11, 22, 0, tzinfo=SEOUL),
                              moved_to=datetime(2026, 9, 12, 9, 0, tzinfo=SEOUL))]),
        frankenstein(), now=NOW, count=2,
    )

    assert [o.starts_at for o in got] == [
        datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL),
        datetime(2026, 9, 8, 22, 0, tzinfo=SEOUL),
    ]
    assert not any(o.moved for o in got)


@pytest.mark.parametrize("count", [1, 2, 5])
async def test_count_is_respected_even_with_skips(count):
    got = await resolve_occurrences(
        FakeSession([override(datetime(2026, 9, 8, 22, 0, tzinfo=SEOUL), cancelled=True)]),
        frankenstein(), now=NOW, count=count,
    )
    assert len(got) == count


async def test_moved_flag_is_false_when_the_time_is_unchanged():
    """An instance created for a signup sheet is not a reschedule."""
    original = datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL)
    got = await resolve_occurrences(
        FakeSession([override(original)]), frankenstein(), now=NOW, count=1
    )
    assert got[0].moved is False


async def test_lead_time_follows_the_moved_date():
    """What the announcement scheduler ultimately depends on."""
    original = datetime(2026, 9, 5, 22, 0, tzinfo=SEOUL)
    moved_to = datetime(2026, 9, 6, 0, 30, tzinfo=SEOUL)

    got = await resolve_occurrences(
        FakeSession([override(original, moved_to=moved_to)]),
        frankenstein(), now=NOW, count=1,
    )
    posts_at = got[0].starts_at - timedelta(minutes=30)
    assert posts_at == datetime(2026, 9, 6, 0, 0, tzinfo=SEOUL)
