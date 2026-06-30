"""内置 Guard 集合（7+1 个中的 5 个实现）。

使用方式:
    from app.core.guard.guards import (
        soft_delete, version_check, idempotency,
        result_limit, query_timeout,
    )
"""

from app.core.guard.guards.idempotency import IdempotencyGuard, idempotency
from app.core.guard.guards.query_timeout import QueryTimeoutGuard, query_timeout
from app.core.guard.guards.result_limit import ResultLimitGuard, result_limit
from app.core.guard.guards.soft_delete import SoftDeleteGuard, soft_delete
from app.core.guard.guards.version_check import VersionCheckGuard, version_check

__all__ = [
    "IdempotencyGuard",
    "QueryTimeoutGuard",
    "ResultLimitGuard",
    "SoftDeleteGuard",
    "VersionCheckGuard",
    "idempotency",
    "query_timeout",
    "result_limit",
    "soft_delete",
    "version_check",
]
