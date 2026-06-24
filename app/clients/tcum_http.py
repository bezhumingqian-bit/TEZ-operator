"""TCUM HTTP 客户端：通过 Playwright 页面上下文调用 CMDB REST API。

原理：先打开 TCUM 搜索页（确保 session），然后用 page.evaluate(fetch()) 调 API。
比 UI 自动化（翻页、提取表格）快 10x+。

核心 API（抓包确认 2026-05-29）：
- POST {cmdb_base}/api/search/search_by_key
  Body: {"key": ["asset1", "asset2"]}
  返回: serverAssetId, serverLanIP, SvrDeviceClassName, BsiPath, EqsName, ...
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class TCUMHttpClient:
    """TCUM/CloudCMDB HTTP API 客户端。"""

    LOGIN_WAIT_TIMEOUT = 120
    CMDB_API_BASE = ""  # 从 settings.cmdb_base_url 读取

    def __init__(self) -> None:
        self._settings = get_settings()
        self._tcum_url = self._settings.tcum_base_url.rstrip("/")
        self._cmdb_base = getattr(self._settings, 'cmdb_base_url', '') or self._tcum_url.replace('tcum', 'cloudcmdb')

    async def batch_search(self, asset_ids: list[str]) -> list[dict[str, Any]]:
        """批量按固资号查询设备信息。

        等效于 TCUMBrowserImpl.batch_search() 但用 HTTP API。
        支持一次查询多个固资号（API 天然支持数组）。

        Returns:
            list of device dicts, 每条含 asset_id/ip/machine_type/module/status 等。
        """
        if not asset_ids:
            return []

        async with BrowserSession.page() as page:
            # 1. 打开 TCUM 确保 session
            if not await self._ensure_session(page):
                raise RuntimeError("TCUM 登录超时")

            # 2. 分批查询（每批 50 个）
            all_devices = []
            batch_size = 50

            for i in range(0, len(asset_ids), batch_size):
                batch = asset_ids[i:i + batch_size]
                devices = await self._search_by_key(page, batch)
                all_devices.extend(devices)
                log.info("tcum_http.batch", num=i // batch_size + 1, found=len(devices))

            return all_devices

    async def search_single(self, asset_id: str) -> dict[str, Any] | None:
        """查询单个固资号。"""
        results = await self.batch_search([asset_id])
        return results[0] if results else None

    async def _ensure_session(self, page) -> bool:
        """确保 TCUM 已登录。"""
        try:
            search_url = f"{self._tcum_url}/cmdb/product/search?key=test"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass

        # SSO 自动登录（headless 模式需要）
        if is_login_url(page.url):
            from app.clients.base_browser import BaseBrowserImpl
            sso = BaseBrowserImpl()
            await sso._try_finish_sso_flow(page)

        if is_login_url(page.url):
            log.info("tcum_http.waiting_for_login")
            waited = 0
            while is_login_url(page.url) and waited < self.LOGIN_WAIT_TIMEOUT:
                await asyncio.sleep(3)
                waited += 3
            if is_login_url(page.url):
                return False
            log.info("tcum_http.login_success", waited=waited)

        await asyncio.sleep(5)
        return True

    async def _search_by_key(self, page, keys: list[str]) -> list[dict[str, Any]]:
        """调用 TCUM 页面的 search_by_key API。"""
        import json
        keys_json = json.dumps(keys)
        # 使用 tcum 自身域名（同源），而非 cmdb_woa
        api_url = f"{self._tcum_url}/api/search/search_by_key"

        try:
            result = await page.evaluate(f"""async () => {{
                try {{
                    const resp = await fetch('{api_url}', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        credentials: 'include',
                        body: JSON.stringify({{key: {keys_json}}})
                    }});
                    return await resp.json();
                }} catch(e) {{
                    return {{error: e.message}};
                }}
            }}""")

            if result.get("error"):
                log.error("tcum_http.fetch_error", error=result["error"])
                return []

            if result.get("code") != 0:
                log.warning("tcum_http.api_error", code=result.get("code"), msg=result.get("message"))
                return []

            # 转换为统一格式（与 TCUMBrowserImpl 输出兼容）
            devices = []
            for item in result.get("data", {}).get("key_values", []):
                devices.append({
                    "asset_id": item.get("serverAssetId", ""),
                    "ip": (item.get("serverLanIP") or [""])[0] if isinstance(item.get("serverLanIP"), list) else item.get("serverLanIP", ""),
                    "machine_type": item.get("SvrDeviceClassName", ""),
                    "module": item.get("BsiPath", "") or item.get("ModName", ""),
                    "status": self._map_status(item.get("EqsName", ""), item.get("EqsId")),
                    "rack": item.get("serverRack", ""),
                    "idc": item.get("IdcName", ""),
                    "operator": item.get("serverOperator", ""),
                })

            return devices

        except Exception as exc:
            log.error("tcum_http.search_failed", error=str(exc))
            return []

    @staticmethod
    def _map_status(eqs_name: str, eqs_id: int | None = None) -> str:
        """将 TCUM 的 EqsName 映射为简单状态。"""
        if not eqs_name:
            return "unknown"
        name_lower = eqs_name.lower()
        if "运营中" in eqs_name or "online" in name_lower:
            return "online"
        elif "维护" in eqs_name or "maintenance" in name_lower:
            return "maintenance"
        elif "故障" in eqs_name or "fault" in name_lower:
            return "offline"
        elif "下线" in eqs_name or "offline" in name_lower:
            return "offline"
        elif "待回收" in eqs_name:
            return "offline"
        else:
            return eqs_name
