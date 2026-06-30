"""幂等性 Guard：触发类动作必须带幂等键，30 分钟内重复执行直接返回上次结果。"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from app.core.guard.actor import Actor
from app.core.guard.chain import Guard, HarnessCtx
from app.utils.logger import get_logger

log = get_logger(__name__)


class IdempotencyStore:
    """幂等键存储（内存版，生产应换 Redis）。"""

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        if key not in self._store:
            return None
        ts, value = self._store[key]
        if time.time() - ts > self.ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)


# 全局单例（PoC 阶段先用内存版）
_store = IdempotencyStore()


class IdempotencyGuard(Guard):
    """幂等性 Guard。

    行为：
    1. 如果 kwargs 中有 `idempotency_key`，用它去 _store 里查
    2. 命中 → 直接返回上次结果（不执行原函数）
    3. 未命中 → 执行原函数，把结果存进 _store
    """

    name = "idempotency"

    async def before(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
    ) -> tuple[tuple, dict]:
        key = kwargs.get("idempotency_key")
        if not key:
            # 自动生成（基于 actor + func + 原始参数 hash，不含 idempotency_key 字段，
            # 这样同一调用连续触发会产生同样的 key）
            clean_kwargs = {k: v for k, v in kwargs.items() if k != "idempotency_key"}
            payload = json.dumps(
                {
                    "actor": actor.id,
                    "func": ctx.func_name,
                    "args": str(args),
                    "kwargs": str(clean_kwargs),
                },
                sort_keys=True,
            )
            key = hashlib.sha256(payload.encode()).hexdigest()[:32]
            kwargs["idempotency_key"] = key

        ctx.idempotency_key = key
        cached = _store.get(key)
        if cached is not None:
            ctx.has_cache_hit = True
            ctx.cached_result = cached
            # 短路：chain 看到后会跳过原函数，直接走 after 链
            ctx.extra["__short_circuit__"] = cached
            log.info(
                "harness.idempotency.hit",
                actor_id=actor.id,
                func=ctx.func_name,
                key=key,
            )
        return args, kwargs

    async def after(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
        result: Any,
    ) -> Any:
        # before 阶段命中缓存时，直接返回缓存
        if ctx.has_cache_hit:
            return ctx.cached_result

        # 否则把结果存起来
        if ctx.idempotency_key:
            _store.set(ctx.idempotency_key, result)
        return result


def idempotency() -> IdempotencyGuard:
    return IdempotencyGuard()
