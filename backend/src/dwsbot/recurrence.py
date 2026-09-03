"""Occurrence math for recurring in-game events.

Kept free of database and Discord imports so the rotation rules can be unit
tested directly.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def _parse_hhmm(value: str | None) -> time:
    if not value:
        return time(0, 0)
    hh, _, mm = value.partition(":")
    return time(int(hh), int(mm or 0))


def occurrence_dates(
    *,
    schedule_type: str,
    after: date,
    horizon_days: int,
    weekdays: list[int] | None = None,
    rotation_days: int | None = None,
    reference_date: date | None = None,
    fixed_dates: list[str] | None = None,
) -> list[date]:
    """Dates on which the event happens, within `after` .. `after + horizon_days`.

    `weekly`   - every listed weekday (0=Monday .. 6=Sunday)
    `rotation` - every `rotation_days` days counted from `reference_date`
    `fixed`    - an explicit list of ISO dates
    """
    window = [after + timedelta(days=i) for i in range(horizon_days + 1)]

    if schedule_type == "weekly":
        wanted = set(weekdays or [])
        return [d for d in window if d.weekday() in wanted]

    if schedule_type == "rotation":
        if not rotation_days or rotation_days < 1 or reference_date is None:
            return []
        # A date is an occurrence when its offset from the reference lands on
        # the rotation boundary. Python's % is non-negative, so dates before
        # the reference date work without a special case.
        return [d for d in window if (d - reference_date).days % rotation_days == 0]

    if schedule_type == "fixed":
        wanted = {date.fromisoformat(s) for s in (fixed_dates or [])}
        return [d for d in window if d in wanted]

    return []


def next_occurrences(
    definition,
    *,
    now: datetime | None = None,
    count: int = 5,
    horizon_days: int = 60,
) -> list[datetime]:
    """The next `count` timezone-aware start times for an EventDefinition."""
    tz = ZoneInfo(definition.timezone or "UTC")
    now = (now or datetime.now(tz)).astimezone(tz)
    start = _parse_hhmm(definition.start_time)

    ref = definition.reference_date
    if isinstance(ref, datetime):
        ref = ref.astimezone(tz).date()

    days = occurrence_dates(
        schedule_type=definition.schedule_type,
        after=now.date(),
        horizon_days=horizon_days,
        weekdays=definition.weekdays,
        rotation_days=definition.rotation_days,
        reference_date=ref,
        fixed_dates=definition.fixed_dates,
    )

    out: list[datetime] = []
    for d in days:
        dt = datetime.combine(d, start, tzinfo=tz)
        if dt > now:
            out.append(dt)
        if len(out) >= count:
            break
    return out
