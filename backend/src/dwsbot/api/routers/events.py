"""Backoffice CRUD for recurring in-game event definitions."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...models import EventDefinition
from ...recurrence import next_occurrences
from ...schemas import EventCreate, EventOut
from ..deps import AdminUser, DbSession, write_audit

router = APIRouter(prefix="/events", tags=["events"])


def _out(defn: EventDefinition) -> EventOut:
    out = EventOut.model_validate(defn)
    # Preview the schedule so the backoffice can show what was just configured.
    out.upcoming = next_occurrences(defn, count=5)
    return out


@router.get("", response_model=list[EventOut])
async def list_events(session: DbSession, _: AdminUser):
    rows = (await session.scalars(select(EventDefinition).order_by(EventDefinition.id))).all()
    return [_out(r) for r in rows]


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventCreate, session: DbSession, user: AdminUser):
    defn = EventDefinition(**payload.model_dump())
    session.add(defn)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Event key '{payload.key}' already exists"
        ) from exc
    await write_audit(session, user, "event.create", "event", defn.id, {"key": defn.key})
    await session.commit()
    return _out(defn)


@router.put("/{event_id}", response_model=EventOut)
async def update_event(event_id: int, payload: EventCreate, session: DbSession, user: AdminUser):
    defn = await session.get(EventDefinition, event_id)
    if defn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such event")
    for field, value in payload.model_dump().items():
        setattr(defn, field, value)
    await write_audit(session, user, "event.update", "event", defn.id, {"key": defn.key})
    await session.commit()
    return _out(defn)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(event_id: int, session: DbSession, user: AdminUser):
    defn = await session.get(EventDefinition, event_id)
    if defn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such event")
    await write_audit(session, user, "event.delete", "event", defn.id, {"key": defn.key})
    await session.delete(defn)
    await session.commit()


@router.post("/preview", response_model=list[str], summary="Preview a schedule without saving")
async def preview(payload: EventCreate, _: AdminUser):
    """Let the backoffice show upcoming dates while the form is still being filled in."""
    provisional = EventDefinition(**payload.model_dump())
    return [dt.isoformat() for dt in next_occurrences(provisional, count=10)]
