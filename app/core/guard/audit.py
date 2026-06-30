"""审计日志 Guard：所有动作强制留痕。"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from app.core.guard.actor import Actor
from app.core.guard.chain import Guard, HarnessCtx
from app.utils.logger import get_logger

log = get_logger(__name__)


class AuditLogGuard(Guard):
    """审计日志 Guard。

    所有经过此 Guard 的动作都会产出一条审计日志（结构化日志格式）。
    失败/成功都会记。
    """

    name = "audit_log"

    async def before(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
    ) -> tuple[tuple, dict]:
        ctx.start_time = time.monotonic()
        log.info(
            "harness.audit.start",
            actor_id=actor.id,
            actor_type=actor.type.value,
            func=ctx.func_name,
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
        duration_ms = int((time.monotonic() - ctx.start_time) * 1000)
        log.info(
            "harness.audit.success",
            actor_id=actor.id,
            actor_type=actor.type.value,
            func=ctx.func_name,
            duration_ms=duration_ms,
            result_type=type(result).__name__,
        )
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
        duration_ms = int((time.monotonic() - ctx.start_time) * 1000) if ctx.start_time else 0
        log.error(
            "harness.audit.error",
            actor_id=actor.id,
            actor_type=actor.type.value,
            func=ctx.func_name,
            duration_ms=duration_ms,
            error_type=type(exc).__name__,
            error=str(exc),
        )


def audit_log() -> AuditLogGuard:
    """工厂函数：返回一个 AuditLogGuard 实例。"""
    return AuditLogGuard()
