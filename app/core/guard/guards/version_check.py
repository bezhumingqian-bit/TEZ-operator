"""版本号校验 Guard：写入必须带版本号，防止并发覆盖。"""

from __future__ import annotations

from collections.abc import Callable

from app.core.guard.actor import Actor
from app.core.guard.chain import Guard, HarnessCtx
from app.core.guard.exceptions import GuardRejected
from app.utils.logger import get_logger

log = get_logger(__name__)


class VersionCheckGuard(Guard):
    """版本号校验 Guard。

    要求调用方传 `version` 字段（业务函数实际收到），并由业务函数在 update 时
    用 ctx.extra['_expected_version'] 做乐观锁。

    用法（业务侧示例）:
        @guard_chain(audit_log(), version_check())
        async def update_host(asset_id, payload, version, actor, ctx=None):
            result = await db.update(
                asset_id, payload,
                where={"version": version}
            )
            if result.rowcount == 0:
                raise ConflictError("数据已被他人修改")
    """

    name = "version_check"

    async def before(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        actor: Actor,
        ctx: HarnessCtx,
    ) -> tuple[tuple, dict]:
        version = kwargs.get("version")
        if version is None:
            log.warning(
                "harness.version_check.missing_version",
                actor_id=actor.id,
                func=ctx.func_name,
            )
            raise GuardRejected(
                f"version_check Guard 要求参数中包含 'version' 字段。"
                f"这是为了防止并发覆盖。"
                f"调用方: actor={actor.id}, func={ctx.func_name}"
            )

        # 把期望版本号存到 ctx（不污染 kwargs）
        ctx.extra["_expected_version"] = version
        return args, kwargs


def version_check() -> VersionCheckGuard:
    return VersionCheckGuard()
