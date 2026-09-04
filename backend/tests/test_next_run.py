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
        event=make_event(),
    )
    base.update(over)
    return SimpleNamespace(**base)


def test_event_announcement_reports_the_next_occurrence_minus_lead():
    """Regression: this used to read "Not scheduled" until 90 minutes before."""
    out = mod._with_next_run(make_ann())

    assert out.next_run_at is not None, "a configured event announcement must show a time"
    # Occurrences land at 22:00; a 30 minute lead means 21:30.
    assert out.next_run_at.astimezone(SEOUL).hour == 21
    assert out.next_run_at.astimezone(SEOUL).minute == 30
    assert out.next_run_at > datetime.now(SEOUL)


def test_zero_lead_fires_exactly_at_the_occurrence():
    out = mod._with_next_run(make_ann(lead_minutes=0))
    assert out.next_run_at.astimezone(SEOUL).hour == 22
    assert out.next_run_at.astimezone(SEOUL).minute == 0


def test_a_longer_lead_moves_it_earlier():
    at30 = mod._with_next_run(make_ann(lead_minutes=30)).next_run_at
    at90 = mod._with_next_run(make_ann(lead_minutes=90)).next_run_at
    assert at90 == at30 - timedelta(minutes=60)


def test_disabled_event_reports_nothing():
    out = mod._with_next_run(make_ann(event=make_event(enabled=False)))
    assert out.next_run_at is None


def test_event_with_no_upcoming_occurrence_reports_nothing():
    past_only = make_event(schedule_type="fixed", fixed_dates=["2020-01-01"])
    out = mod._with_next_run(make_ann(event=past_only))
    assert out.next_run_at is None


def test_unlinked_announcement_is_unaffected():
    out = mod._with_next_run(make_ann(kind=ScheduleKind.CRON, cron_expr="0 9 * * *", event=None))
    assert out.next_run_at is None
