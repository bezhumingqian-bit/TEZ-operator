"""结果集大小限制 Guard：查询结果超过 N 条自动截断 + 告警。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.guard.actor import Actor
from app.core.guard.chain import Guard, HarnessCtx
from app.utils.logger import get_logger

log = get_logger(__name__)


class ResultLimitGuard(Guard):
    """结果集限制 Guard。

    行为：
    - 如果原函数返回 list 且长度 > limit，截断 + warn 日志
    - 返回 dict 且含 'items' 字段，同理处理
    - 截断后会标记 _truncated / _original_size / _limit
    """

    name = "result_limit"

    def __init__(self, max_items: int = 1000) -> None:
        self.max_items = max_items

    async def after(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
        result: Any,
    ) -> Any:
        truncated = False
        original_size = 0

        if isinstance(result, list):
            original_size = len(result)
            if original_size > self.max_items:
                result = result[: self.max_items]
                truncated = True
        elif isinstance(result, dict) and "items" in result and isinstance(result["items"], list):
            original_size = len(result["items"])
            if original_size > self.max_items:
                result = {**result, "items": result["items"][: self.max_items]}
                truncated = True

        if truncated:
            log.warning(
                "harness.result_limit.truncated",
                actor_id=actor.id,
                func=ctx.func_name,
                original_size=original_size,
                limit=self.max_items,
            )
            if isinstance(result, dict):
                result = {
                    **result,
                    "_truncated": True,
                    "_original_size": original_size,
                    "_limit": self.max_items,
                }
            else:
                result = {
                    "items": result,
                    "_truncated": True,
                    "_original_size": original_size,
                    "_limit": self.max_items,
                }

        return result


def result_limit(max_items: int = 1000) -> ResultLimitGuard:
    return ResultLimitGuard(max_items=max_items)
