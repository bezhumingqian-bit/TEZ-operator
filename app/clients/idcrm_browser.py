"""IDCRM（数全通）Browser 实现 —— 框架占位。

数全通的页面 PoC 没有抓取样本（docs/15），W4 联调时才能拿到真实页面：
- ``get_position`` 内部 fetch 走通用流程，但 ``_parse_row`` 当前 raise NotImplementedError
- 上层 HostService 已能处理客户端异常（partial 降级）

W4 验收阶段拿到真实页面后：
1. 取消 _parse_row 里的 NotImplementedError
2. 根据真实页面调整 ``COL_*`` 索引
3. 填实 ``_build_query_url``
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

from app.clients.base_browser import BaseBrowserImpl, BrowserAuthExpired
from app.clients.browser_session import BrowserSession, is_login_url
from app.utils.logger import get_logger

log = get_logger(__name__)


class IDCRMBrowserImpl(BaseBrowserImpl):
    """数全通浏览器自动化实现（框架占位 —— 真实解析等 W4 联调）。"""

    name = "idcrm-browser"
    _log_prefix = "idcrm_browser"
    _fetch_enable_sso = False

    # W4 真实页面样本：0 机位ID / 1 一级机房 / 2 机房管理单元 / 3 机架编号
    # 4 机位编号 / 5 Module / 6 机位逻辑区域 / 7 机位状态
    COL_IDC = 2
    COL_CABINET = 3
    COL_POSITION = 4
    COL_STATUS = 7
    COL_HAS_TPC = -1

    async def get_position(
        self,
        idc: str,
        cabinet: str | None = None,
        asset_id: str | None = None,
    ) -> dict[str, Any] | None:
        """按 IDC + 机柜 + 固资号 查询机位。

        Raises:
            NotImplementedError: 当前 ``_parse_row`` 未实现，需 W4 联调时补。
        """
        if not idc:
            return None
        url = self._build_query_url(idc=idc, cabinet=cabinet, asset_id=asset_id)
        try:
            rows = await self._fetch_rows(url, target_keyword=asset_id or idc)
        except BrowserAuthExpired:
            raise
        if not rows:
            return None
        log.error(
            "idcrm_browser.parse_not_implemented",
            hint="IDCRM browser 模式待 W4 获取真实页面样本后补齐；当前请保持 TEZ_IDCRM_MODE=mock",
        )
        # _parse_row 会 raise，让 HostService 降级
        return self._parse_row(
            rows[0],
            asset_id=asset_id,
            fallback_idc=idc,
            fallback_cabinet=cabinet,
        )

    # ──────────────── 内部 ────────────────

    def _build_query_url(
        self,
        idc: str,
        cabinet: str | None = None,
        asset_id: str | None = None,
    ) -> str:
        """构造数全通查询 URL。

        Note:
            TODO(W4): 真实查询路径待联调。当前用占位形式构造，便于单测验证。
        """
        base = self._settings.idcrm_base_url.rstrip("/")
        params = {"idc": idc}
        if cabinet:
            params["cabinet"] = cabinet
        if asset_id:
            params["asset_id"] = asset_id
        return f"{base}/db/positions?{urlencode(params)}"

    async def _fetch_rows(
        self,
        url: str,
        target_keyword: str = "",
    ) -> list[list[str]]:
        timeout_ms = self._settings.browser_page_timeout_ms

        async with BrowserSession.page() as page:
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as exc:  # noqa: BLE001
                log.debug("idcrm_browser.goto_networkidle_warn", error=str(exc))

            await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)

            current_url = page.url
            if is_login_url(current_url):
                log.warning("idcrm_browser.auth_expired", url=current_url)
                raise BrowserAuthExpired("数全通登录态失效（被踢回 SSO），请重新扫码登录")

            rows: list[list[str]] = []
            for selector in self.SELECTOR_FALLBACKS:
                try:
                    rows = await page.eval_on_selector_all(
                        selector,
                        """rows => rows.slice(0, 50).map(r =>
                            Array.from(r.cells || r.children || []).slice(0, 24).map(
                                c => (c.innerText || '').trim()
                            )
                        )""",
                    )
                except Exception as exc:  # noqa: BLE001
                    log.debug(
                        "idcrm_browser.selector_failed",
                        selector=selector,
                        error=str(exc),
                    )
                    continue
                if rows:
                    break

            if not rows:
                log.info("idcrm_browser.no_rows", url=url)
                return []

            cleaned = [r for r in rows if any(c for c in r)]
            if target_keyword:
                hits = [r for r in cleaned if any(target_keyword.upper() in c.upper() for c in r)]
                if hits:
                    return hits
            return cleaned

    # ──────────────── 解析 ────────────────

    @staticmethod
    def _parse_has_tpc(status: str | None) -> bool | None:
        if status is None:
            return None
        value = status.strip().lower()
        if value in {"已占用", "已使用", "使用中", "occupied", "used"}:
            return True
        if value in {"空闲", "未使用", "free", "idle"}:
            return False
        return None

    @classmethod
    def _parse_row(
        cls,
        cells: list[str],
        asset_id: str | None = None,
        fallback_idc: str | None = None,
        fallback_cabinet: str | None = None,
    ) -> dict[str, Any]:
        """把数全通页面一行映射到 schema。"""

        return {
            "idc": cls._safe_cell(cells, cls.COL_IDC) or fallback_idc,
            "cabinet": cls._safe_cell(cells, cls.COL_CABINET) or fallback_cabinet,
            "position": cls._safe_cell(cells, cls.COL_POSITION),
            "has_tpc": cls._parse_has_tpc(cls._safe_cell(cells, cls.COL_STATUS)),
            "raw_json": {
                "asset_id": asset_id,
                "source_status": cls._safe_cell(cells, cls.COL_STATUS),
            },
            "_source": "idcrm-browser",
        }
