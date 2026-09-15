from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

engine = None
async_session_factory = None


def init_db_engine():
    """Initialize the database engine. Must be called before running the app."""
    import asyncpg  # noqa: F401 - must be imported before SQLAlchemy create_async_engine
    from sqlalchemy.ext.asyncio import create_async_engine

    global engine, async_session_factory
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,
        pool_pre_ping=True,
        echo=settings.is_development,
    )
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        init_db_engine()
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# FastAPI's `Depends(get_session)` drives the bare async generator itself, so
# `get_session` must stay undecorated. Non-FastAPI callers (Celery workers)
# need an actual context manager to use `async with`; wrap it separately here
# rather than decorating get_session, which would break dependency injection.
get_session_context = asynccontextmanager(get_session)


async def init_db() -> None:
    if engine is None:
        init_db_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None
