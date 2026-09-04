"""Backoffice CRUD for scheduled announcements."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ...models import Announcement, ScheduleKind
from ...occurrences import resolve_occurrences
from ...scheduler import scheduler
from ...schemas import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from ..deps import AdminUser, DbSession, write_audit

router = APIRouter(prefix="/announcements", tags=["announcements"])


async def _with_next_run(session, ann: Announcement) -> AnnouncementOut:
    """Attach the next fire time, however this announcement is driven."""
    out = AnnouncementOut.model_validate(ann)

    for job in scheduler.jobs:
        if job.id != f"ann:{ann.id}" and not job.id.startswith(f"ann:{ann.id}:"):
            continue
        # APScheduler only sets next_run_time once a job belongs to a *running*
        # scheduler; jobs queued before start-up have no such attribute.
        nxt = getattr(job, "next_run_time", None)
        if nxt and (out.next_run_at is None or nxt < out.next_run_at):
            out.next_run_at = nxt

    # An event-linked announcement holds no standing job: the planner only
    # materialises one shortly before each occurrence. Reading the job list
    # alone therefore showed "Not scheduled" for a correctly configured
    # announcement almost all of the time, so derive it from the event.
    if (
        out.next_run_at is None
        and ann.kind == ScheduleKind.EVENT
        and ann.event
        and ann.event.enabled
    ):
        upcoming = await resolve_occurrences(session, ann.event, count=1)
        if upcoming:
            out.event_starts_at = upcoming[0].starts_at
            out.next_run_at = upcoming[0].starts_at - timedelta(minutes=ann.lead_minutes)
    return out


# `ann.event` is read above, and an async session cannot lazy-load mid-request,
# so every path that builds an AnnouncementOut eager-loads the relationship.
_WITH_EVENT = (selectinload(Announcement.event),)


async def _reload_one(session, announcement_id: int) -> Announcement | None:
    """Re-read a row with its event attached, for the response."""
    return await session.scalar(
        select(Announcement).where(Announcement.id == announcement_id).options(*_WITH_EVENT)
    )


@router.get("", response_model=list[AnnouncementOut])
async def list_announcements(session: DbSession, _: AdminUser):
    rows = (
        await session.scalars(
            select(Announcement).order_by(Announcement.id).options(*_WITH_EVENT)
        )
    ).all()
    return [await _with_next_run(session, r) for r in rows]


@router.post("", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED)
async def create_announcement(payload: AnnouncementCreate, session: DbSession, user: AdminUser):
    ann = Announcement(**payload.model_dump())
    session.add(ann)
    await session.flush()
    await write_audit(session, user, "announcement.create", "announcement", ann.id,
                      {"name": ann.name})
    await session.commit()
    await scheduler.reload()
    return await _with_next_run(session, await _reload_one(session, ann.id))


@router.get("/{announcement_id}", response_model=AnnouncementOut)
async def get_announcement(announcement_id: int, session: DbSession, _: AdminUser):
    ann = await _reload_one(session, announcement_id)
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such announcement")
    return await _with_next_run(session, ann)


@router.put("/{announcement_id}", response_model=AnnouncementOut)
async def update_announcement(
    announcement_id: int, payload: AnnouncementUpdate, session: DbSession, user: AdminUser
):
    ann = await session.get(Announcement, announcement_id)
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such announcement")
    for field, value in payload.model_dump().items():
        setattr(ann, field, value)
    await write_audit(session, user, "announcement.update", "announcement", ann.id,
                      {"name": ann.name})
    await session.commit()
    await scheduler.reload()
    return await _with_next_run(session, await _reload_one(session, ann.id))


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(announcement_id: int, session: DbSession, user: AdminUser):
    ann = await session.get(Announcement, announcement_id)
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such announcement")
    await write_audit(session, user, "announcement.delete", "announcement", ann.id,
                      {"name": ann.name})
    await session.delete(ann)
    await session.commit()
    await scheduler.reload()


@router.post("/{announcement_id}/test", summary="Send this announcement immediately")
async def test_announcement(announcement_id: int, session: DbSession, user: AdminUser):
    """Deliver the message now without touching its schedule.

    This is why the API and the bot share one process: the button in the
    backoffice can reach the live gateway connection directly.
    """
    from ...discord_bot.bot import bot

    ann = await _reload_one(session, announcement_id)
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such announcement")
    if not bot.is_ready():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The bot is not connected to Discord yet — try again"
        )

    # Resolve the same occurrence the scheduler would, so a test of a moved
    # date shows the reschedule notice rather than a message members will
    # never actually see.
    occurrence = None
    if ann.kind == ScheduleKind.EVENT and ann.event and ann.event.enabled:
        upcoming = await resolve_occurrences(session, ann.event, count=1)
        occurrence = upcoming[0] if upcoming else None

    try:
        await bot.send_announcement(ann, occurrence)
    except Exception as exc:
        # Deliberately 409 and not 502. Cloudflare treats an origin 5xx as its
        # own gateway failure: it replaces the body with "error code: 502" and
        # drops the CORS headers, so the browser reports a bare "Failed to
        # fetch" and this message never reaches the user.
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Discord refused the message: {exc}"
        ) from exc

    await write_audit(session, user, "announcement.test", "announcement", ann.id, None)
    await session.commit()
    return {"sent": True, "name": ann.name}
