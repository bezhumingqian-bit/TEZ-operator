"""API 访问日志中间件。

记录每次 HTTP 请求的完整链路：
- 请求来源 IP、路径、方法、状态码、耗时
- 慢请求（>3s）和错误请求自动告警
- 日志持久化到 data/observability/api_logs/
"""
from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.observability import APIAccessLogger
from app.utils.logger import get_logger

log = get_logger(__name__)

# 不记录日志的路径（健康检查、静态资源等）
_SKIP_PATHS = {"/health", "/favicon.ico"}
_SKIP_PREFIXES = ("/assets/",)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """记录每次 API 请求的访问日志。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # 跳过不需要记录的路径
        if path in _SKIP_PATHS or path.startswith(_SKIP_PREFIXES):
            return await call_next(request)

        start = time.time()
        error_msg = ""

        try:
            response = await call_next(request)
        except Exception as exc:
            error_msg = str(exc)
            # 仍尝试记录，然后重新抛出
            duration_ms = (time.time() - start) * 1000
            logger = APIAccessLogger()
            await logger.log_request(
                method=request.method,
                path=path,
                status_code=500,
                duration_ms=duration_ms,
                client_ip=_get_client_ip(request),
                user_agent=request.headers.get("user-agent", ""),
                error=error_msg,
            )
            raise

        duration_ms = (time.time() - start) * 1000
        logger = APIAccessLogger()
        await logger.log_request(
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=_get_client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            error=error_msg,
        )

        return response


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP（支持反向代理）。"""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host or ""
    return ""
