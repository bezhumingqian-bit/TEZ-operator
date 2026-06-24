"""数全通（IDCRM）客户端（三态：mock / api / browser）。

负责：机房 + 机柜 → 机位 / TPC 信息。
"""

from __future__ import annotations

from typing import Any

from app.clients.base import BrowserAuthExpired, ClientError, ClientMode
from app.clients.idcrm_browser import IDCRMBrowserImpl
from app.clients.idcrm_mock import IDCRMMockImpl
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class IDCRMAPIImpl:
    async def get_position(
        self,
        idc: str,
        cabinet: str | None = None,
        asset_id: str | None = None,
    ) -> dict[str, Any] | None:
        raise NotImplementedError("IDCRM api 模式待账号到位后接入")

    async def close(self) -> None:
        return None


class IDCRMClient:
    name = "idcrm"

    def __init__(self, mode: ClientMode | None = None) -> None:
        s = get_settings()
        self.mode: ClientMode = mode or s.idcrm_mode
        self._impl = self._build_impl(self.mode)
        log.info("idcrm.client_init", mode=self.mode)

    def _build_impl(self, mode: ClientMode) -> Any:
        if mode == "mock":
            return IDCRMMockImpl()
        if mode == "api":
            return IDCRMAPIImpl()
        if mode == "browser":
            return IDCRMBrowserImpl()
        if mode == "http":
            from app.clients.idcrm_http import IDCRMHttpClient
            return IDCRMHttpClient()
        raise ClientError(f"未知 IDCRM mode: {mode!r}")

    # ──────────────── public ────────────────

    async def get_position(
        self,
        idc: str,
        cabinet: str | None = None,
        asset_id: str | None = None,
    ) -> dict[str, Any] | None:
        try:
            return await self._impl.get_position(idc, cabinet, asset_id)
        except BrowserAuthExpired:
            raise

    async def close(self) -> None:
        impl_close = getattr(self._impl, "close", None)
        if impl_close is not None:
            await impl_close()
