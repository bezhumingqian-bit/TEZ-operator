"""CCDB 客户端（三态：mock / api / browser）。

W2：保留 mock + api 占位；browser 模式 W3 再实现（可参考 TCUMBrowserImpl 结构）。
"""

from __future__ import annotations

from typing import Any

from app.clients.base import BrowserAuthExpired, ClientError, ClientMode
from app.clients.ccdb_browser import CCDBBrowserImpl
from app.clients.ccdb_mock import CCDBMockImpl
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class CCDBAPIImpl:
    """公司 CMDB OpenAPI 实现（占位，等 AppID/AppSecret 到位再写）。"""

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        raise NotImplementedError("CCDB api 模式待账号 Q1 到位后接入")

    async def get_by_ip(self, ip: str) -> dict[str, Any] | None:
        raise NotImplementedError("CCDB api 模式待账号 Q1 到位后接入")

    async def list_by_zone(self, zone: str, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError("CCDB api 模式待账号 Q1 到位后接入")

    async def close(self) -> None:
        return None


class CCDBBrowserImplPlaceholder:
    """旧占位实现保留为示例，真实使用见 ``ccdb_browser.CCDBBrowserImpl``。"""

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        raise NotImplementedError("已切换为 ccdb_browser.CCDBBrowserImpl")

    async def get_by_ip(self, ip: str) -> dict[str, Any] | None:
        raise NotImplementedError("已切换为 ccdb_browser.CCDBBrowserImpl")

    async def list_by_zone(self, zone: str, limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError("已切换为 ccdb_browser.CCDBBrowserImpl")

    async def close(self) -> None:
        return None


class CCDBClient:
    """CCDB 客户端代理层。"""

    name = "ccdb"

    def __init__(self, mode: ClientMode | None = None) -> None:
        s = get_settings()
        self.mode: ClientMode = mode or s.ccdb_mode
        self._impl = self._build_impl(self.mode)
        log.info("ccdb.client_init", mode=self.mode)

    def _build_impl(self, mode: ClientMode) -> Any:
        if mode == "mock":
            return CCDBMockImpl()
        if mode == "api":
            return CCDBAPIImpl()
        if mode == "browser":
            return CCDBBrowserImpl()
        raise ClientError(f"未知 CCDB mode: {mode!r}")

    # ──────────────── public ────────────────

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        try:
            return await self._impl.get_by_asset(asset_id)
        except BrowserAuthExpired:
            raise

    async def get_by_ip(self, ip: str) -> dict[str, Any] | None:
        try:
            return await self._impl.get_by_ip(ip)
        except BrowserAuthExpired:
            raise

    async def list_by_zone(self, zone: str, limit: int = 100) -> list[dict[str, Any]]:
        try:
            return await self._impl.list_by_zone(zone, limit)
        except BrowserAuthExpired:
            raise

    async def close(self) -> None:
        impl_close = getattr(self._impl, "close", None)
        if impl_close is not None:
            await impl_close()
