"""agent-guard：AI Agent 动作守卫框架（L4 中间件/装饰器层）。

为 TEZ Operator 内部 AI Agent 提供物理级安全约束，
避免 LLM 在执行"写入/删除/触发"等高风险动作时出错。

使用示例:
    from app.core.guard import Actor, ActorType
    from app.core.guard import guard_chain, audit_log
    from app.core.guard.guards import soft_delete, version_check

    @guard_chain(audit_log(), version_check(), soft_delete())
    async def delete_host(asset_id: str, actor: Actor):
        ...
"""

from app.core.guard.actor import Actor, ActorType
from app.core.guard.audit import audit_log
from app.core.guard.chain import Guard, guard_chain
from app.core.guard.exceptions import (
    GuardError,
    GuardRejected,
    GuardTimeout,
    PermissionDenied,
)

__version__ = "0.1.0"

__all__ = [
    # 核心抽象
    "Actor",
    "ActorType",
    "Guard",
    "guard_chain",
    # 异常
    "GuardError",
    "GuardRejected",
    "GuardTimeout",
    "PermissionDenied",
    # 内置 Guard（最常用的 2 个）
    "audit_log",
    # 子包 guards 需要单独导入：
    # from app.core.guard.guards import soft_delete, version_check, idempotency, ...
]
