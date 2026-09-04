"""What the backoffice reports as an announcement's next fire time.

Event-linked announcements are the awkward case: they never hold a standing
APScheduler job, so the job list alone cannot answer the question.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from dwsbot.api.routers import announcements as mod
from dwsbot.models import ScheduleKind

SEOUL = ZoneInfo("Asia/Seoul")


@pytest.fixture(autouse=True)
def no_scheduler_jobs(monkeypatch):
    """The planner has not materialised anything yet — the normal state."""
    monkeypatch.setattr(mod, "scheduler", SimpleNamespace(jobs=[]))


@pytest.fixture(autouse=True)
def rule_only_resolver(monkeypatch):
    """Stub the override lookup: these tests are about the lead arithmetic."""
    from dwsbot.occurrences import Occurrence
    from dwsbot.recurrence import next_occurrences

    async def fake(session, defn, *, now=None, count=5, horizon_days=90):
        return [
            Occurrence(starts_at=d, original_starts_at=d)
            for d in next_occurrences(defn, now=now, count=count)
        ]

    monkeypatch.setattr(mod, "resolve_occurrences", fake)


def make_event(**over):
    base = dict(
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


def make_ann(**over):
    base = dict(
        id=5, name="Frankenstein Round 1", enabled=True,
        channel_id=1498289269121355867, kind=ScheduleKind.EVENT,
        cron_expr=None, interval_minutes=None, run_at=None,
        timezone="Asia/Seoul", title=None, body="rally up",
        use_embed=True, embed_color=None, mention=None,
        event_id=1, lead_minutes=30,
        last_fired_at=None, last_error=None, fire_count=0,
        created_by_id=None, updated_by_id=None,
        created_by_name=None, updated_by_name=None,
        event=make_event(),
    )
    base.update(over)
    return SimpleNamespace(**base)


async def test_event_announcement_reports_the_next_occurrence_minus_lead():
    """Regression: this used to read "Not scheduled" until 90 minutes before."""
    out = await mod._with_next_run(None, make_ann())

    assert out.next_run_at is not None, "a configured event announcement must show a time"
    # Occurrences land at 22:00; a 30 minute lead means 21:30.
    assert out.next_run_at.astimezone(SEOUL).hour == 21
    assert out.next_run_at.astimezone(SEOUL).minute == 30
    assert out.next_run_at > datetime.now(SEOUL)


async def test_zero_lead_fires_exactly_at_the_occurrence():
    out = await mod._with_next_run(None, make_ann(lead_minutes=0))
    assert out.next_run_at.astimezone(SEOUL).hour == 22
    assert out.next_run_at.astimezone(SEOUL).minute == 0


async def test_a_longer_lead_moves_it_earlier():
    at30 = (await mod._with_next_run(None, make_ann(lead_minutes=30))).next_run_at
    at90 = (await mod._with_next_run(None, make_ann(lead_minutes=90))).next_run_at
    assert at90 == at30 - timedelta(minutes=60)


async def test_disabled_event_reports_nothing():
    out = await mod._with_next_run(None, make_ann(event=make_event(enabled=False)))
    assert out.next_run_at is None


async def test_event_with_no_upcoming_occurrence_reports_nothing():
    past_only = make_event(schedule_type="fixed", fixed_dates=["2020-01-01"])
    out = await mod._with_next_run(None, make_ann(event=past_only))
    assert out.next_run_at is None


async def test_unlinked_announcement_is_unaffected():
    ann = make_ann(kind=ScheduleKind.CRON, cron_expr="0 9 * * *", event=None)
    out = await mod._with_next_run(None, ann)
    assert out.next_run_at is None


async def test_both_times_are_reported_and_differ_by_the_lead():
    """The card shows the post time and the event time; the gap is the lead."""
    out = await mod._with_next_run(None, make_ann(lead_minutes=30))

    assert out.event_starts_at is not None
    assert out.next_run_at is not None
    assert out.event_starts_at - out.next_run_at == timedelta(minutes=30)
    # The event is at 22:00; the post goes out at 21:30.
    assert out.event_starts_at.astimezone(SEOUL).hour == 22
    assert out.next_run_at.astimezone(SEOUL).hour == 21


async def test_non_event_announcements_have_no_event_time():
    ann = make_ann(kind=ScheduleKind.CRON, cron_expr="0 9 * * *", event=None)
    out = await mod._with_next_run(None, ann)
    assert out.event_starts_at is None
