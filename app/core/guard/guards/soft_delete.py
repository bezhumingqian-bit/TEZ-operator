"""软删除 Guard：所有删除走软删除，不真 DELETE。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.core.guard.actor import Actor
from app.core.guard.chain import Guard, HarnessCtx
from app.core.guard.exceptions import GuardRejected
from app.utils.logger import get_logger

log = get_logger(__name__)


class SoftDeleteGuard(Guard):
    """软删除 Guard。

    行为：
    1. 把 kwargs 中的 `hard_delete` 强制设为 False（不管调用方传什么）
    2. 自动注入 `deleted_at` / `deleted_by` 字段到 kwargs（业务函数接收）
    3. 在 audit log 中标记为 soft_delete 操作
    """

    name = "soft_delete"

    async def before(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
    ) -> tuple[tuple, dict]:
        if kwargs.get("hard_delete"):
            log.warning(
                "harness.soft_delete.blocked_hard_delete",
                actor_id=actor.id,
                func=ctx.func_name,
            )
            raise GuardRejected(
                "软删除 Guard 已启用，禁止 hard_delete。 "
                "如需物理删除，请显式走 admin 接口（不在 Harness 保护下）。"
            )

        # 这些是业务字段（deleted_at / deleted_by），业务函数如果定义了同名字段会自然接收
        # 标记软删除模式（ctx）
        ctx.soft_delete = True
        kwargs["deleted_at"] = datetime.now(timezone.utc).isoformat()  # noqa: UP017 — 3.9 compat
        kwargs["deleted_by"] = actor.id

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
        log.info(
            "harness.soft_delete.applied",
            actor_id=actor.id,
            func=ctx.func_name,
        )
        return result


def soft_delete() -> SoftDeleteGuard:
    return SoftDeleteGuard()
