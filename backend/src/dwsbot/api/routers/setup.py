"""The guided path: define an event and its first announcement together.

The two halves are separate resources, and separate endpoints exist for
editing either. But creating them one at a time is where a newcomer gets
lost — and a failure between the two calls leaves an event with nothing
attached, which looks broken rather than half-finished. So the guided flow
commits both or neither.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from ...models import Announcement, EventDefinition, ScheduleKind
from ...schemas import AnnouncementBase, EventCreate, EventOut
from ..deps import AdminUser, DbSession, write_audit

router = APIRouter(prefix="/setup", tags=["setup"])


class GuidedSetupIn(BaseModel):
    event: EventCreate
    # AnnouncementBase, not AnnouncementCreate: the latter insists on an
    # event_id, which cannot exist until the event in this same payload has
    # been written. The id is filled in server-side below.
    announcement: AnnouncementBase


class GuidedSetupOut(BaseModel):
    event_id: int
    announcement_id: int
    event: EventOut


@router.post("/event-announcement", response_model=GuidedSetupOut,
             status_code=status.HTTP_201_CREATED)
async def create_event_with_announcement(
    payload: GuidedSetupIn, session: DbSession, user: AdminUser
):
    """Create an event and one announcement wired to it, in a single commit."""
    defn = EventDefinition(
        **payload.event.model_dump(),
        created_by_id=user.discord_id,
        created_by_name=user.username,
    )
    session.add(defn)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"An event with the key '{payload.event.key}' already exists",
        ) from None

    fields = payload.announcement.model_dump()
    # The wizard cannot know the id before the event exists, so it is filled in
    # here rather than trusted from the client.
    fields["event_id"] = defn.id
    fields["kind"] = ScheduleKind.EVENT
    ann = Announcement(
        **fields,
        created_by_id=user.discord_id,
        created_by_name=user.username,
    )
    session.add(ann)
    await session.flush()

    await write_audit(session, user, "event.create", "event", defn.id, {"key": defn.key})
    await write_audit(
        session, user, "announcement.create", "announcement", ann.id, {"name": ann.name}
    )
    await session.commit()

    from ...scheduler import scheduler
    from .events import _out

    await scheduler.reload()
    return GuidedSetupOut(
        event_id=defn.id, announcement_id=ann.id, event=await _out(session, defn)
    )
