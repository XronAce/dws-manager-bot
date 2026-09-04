"""The shared line-up endpoint, exercised against a real database.

Runs on SQLite so it needs no server; JSONB is told to compile as JSON there.
That covers routing, permissions and the JSON round-trip. It does not prove
anything about Postgres-specific behaviour — the deployed database is Postgres 16.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from dwsbot.api.deps import current_user, get_session, require_admin
from dwsbot.api.routers import lineups
from dwsbot.db import Base
from dwsbot.schemas import MeOut


@compiles(JSONB, "sqlite")
def _jsonb_on_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


OFFICER = MeOut(discord_id=1, username="Officer", is_admin=True)
MEMBER = MeOut(discord_id=2, username="Member", is_admin=False)


@pytest_asyncio.fixture
async def client_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    def build(user: MeOut):
        app = FastAPI()
        app.include_router(lineups.router)

        async def _session():
            async with maker() as s:
                yield s

        async def _user():
            return user

        async def _admin():
            if not user.is_admin:
                from fastapi import HTTPException, status
                raise HTTPException(status.HTTP_403_FORBIDDEN, "officers only")
            return user

        app.dependency_overrides[get_session] = _session
        app.dependency_overrides[current_user] = _user
        app.dependency_overrides[require_admin] = _admin
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    yield build
    await engine.dispose()


PLAN = {
    "order": ["Dubai88", "Ronin", "Sunflowerseeds"],
    "mercs": [{"name": "Ronin", "bgb": 0}],
    "opts": {"version": 1, "orient": "bottom", "portalOwners": 24},
}


@pytest.mark.asyncio
async def test_missing_plan_reads_as_empty(client_factory):
    async with client_factory(MEMBER) as c:
        r = await c.get("/lineups/default")
    assert r.status_code == 200
    assert r.json()["order"] == []


@pytest.mark.asyncio
async def test_officer_saves_and_anyone_reads_it_back(client_factory):
    async with client_factory(OFFICER) as c:
        put = await c.put("/lineups/default", json=PLAN)
    assert put.status_code == 200, put.text
    assert put.json()["updated_by_name"] == "Officer"

    async with client_factory(MEMBER) as c:
        got = await c.get("/lineups/default")
    body = got.json()
    assert body["order"] == PLAN["order"]                 # hand-tuned order survives
    assert body["mercs"] == PLAN["mercs"]                 # mercenaries survive
    assert body["opts"]["portalOwners"] == 24
    assert body["updated_by_name"] == "Officer"


@pytest.mark.asyncio
async def test_plain_member_cannot_save(client_factory):
    async with client_factory(MEMBER) as c:
        r = await c.put("/lineups/default", json=PLAN)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_save_is_a_replace_not_a_merge(client_factory):
    async with client_factory(OFFICER) as c:
        await c.put("/lineups/default", json=PLAN)
        await c.put("/lineups/default", json={"order": ["XoD"], "mercs": [], "opts": {}})
        r = await c.get("/lineups/default")
    assert r.json()["order"] == ["XoD"]
    assert r.json()["mercs"] == []


@pytest.mark.asyncio
async def test_oversized_plan_is_refused(client_factory):
    async with client_factory(OFFICER) as c:
        r = await c.put("/lineups/default", json={"order": [f"m{i}" for i in range(1001)],
                                                  "mercs": [], "opts": {}})
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_officer_can_clear_and_member_cannot(client_factory):
    async with client_factory(OFFICER) as c:
        await c.put("/lineups/default", json=PLAN)
    async with client_factory(MEMBER) as c:
        assert (await c.delete("/lineups/default")).status_code == 403
