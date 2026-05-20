"""TCUM CMDB 客户端（三态：mock / api / browser）。

负责：固资号 → 物理机房 / 机柜 / 机型 / 投放历史。

W2 实现 ``browser`` 模式（Playwright 走真实 TCUM 页面），``api`` 仍占位。
对外仍保持 ``TCUMClient`` 单一入口，内部按 ``mode`` 委托给 Impl。
"""

from __future__ import annotations

from typing import Any

from app.clients.base import BrowserAuthExpired, ClientError, ClientMode
from app.clients.tcum_browser import TCUMBrowserImpl
from app.clients.tcum_mock import TCUMMockImpl
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class TCUMAPIImpl:
    """TCUM 官方 OpenAPI 实现（W2 占位，等账号到位再写）。"""

    name = "tcum-api"

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:  # noqa: D401
        raise NotImplementedError("TCUM api 模式待 OpenAPI 账号到位后接入")

    async def search_by_ip(self, ip: str) -> dict[str, Any] | None:  # noqa: D401
        raise NotImplementedError("TCUM api 模式待 OpenAPI 账号到位后接入")

    async def close(self) -> None:
        return None


class TCUMClient:
    """TCUM 客户端代理层 —— 按 ``mode`` 委托给具体 Impl。"""

    name = "tcum"

    def __init__(self, mode: ClientMode | None = None) -> None:
        s = get_settings()
        self.mode: ClientMode = mode or s.tcum_mode
        self._impl = self._build_impl(self.mode)
        log.info("tcum.client_init", mode=self.mode)

    def _build_impl(self, mode: ClientMode) -> Any:
        if mode == "mock":
            return TCUMMockImpl()
        if mode == "browser":
            return TCUMBrowserImpl()
        if mode == "api":
            return TCUMAPIImpl()
        raise ClientError(f"未知 TCUM mode: {mode!r}")

    # ──────────────── public（兼容旧签名） ────────────────

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        try:
            return await self._impl.get_by_asset(asset_id)
        except BrowserAuthExpired:
            # 透传给 HostService 处理（partial 降级 + 告警）
            raise

    async def search_by_ip(self, ip: str) -> dict[str, Any] | None:
        try:
            return await self._impl.search_by_ip(ip)
        except BrowserAuthExpired:
            raise

    async def close(self) -> None:
        impl_close = getattr(self._impl, "close", None)
        if impl_close is not None:
            await impl_close()
