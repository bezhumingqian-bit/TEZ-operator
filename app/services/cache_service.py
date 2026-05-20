"""Redis 缓存封装。

设计：
- async get/set，JSON 序列化
- TTL 默认 300s（可被传参覆盖）
- 提供 in-memory fallback：当 Redis 连接失败 / 测试场景，自动降级到进程内字典
"""

from __future__ import annotations

import json
import time
from typing import Any

try:
    import redis.asyncio as aioredis  # type: ignore[import-not-found]

    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REDIS_AVAILABLE = False

from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class _MemoryCache:
    """进程内字典缓存，作为 Redis 不可用时的降级。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    async def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if not item:
            return None
        expire, value = item
        if expire > 0 and time.time() > expire:
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl: int = 0) -> None:
        expire = time.time() + ttl if ttl > 0 else 0
        self._store[key] = (expire, value)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def clear(self) -> None:
        self._store.clear()


class CacheService:
    """统一的缓存服务。"""

    def __init__(self, url: str | None = None, default_ttl: int | None = None) -> None:
        s = get_settings()
        self._url = url or s.redis_url
        self._default_ttl = default_ttl if default_ttl is not None else s.cache_default_ttl
        self._redis: Any = None
        self._memory = _MemoryCache()
        self._use_memory = False

    async def _get_redis(self) -> Any:
        if self._use_memory:
            return None
        if self._redis is None:
            if not _REDIS_AVAILABLE:
                log.warning("cache.redis_lib_missing_use_memory")
                self._use_memory = True
                return None
            try:
                self._redis = aioredis.from_url(self._url, decode_responses=True)
                await self._redis.ping()
            except Exception as exc:  # noqa: BLE001
                log.warning("cache.redis_unavailable_use_memory", error=str(exc))
                self._use_memory = True
                self._redis = None
        return self._redis

    async def get(self, key: str) -> Any:
        client = await self._get_redis()
        if client is None:
            raw = await self._memory.get(key)
        else:
            try:
                raw = await client.get(key)
            except Exception as exc:  # noqa: BLE001
                log.warning("cache.get_failed_fallback", key=key, error=str(exc))
                self._use_memory = True
                raw = await self._memory.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl_seconds = self._default_ttl if ttl is None else ttl
        try:
            payload = json.dumps(value, default=str, ensure_ascii=False)
        except TypeError as exc:
            log.warning("cache.set_serialize_failed", key=key, error=str(exc))
            return

        client = await self._get_redis()
        if client is None:
            await self._memory.set(key, payload, ttl=ttl_seconds)
            return
        try:
            if ttl_seconds > 0:
                await client.set(key, payload, ex=ttl_seconds)
            else:
                await client.set(key, payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("cache.set_failed_fallback", key=key, error=str(exc))
            self._use_memory = True
            await self._memory.set(key, payload, ttl=ttl_seconds)

    async def delete(self, key: str) -> None:
        client = await self._get_redis()
        if client is None:
            await self._memory.delete(key)
            return
        try:
            await client.delete(key)
        except Exception as exc:  # noqa: BLE001
            log.warning("cache.delete_failed", key=key, error=str(exc))

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # pragma: no cover  # noqa: BLE001
                pass
            self._redis = None


# 全局单例（路由 / 服务直接 import 使用；测试可通过 dependency override）
cache = CacheService()
