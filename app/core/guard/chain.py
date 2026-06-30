"""Guard 链：所有守卫的基类和组合机制。

设计要点：
- Guard 之间通过 before/after 通信
- Guard 注入的私有元数据存到 _HarnessCtx（不污染 kwargs）
- 原函数的 kwargs 不会被 Guard 看到私有字段
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from app.core.guard.actor import Actor
from app.core.guard.exceptions import GuardRejected


@dataclass
class HarnessCtx:
    """Guard 链的私有上下文，跨 Guard 传递元数据，但不暴露给原函数。"""

    start_time: float = 0.0
    func_name: str = ""
    soft_delete: bool = False
    idempotency_key: str = ""
    cached_result: Any = None
    has_cache_hit: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class Guard:
    """所有 Guard 的基类。

    一个 Guard 拦截一次函数调用，可以：
    - 放行（不修改参数）
    - 改写（修改参数后再传给下一个）
    - 拒绝（抛 GuardRejected）

    通过 before/after/on_error 三个钩子实现统一的拦截点。
    子类应设置 `name` 类属性作为唯一标识。
    """

    name: str = "base"

    async def before(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
    ) -> tuple[tuple, dict]:
        """调用前检查。返回 (args, kwargs) 传给下一个 Guard 或原函数。

        抛 GuardRejected 表示拒绝。默认空实现（子类可重写）。
        """
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
        """调用后处理（默认不做事，子类可重写）。"""
        return result

    async def on_error(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
        exc: Exception,
    ) -> None:
        """出错时的处理（默认不做事，子类可重写）。"""
        return None


def guard_chain(*guards: Guard) -> Callable:
    """Guard 链装饰器：把多个 Guard 串成一个执行链。

    用法:
        @guard_chain(audit_log(), version_check(), soft_delete())
        async def delete_host(asset_id: str, actor: Actor):
            ...
    """
    if not guards:
        raise ValueError("guard_chain 至少需要一个 Guard")

    def decorator(func: Callable) -> Callable:
        func.__harness_guards__ = [g.name for g in guards]  # type: ignore[attr-defined]

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1. 提取 actor
            actor = _extract_actor(args, kwargs)
            if actor is None:
                raise GuardRejected(
                    "guard_chain 要求函数签名包含 actor: Actor 参数，"
                    f"实际参数: args={args}, kwargs={list(kwargs.keys())}"
                )

            applied: list[str] = []
            ctx = HarnessCtx(func_name=func.__name__)

            # 2. 顺序执行 before
            current_args, current_kwargs = args, dict(kwargs)
            for g in guards:
                try:
                    current_args, current_kwargs = await g.before(
                        func, current_args, current_kwargs, actor, ctx
                    )
                    applied.append(g.name)
                except GuardRejected as e:
                    e.guards_applied = applied
                    e.guards_rejected = [*applied[-1:]] if applied else []
                    raise

            # 3. 检查是否有 Guard 要求短路（如 idempotency 缓存命中）
            # before 阶段可设置 ctx.extra['__short_circuit__'] = value 来跳过原函数
            short_circuit = ctx.extra.get("__short_circuit__")
            if short_circuit is not None:
                # 倒序触发 after（让所有 Guard 都有机会处理 cached value）
                result = short_circuit
                for g in reversed(guards):
                    result = await g.after(func, current_args, current_kwargs, actor, ctx, result)
                return result

            # 4. 执行原函数
            try:
                result = await func(*current_args, **current_kwargs)
            except Exception as exc:
                # 倒序触发 on_error
                for g in reversed(guards):
                    await g.on_error(func, current_args, current_kwargs, actor, ctx, exc)
                raise

            # 5. 顺序执行 after
            for g in guards:
                result = await g.after(func, current_args, current_kwargs, actor, ctx, result)

            return result

        wrapper.__harness_guards__ = [g.name for g in guards]  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _extract_actor(args: tuple, kwargs: dict) -> Actor | None:
    """从参数中提取 Actor。

    支持两种位置：
    - 最后一个位置参数
    - 名为 'actor' 的关键字参数
    """
    if "actor" in kwargs and isinstance(kwargs["actor"], Actor):
        return kwargs["actor"]
    if args and isinstance(args[-1], Actor):
        return args[-1]
    return None
