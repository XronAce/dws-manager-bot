"""Async SQLAlchemy engine and session plumbing.

The engine is built lazily rather than at import time. Importing the models
should not require a Discord token or a reachable database — that would make
the model layer untestable and force CI to invent fake credentials just to
collect the test suite.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,   # home server; connections can be reaped by the router
        pool_recycle=1800,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)


def SessionLocal() -> AsyncSession:  # noqa: N802 - reads as a class at call sites
    """Open a new session: `async with SessionLocal() as session:`."""
    return get_sessionmaker()()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a transactional session."""
    async with SessionLocal() as session:
        yield session
