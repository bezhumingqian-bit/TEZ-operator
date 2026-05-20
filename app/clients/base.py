"""HTTP 客户端基类与三态枚举。

设计要点
========
- ``ClientMode`` 三态：``mock`` / ``api`` / ``browser``。
  - ``mock``  —— 不发请求，由 Impl 返回固定假数据，用于测试 / 本地无凭据联调。
  - ``api``   —— 走官方 OpenAPI（httpx），W2 阶段 Q1/Q2 账号未到，先占位。
  - ``browser`` —— 走 Playwright 自动化，登录态在 ``data/playwright-profile``。
- 重试：4xx 不重试（`reviewer 建议-6`），仅对 5xx / 网络错误重试。
- 不在日志中打印 token / cookie（参考 docs/16）。
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar, Literal

import httpx

from app.utils.logger import get_logger

log = get_logger(__name__)


# ────────────────── 三态定义 ──────────────────

ClientMode = Literal["mock", "api", "browser"]
"""客户端运行模式。"""


class ClientError(RuntimeError):
    """客户端调用失败的统一异常。"""


class BrowserAuthExpired(ClientError):  # noqa: N818 - 任务包指定的命名
    """浏览器登录态失效（被踢回 SSO 登录页）。

    上层应当：
    1. 记录日志 + 企微告警；
    2. 当前请求降级返回（其他数据源仍可用，HostService 会标 ``partial=True``）；
    3. 通知用户重新扫码登录（参见 ``data/playwright-profile``）。
    """


# ────────────────── HTTP 基类 ──────────────────


class BaseHTTPClient:
    """所有外部 HTTP 客户端的基类（仅在 ``mode == 'api'`` 下使用）。

    设计要点：
    1. 超时使用 httpx 的 timeout，5xx / 网络错误才重试（默认 3 次，指数退避，最大 4s）。
    2. 4xx 直接抛 ``ClientError``，**不重试**（参数错误重试无意义）。
    3. 不在日志里打 token / Authorization header。
    """

    name: ClassVar[str] = "base"

    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: float = 5.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token  # 不打日志
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

    # ──────────────── 生命周期 ────────────────

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> BaseHTTPClient:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    # ──────────────── 请求封装 ────────────────

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """统一请求入口，带重试和日志（不会泄露 token）。

        - 4xx：抛 ``ClientError``，**不重试**（reviewer 建议-6）
        - 5xx / 网络异常：指数退避重试，最多 ``max_retries`` 次
        """

        client = await self._ensure_client()
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                log.debug(
                    "client.request",
                    client=self.name,
                    method=method,
                    path=path,
                    attempt=attempt,
                )
                resp = await client.request(method, path, params=params, json=json)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if 400 <= status < 500:
                    # 4xx 不重试，直接抛
                    log.warning(
                        "client.request_4xx_no_retry",
                        client=self.name,
                        method=method,
                        path=path,
                        status=status,
                    )
                    raise ClientError(
                        f"{self.name} {method} {path} 4xx ({status}), 不重试"
                    ) from exc
                # 5xx 走重试
                last_exc = exc
                log.warning(
                    "client.request_5xx_retry",
                    client=self.name,
                    method=method,
                    path=path,
                    status=status,
                    attempt=attempt,
                )
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_exc = exc
                log.warning(
                    "client.request_failed",
                    client=self.name,
                    method=method,
                    path=path,
                    attempt=attempt,
                    error=str(exc),
                )
            if attempt < self.max_retries:
                await asyncio.sleep(min(2 ** (attempt - 1) * 0.5, 4.0))

        raise ClientError(
            f"{self.name} {method} {path} failed after {self.max_retries} attempts: {last_exc}"
        )
