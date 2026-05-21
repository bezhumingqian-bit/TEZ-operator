"""FastAPI 依赖注入。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.services.host_service import HostService

_host_service_singleton: HostService | None = None


def get_host_service() -> HostService:
    """单例 HostService（FastAPI Depends 使用）。"""

    global _host_service_singleton
    if _host_service_singleton is None:
        _host_service_singleton = HostService()
    return _host_service_singleton


def set_host_service(service: HostService | None) -> None:
    """测试用：覆盖单例。"""

    global _host_service_singleton
    _host_service_singleton = service


# ─────────────── Async DB Session ───────────────

_async_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_async_engine():
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        # 将同步 URL 转为 async（sqlite → aiosqlite, mysql → aiomysql）
        db_url = settings.database_url
        if "sqlite+pysqlite" in db_url:
            db_url = db_url.replace("sqlite+pysqlite", "sqlite+aiosqlite")
        elif "sqlite" in db_url and "aiosqlite" not in db_url:
            db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
        elif "pymysql" in db_url:
            db_url = db_url.replace("pymysql", "aiomysql")
        _async_engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
    return _async_engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            _get_async_engine(), expire_on_commit=False
        )
    return _async_session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends：每请求一个 async session，请求结束自动关闭。"""
    factory = _get_session_factory()
    async with factory() as session:
        yield session
