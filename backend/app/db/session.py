from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine: AsyncEngine | None = None
_async_session_local: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_async_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _async_session_local
    if _async_session_local is None:
        _async_session_local = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _async_session_local


async def dispose_engine() -> None:
    global _async_session_local, _engine
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _async_session_local = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async_session_local = get_async_sessionmaker()
    async with async_session_local() as session:
        yield session
