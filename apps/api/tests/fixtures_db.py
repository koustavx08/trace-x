"""
Shared, additive test fixtures for WS4 (backend test suite).

This module intentionally lives outside conftest.py so that the shared
DB/HTTP fixtures used by test_wallets.py, test_cases.py, test_graph.py,
test_risk.py and test_reports.py can be reused without editing the
pre-existing conftest.py fixtures (test_engine/test_session/event_loop).

Import what you need directly into a test module, e.g.:

    from fixtures_db import db_session, api_client  # noqa: F401

`db_session` is intentionally independent from conftest.py's session-scoped
`test_engine` fixture: that fixture eagerly creates the schema the moment
any test requests it, and if the `tracex_test` Postgres database isn't
reachable (e.g. no local Postgres/Docker in a sandbox), a session-scoped
fixture failure would ERROR every subsequent test that depends on it for
the rest of the run. `db_session` instead probes connectivity itself and
calls `pytest.skip(...)` on failure, so tests that need a real database
skip cleanly (not "pass" falsely, not cascade-error) when one isn't
available, while still exercising the real DB code path whenever Postgres
*is* reachable (e.g. in CI / a docker-compose'd dev environment).
"""
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core.config import get_settings
from src.core.database import Base, get_session
from src.main import app


def _test_database_url() -> str:
    settings = get_settings()
    return settings.DATABASE_URL.replace("tracex", "tracex_test")


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """A real AsyncSession against the `tracex_test` Postgres database.

    Skips (does not fail/error) the requesting test if that database isn't
    reachable.
    """
    engine = create_async_engine(_test_database_url(), poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover - environment dependent
        await engine.dispose()
        pytest.skip(f"tracex_test Postgres database not reachable: {exc}")
        return

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = async_session()
    try:
        yield session
    finally:
        await session.rollback()
        await session.close()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """An httpx AsyncClient wired to the FastAPI app, with `get_session`
    overridden to hand out the `tracex_test`-backed `db_session` instead of
    the real dev/prod database `main.py`/`core.database` otherwise points
    at. Depends on `db_session`, so it skips under the same conditions.
    """

    async def _override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)
