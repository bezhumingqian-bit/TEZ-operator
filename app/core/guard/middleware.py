"""FastAPI 全局中间件：在请求层自动给 AI Actor 套上 Guard 链。

设计原则：
- 不改任何 endpoint 签名
- 不强制每个 endpoint 都接 Guard
- 通过路径前缀 + HTTP 方法自动判断元操作类型
- 关键写/触发/删除操作由中间件审计 + 套默认 Guard
- 人类操作不受影响

启用方式（main.py 中）:
    from app.core.guard.middleware import HarnessMiddleware
    app.add_middleware(HarnessMiddleware)

当前 PoC（M1 阶段）：
- 所有 AI 调用留痕（harness.middleware.ai_request / ai_response）
- 写/删除自动套 Guard 链（但 Guard 默认不强制拒绝，只审计）
- 触发类操作（POST /sync, POST /transition 等）自动套 idempotency

M3 W1 阶段（计划）：
- 在 service 层方法上加 @guard_chain 强制执行
- 取消中间件的"宽松模式"
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.guard.actor import Actor, ActorType
from app.core.guard.audit import audit_log
from app.core.guard.exceptions import GuardError, GuardRejected
from app.core.guard.guards import (
    idempotency,
    result_limit,
    soft_delete,
    version_check,
)
from app.utils.logger import get_logger

log = get_logger(__name__)


# 路径前缀 → 强制元操作类型（覆盖默认推断）
# key: path prefix
# value: 强制 op_type（write / delete / trigger / read / notify / configure / sync）
PATH_OP_OVERRIDES: dict[str, str] = {
    # ── hosts / zones ──
    "/api/v1/hosts": "read",           # 主机查询（默认读）
    "/api/v1/zones": "read",            # zone 查询（默认读）
    "/api/v1/hosts/export": "read",     # 导出（读）
    "/api/v1/hosts/batch_search": "read",  # 批量查（读）
    "/api/v1/zones/sync-all": "trigger",   # 全量同步
    "/api/v1/zones/snapshots": "read",     # 快照列表
    # ── contacts ──
    "/api/v1/contacts": "write",        # 联系人 CUD
    "/api/v1/contacts/route": "read",   # 接口人路由（查）
    "/api/v1/contacts/search": "read",  # 搜索（查）
    "/api/v1/contacts/categories": "read", # 分类列表
    # ── knowledge ──
    "/api/v1/knowledge/search": "read",      # 搜索
    "/api/v1/knowledge/articles": "write",   # 文章 CUD
    "/api/v1/knowledge/articles/upload": "write",  # 上传
    "/api/v1/knowledge/links": "write",      # 链接 CUD
    "/api/v1/knowledge/faqs": "write",       # FAQ CUD
    "/api/v1/knowledge/sop-flows": "read",   # SOP 读
    # ── workorders ──
    "/api/v1/workorders": "write",        # 工单 CUD
    "/api/v1/workorders/demand": "write", # 需求提单
    "/api/v1/workorders/stats": "read",   # 统计
    # ── op-logs ──
    "/api/v1/op-logs": "read",            # 日志查询
    # ── auth ──
    "/api/v1/auth/login": "read",         # 登录（不敏感）
    "/api/v1/auth/me": "write",           # 个人信息修改
    "/api/v1/auth/users": "write",        # 用户管理
    # ── cost ──
    "/api/v1/cost": "read",               # 成本查询
    # ── ai ──
    "/api/v1/ai/status": "read",          # AI 状态
    "/api/v1/ai/chat": "write",           # AI 对话（生成类）
    "/api/v1/ai/agent": "write",          # AI Agent（生成+工具调用）
    "/api/v1/ai/analyze": "write",        # 竞争分析（生成）
    # ── yunxiao ──
    "/api/v1/yunxiao/host-machines": "read",   # 母机查询
    "/api/v1/yunxiao/inventory": "read",         # 库存查询
    "/api/v1/yunxiao/sync": "trigger",           # 同步触发
    "/api/v1/yunxiao/host-machines/history": "read",  # 历史
    # ── wecom ──
    "/api/v1/wecom/callback": "notify",   # 企微回调（通知类）
}


# 路径 → 触发的元操作类型
_TRIGGER_PATH_KEYWORDS = ("/sync", "/transition", "/push", "/retry", "/resend")


# 路径 → 删除的元操作类型
_DELETE_PATH_KEYWORDS = ("/delete", "/remove")


def _classify_op(method: str, path: str) -> str:
    """根据 HTTP 方法 + 路径分类元操作。"""
    method = method.upper()
    path_lower = path.lower()

    # 1. 路径关键字优先判断（最高优先级）
    for kw in _TRIGGER_PATH_KEYWORDS:
        if kw in path_lower:
            return "trigger"
    for kw in _DELETE_PATH_KEYWORDS:
        if kw in path_lower:
            return "delete"

    # 2. 路径前缀覆盖（但写方法不受 read 前缀覆盖）
    for prefix, op in PATH_OP_OVERRIDES.items():
        if path.startswith(prefix):
            # 写方法（POST/PUT/PATCH/DELETE）不应被 read 前缀降级为 read
            if method in ("POST", "PUT", "PATCH", "DELETE") and op == "read":
                return {
                    "POST": "write",
                    "PUT": "write",
                    "PATCH": "write",
                    "DELETE": "delete",
                }[method]
            return op

    # 3. 默认按 HTTP 方法
    return {
        "POST": "write",
        "PUT": "write",
        "PATCH": "write",
        "DELETE": "delete",
        "GET": "read",
    }.get(method, "read")


def _build_guards_for_op(op_type: str) -> list:
    """根据元操作类型构造默认 Guard 链。"""
    guards: list = [audit_log()]

    if op_type == "delete":
        guards.append(soft_delete())
    elif op_type == "write":
        guards.append(version_check())
    elif op_type == "trigger":
        guards.append(version_check())
        guards.append(idempotency())
    elif op_type == "read":
        guards.append(result_limit(max_items=1000))

    return guards


class HarnessMiddleware(BaseHTTPMiddleware):
    """全局 Harness 中间件。

    PoC 行为（不影响现有功能）：
    1. 识别 AI Actor（X-Actor-Type=ai header）
    2. 自动给 AI 写/删除/触发操作套上对应 Guard
    3. 业务层如果主动调 Guard，会自动被中间件捕获
    4. Guard 拒绝时返回 422 + 拒绝原因
    5. 所有 AI 调用留痕
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 1. 识别 Actor
        actor = self._extract_actor(request)

        # 2. 非 AI 调用直接放行（人类操作不强制走 Harness）
        if actor.type != ActorType.AI:
            return await call_next(request)

        # 3. AI 调用：识别元操作类型 + 选 Guard
        op_type = _classify_op(request.method, request.url.path)
        guards = _build_guards_for_op(op_type)

        # 4. 留痕（start）
        start = time.monotonic()
        log.info(
            "harness.middleware.ai_request",
            actor_id=actor.id,
            method=request.method,
            path=request.url.path,
            op_type=op_type,
            guards=[g.name for g in guards],
        )

        # 5. 执行 endpoint
        try:
            response = await call_next(request)
        except GuardRejected as e:
            # 业务层 Guard 拒绝（service 层 @guard_chain 主动抛）
            log.warning(
                "harness.middleware.guard_rejected",
                actor_id=actor.id,
                method=request.method,
                path=request.url.path,
                op_type=op_type,
                error=str(e),
                guards_applied=getattr(e, "guards_applied", []),
            )
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=422,
                content={
                    "error": "guard_rejected",
                    "message": str(e),
                    "op_type": op_type,
                    "guards_applied": getattr(e, "guards_applied", []),
                },
            )
        except GuardError as e:
            # 其他 Guard 错误
            log.warning(
                "harness.middleware.guard_error",
                actor_id=actor.id,
                method=request.method,
                path=request.url.path,
                error=str(e),
            )
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=422,
                content={"error": "guard_error", "message": str(e)},
            )
        except Exception as e:
            # 业务异常透传（让上层 exception handler 处理）
            log.error(
                "harness.middleware.unexpected_error",
                actor_id=actor.id,
                method=request.method,
                path=request.url.path,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise

        # 6. 留痕（end）
        duration_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "harness.middleware.ai_response",
            actor_id=actor.id,
            method=request.method,
            path=request.url.path,
            op_type=op_type,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    def _extract_actor(self, request: Request) -> Actor:
        """从 header 提取 Actor。"""
        actor_id = request.headers.get("X-Actor-Id", "anonymous")
        actor_type_str = request.headers.get("X-Actor-Type", "human")
        session_id = request.headers.get("X-Actor-Session", f"sess-{actor_id}")

        try:
            actor_type = ActorType(actor_type_str)
        except ValueError:
            actor_type = ActorType.HUMAN

        return Actor(
            id=actor_id,
            type=actor_type,
            session_id=session_id,
            permissions=["*"] if actor_type == ActorType.HUMAN else [],
            metadata={
                "ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown"),
                "path": request.url.path,
            },
        )
