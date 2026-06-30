"""查询超时 Guard：超过指定秒数自动中断。

注意：当前 PoC 阶段，超时控制建议由 chain 层用 asyncio.wait_for 包装原函数实现。
Guard 类主要负责传递超时值给业务层做参考。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.guard.actor import Actor
from app.core.guard.chain import Guard, HarnessCtx
from app.utils.logger import get_logger

log = get_logger(__name__)


class QueryTimeoutGuard(Guard):
    """查询超时 Guard。

    行为：
    - 把超时值存到 ctx，业务层可以基于这个值做超时控制
    - M3 阶段会扩展为 chain 层用 asyncio.wait_for 自动包装
    """

    name = "query_timeout"

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout = timeout_seconds

    async def before(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
    ) -> tuple[tuple, dict]:
        ctx.extra["_query_timeout"] = self.timeout
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
        return result


def query_timeout(timeout_seconds: float = 5.0) -> QueryTimeoutGuard:
    return QueryTimeoutGuard(timeout_seconds=timeout_seconds)
