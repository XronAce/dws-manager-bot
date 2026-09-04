"""Building an APScheduler trigger from a standard cron expression.

APScheduler's `from_crontab` looks like it accepts crontab syntax, but its
day-of-week field is numbered 0 = Monday, while crontab — and croniter, which
this project validates with — uses 0 = Sunday. Passing "0 12 * * 5" through it
therefore schedules Saturday when the author meant Friday, silently and with
no error anywhere.

Translating the numbers to APScheduler's names removes the ambiguity: "fri"
means Friday in both systems.
"""
from __future__ import annotations

from apscheduler.triggers.cron import CronTrigger

#: Crontab numbering. 7 is also Sunday, which crontab accepts.
CRON_DAY_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")

DAY_LABELS = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
    "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
}


def translate_day_of_week(field: str) -> str:
    """Rewrite a crontab day-of-week field using names APScheduler agrees with.

    Handles the forms crontab allows: `*`, a number, a range, a list, a step,
    and names that are already unambiguous.
    """
    if field.strip() in {"*", "?"}:
        return "*"

    def one(token: str) -> str:
        token = token.strip().lower()
        if token.isdigit():
            # 0 and 7 are both Sunday in crontab.
            return CRON_DAY_NAMES[int(token) % 7]
        return token

    parts = []
    for chunk in field.split(","):
        step = ""
        if "/" in chunk:
            chunk, _, step = chunk.partition("/")
            step = f"/{step}"
        if "-" in chunk and not chunk.startswith("-"):
            lo, _, hi = chunk.partition("-")
            parts.append(f"{one(lo)}-{one(hi)}{step}")
        else:
            parts.append(f"{one(chunk)}{step}")
    return ",".join(parts)


def cron_trigger(expression: str, timezone) -> CronTrigger:
    """A CronTrigger that reads the expression the way crontab would."""
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError(
            f"a cron expression needs 5 fields, got {len(fields)}: {expression!r}"
        )
    minute, hour, day, month, day_of_week = fields
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=translate_day_of_week(day_of_week),
        timezone=timezone,
    )


def describe(expression: str) -> str:
    """A plain-language reading of the common shapes, for the UI to echo back.

    Falls back to the raw expression for anything unusual rather than guessing
    and being confidently wrong.
    """
    try:
        minute, hour, day, month, dow = expression.split()
    except ValueError:
        return expression

    if not (minute.isdigit() and hour.isdigit()):
        return expression
    at = f"{int(hour):02d}:{int(minute):02d}"

    if day == "*" and month == "*":
        if dow == "*":
            return f"Every day at {at}"
        names = translate_day_of_week(dow)
        parts = [p for p in names.split(",") if p]
        if names == "mon-fri":
            return f"Every weekday at {at}"
        # Order follows whatever was typed, so compare as a set.
        if set(parts) == {"sat", "sun"}:
            return f"Every weekend day at {at}"
        labels = [DAY_LABELS.get(n, n) for n in names.split(",") if "-" not in n]
        if labels:
            joined = labels[0] if len(labels) == 1 else (
                ", ".join(labels[:-1]) + " and " + labels[-1]
            )
            return f"Every {joined} at {at}"
    if dow == "*" and month == "*" and day.isdigit():
        return f"On day {int(day)} of every month at {at}"
    return expression
