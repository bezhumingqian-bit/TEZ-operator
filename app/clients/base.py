"""HTTP 客户端基类：httpx.AsyncClient + 超时 / 重试 / 日志 / mock 开关。"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import httpx

from app.utils.logger import get_logger

log = get_logger(__name__)


class ClientError(RuntimeError):
    """客户端调用失败的统一异常。"""


class BaseHTTPClient:
    """所有外部 HTTP 客户端的基类。

    设计要点：
    1. ``mock_mode=True`` 时不会真的发出请求，由子类覆盖 ``_mock_*`` 方法。
    2. 超时使用 httpx 的 timeout，默认重试 3 次（指数退避，最大 4s）。
    3. 不在日志里打 token / Authorization header。
    """

    name: ClassVar[str] = "base"

    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: float = 5.0,
        mock_mode: bool = True,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token  # 不打日志
        self.timeout = timeout
        self.mock_mode = mock_mode
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

    async def __aenter__(self) -> "BaseHTTPClient":
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
        """统一请求入口，带重试和日志（不会泄露 token）。"""

        if self.mock_mode:
            raise ClientError(
                f"{self.name}: mock_mode=True 时不应调用 request()，请用客户端高阶方法"
            )

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
        raise ClientError(f"{self.name} {method} {path} failed after {self.max_retries} attempts: {last_exc}")
