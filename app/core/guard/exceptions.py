"""Guard 异常体系。"""

from __future__ import annotations


class GuardError(Exception):
    """Guard 抛出的所有异常的基类。"""

    guards_applied: list[str] = []
    guards_rejected: list[str] = []

    def __init__(self, message: str, *args, **kwargs) -> None:
        super().__init__(message, *args)
        self.message = message


class GuardRejected(GuardError):  # noqa: N818
    """Guard 拒绝放行。"""


class PermissionDenied(GuardRejected):
    """权限不足。"""


class GuardTimeout(GuardRejected):
    """Guard 超时。"""
