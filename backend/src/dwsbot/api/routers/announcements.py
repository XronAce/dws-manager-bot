"""Backoffice CRUD for scheduled announcements."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ...models import Announcement
from ...scheduler import scheduler
from ...schemas import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from ..deps import AdminUser, DbSession, write_audit

router = APIRouter(prefix="/announcements", tags=["announcements"])


def _with_next_run(ann: Announcement) -> AnnouncementOut:
    """Attach the live next-fire time from the running scheduler."""
    out = AnnouncementOut.model_validate(ann)
    for job in scheduler.jobs:
        if job.id != f"ann:{ann.id}" and not job.id.startswith(f"ann:{ann.id}:"):
            continue
        # APScheduler only sets next_run_time once a job belongs to a *running*
        # scheduler; jobs queued before start-up have no such attribute.
        nxt = getattr(job, "next_run_time", None)
        if nxt and (out.next_run_at is None or nxt < out.next_run_at):
            out.next_run_at = nxt
    return out


@router.get("", response_model=list[AnnouncementOut])
async def list_announcements(session: DbSession, _: AdminUser):
    rows = (await session.scalars(select(Announcement).order_by(Announcement.id))).all()
    return [_with_next_run(r) for r in rows]


@router.post("", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED)
async def create_announcement(payload: AnnouncementCreate, session: DbSession, user: AdminUser):
    ann = Announcement(**payload.model_dump())
    session.add(ann)
    await session.flush()
    await write_audit(session, user, "announcement.create", "announcement", ann.id,
                      {"name": ann.name})
    await session.commit()
    await scheduler.reload()
    return _with_next_run(ann)


@router.get("/{announcement_id}", response_model=AnnouncementOut)
async def get_announcement(announcement_id: int, session: DbSession, _: AdminUser):
    ann = await session.get(Announcement, announcement_id)
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such announcement")
    return _with_next_run(ann)


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
    return _with_next_run(ann)


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

    ann = await session.get(Announcement, announcement_id)
    if ann is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such announcement")
    if not bot.is_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bot is not connected yet")

    try:
        await bot.send_announcement(ann)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Discord rejected it: {exc}"
        ) from exc

    await write_audit(session, user, "announcement.test", "announcement", ann.id, None)
    await session.commit()
    return {"sent": True, "name": ann.name}
