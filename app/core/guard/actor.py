"""Actor：执行者抽象。

每个动作都必须由一个 Actor 执行。
AI Agent、人、调度器都是不同的 Actor 类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ActorType(str, Enum):  # noqa: UP042 — keep (str, Enum) for Python 3.9 compat
    """执行者类型。"""

    HUMAN = "human"          # 真人用户
    AI = "ai"                # AI Agent
    SYSTEM = "system"        # 调度器/定时任务
    SERVICE = "service"      # 内部服务调用


@dataclass
class Actor:
    """执行者：所有 Guard 链的输入参数。

    Attributes:
        id: 唯一标识（AI agent 名称 / 用户 ID / 系统服务名）
        type: 执行者类型
        session_id: 会话标识（用于追踪同一次操作链）
        permissions: 权限列表（如 ["resource:read", "resource:write"]）
        metadata: 额外元数据（IP、UA、租户等）
    """

    id: str
    type: ActorType
    session_id: str = field(default_factory=lambda: str(uuid4()))
    permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))  # noqa: UP017 — 3.9 compat

    def has_permission(self, perm: str) -> bool:
        """检查是否拥有某权限。

        支持通配符：
        - "*" 匹配所有
        - "resource:*" 匹配 resource:read、resource:write 等
        """
        if "*" in self.permissions:
            return True
        if perm in self.permissions:
            return True
        # 前缀通配
        prefix = perm.split(":")[0] + ":*"
        if prefix in self.permissions:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，用于审计日志。"""
        return {
            "id": self.id,
            "type": self.type.value,
            "session_id": self.session_id,
            "permissions": self.permissions,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }
