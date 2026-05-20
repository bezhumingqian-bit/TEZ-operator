"""CacheService 单测：fakeredis 真路径 + 内存降级路径 + TTL。

覆盖 reviewer 建议-10：cache_service.py 当前 0% 覆盖。
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest

from app.services.cache_service import CacheService, _MemoryCache

# ─────────────────────────────────────────────
# 1) _MemoryCache 单元测试（不依赖 redis）
# ─────────────────────────────────────────────


@pytest.mark.asyncio
class TestMemoryCache:
    async def test_set_and_get(self) -> None:
        m = _MemoryCache()
        await m.set("k", "v")
        assert await m.get("k") == "v"

    async def test_ttl_expire(self) -> None:
        m = _MemoryCache()
        await m.set("k", "v", ttl=1)
        # 手动把 expire 改到过去，避免真睡 1s
        expire, value = m._store["k"]
        m._store["k"] = (expire - 10, value)
        assert await m.get("k") is None

    async def test_delete(self) -> None:
        m = _MemoryCache()
        await m.set("k", "v")
        await m.delete("k")
        assert await m.get("k") is None
        # 删不存在的不报错
        await m.delete("missing")

    async def test_clear(self) -> None:
        m = _MemoryCache()
        await m.set("a", "1")
        await m.set("b", "2")
        await m.clear()
        assert await m.get("a") is None
        assert await m.get("b") is None

    async def test_zero_ttl_no_expire(self) -> None:
        m = _MemoryCache()
        await m.set("k", "v", ttl=0)
        assert await m.get("k") == "v"


# ─────────────────────────────────────────────
# 2) CacheService 真 Redis 路径（fakeredis 注入）
# ─────────────────────────────────────────────


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.mark.asyncio
class TestCacheServiceRedisPath:
    async def test_set_and_get_via_fakeredis(self, fake_redis) -> None:
        svc = CacheService()
        # 注入 fakeredis，绕开 _get_redis 的真实连接
        svc._redis = fake_redis

        await svc.set("host:TYSV00000001", {"asset_id": "TYSV00000001", "ip": "10.0.0.1"})
        got = await svc.get("host:TYSV00000001")
        assert got == {"asset_id": "TYSV00000001", "ip": "10.0.0.1"}

    async def test_get_miss_returns_none(self, fake_redis) -> None:
        svc = CacheService()
        svc._redis = fake_redis
        assert await svc.get("missing") is None

    async def test_set_with_ttl(self, fake_redis) -> None:
        svc = CacheService(default_ttl=10)
        svc._redis = fake_redis
        await svc.set("k", "v", ttl=5)
        # fakeredis 支持 ttl 查询
        ttl = await fake_redis.ttl("k")
        assert 0 < ttl <= 5

    async def test_set_default_ttl(self, fake_redis) -> None:
        svc = CacheService(default_ttl=300)
        svc._redis = fake_redis
        await svc.set("k", "v")  # ttl 走默认
        ttl = await fake_redis.ttl("k")
        assert 0 < ttl <= 300

    async def test_set_zero_ttl_no_expire(self, fake_redis) -> None:
        svc = CacheService(default_ttl=300)
        svc._redis = fake_redis
        await svc.set("k", "v", ttl=0)
        ttl = await fake_redis.ttl("k")
        # -1 表示无 TTL
        assert ttl == -1

    async def test_delete(self, fake_redis) -> None:
        svc = CacheService()
        svc._redis = fake_redis
        await svc.set("k", "v")
        await svc.delete("k")
        assert await svc.get("k") is None

    async def test_set_serialize_failure_no_raise(self, fake_redis) -> None:
        """不可序列化对象走 default=str 应当能落盘，否则只记 log。"""
        svc = CacheService()
        svc._redis = fake_redis

        # asyncio.Lock 这种不可 json，但 default=str 兜底，不应 raise
        await svc.set("k", asyncio.Lock())
        # 不报错即通过

    async def test_close_releases_redis(self, fake_redis) -> None:
        svc = CacheService()
        svc._redis = fake_redis
        await svc.close()
        # close 后 _redis 置空
        assert svc._redis is None


# ─────────────────────────────────────────────
# 3) Redis 不可用降级到内存路径
# ─────────────────────────────────────────────


@pytest.mark.asyncio
class TestCacheServiceMemoryFallback:
    async def test_redis_unavailable_falls_back_to_memory(self) -> None:
        # 用一个不可达的 url，触发降级
        svc = CacheService(url="redis://127.0.0.1:1/0")  # 端口 1 必失败
        await svc.set("k", {"v": 1})
        assert svc._use_memory is True
        got = await svc.get("k")
        assert got == {"v": 1}

    async def test_get_failure_falls_back(self) -> None:
        svc = CacheService(url="redis://127.0.0.1:1/0")
        # 直接 get（也会触发首次降级判断）
        result = await svc.get("nothing")
        assert result is None
        assert svc._use_memory is True

    async def test_delete_in_memory_mode(self) -> None:
        svc = CacheService(url="redis://127.0.0.1:1/0")
        await svc.set("k", "v")
        await svc.delete("k")
        assert await svc.get("k") is None

    async def test_set_with_runtime_error_fallback(self, fake_redis) -> None:
        """已连接的 redis 中途出错时降级到内存（兜底）。"""
        svc = CacheService()
        svc._redis = fake_redis

        # 把 fake_redis 的 set 替换为会抛异常的版本
        async def boom(*_a, **_kw):
            raise RuntimeError("boom")

        fake_redis.set = boom  # type: ignore[method-assign]
        await svc.set("k", "v")
        assert svc._use_memory is True
        # 落到内存能读出
        assert await svc.get("k") == "v"

    async def test_close_when_no_redis_no_raise(self) -> None:
        svc = CacheService()
        # 未触发任何 _get_redis，_redis 仍是 None
        await svc.close()  # 不应 raise


# ─────────────────────────────────────────────
# 4) 序列化 / 反序列化路径
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_raw_string_when_not_json(fake_redis) -> None:
    """fakeredis 直接塞个非 json 串，应该原样返回。"""
    svc = CacheService()
    svc._redis = fake_redis
    await fake_redis.set("k", "not-a-json")
    assert await svc.get("k") == "not-a-json"
