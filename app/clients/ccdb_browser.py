"""CCDB Browser 实现 —— 通过 Playwright 自动化爬 CCDB（公司 CMDB）页面。

设计来源
========
- PoC 验证（docs/15）：CCDB 也是 Tea Design 框架，``.tea-table tbody tr`` 一次命中
- 复用 ``BrowserSession`` 单例 BrowserContext 与 TCUM 共享登录态
- 字段映射的列序与 PoC TCUM 不同 —— 联调阶段（W4）才能拿到真实页面，
  当前先用占位 + ``# TODO(W4):`` 注释

错误处理
========
- 被踢回 SSO 登录页 → 抛 ``BrowserAuthExpired``（HostService 降级 + 告警）
- 选择器超时 → 返回 None / []
- 4xx 错误页 → log + 返回 None

数据安全
========
- 基础 URL 必须从 ``.env`` 的 ``TEZ_CCDB_BASE_URL`` 读取，不入仓任何真实内网域名
- mock 路径 / api 路径 / browser 路径三态切换由 settings.ccdb_mode 决定
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

from app.clients.base import BrowserAuthExpired
from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class CCDBBrowserImpl:
    """CCDB 浏览器自动化实现。

    Note:
        所有字段索引（``COL_*``）都是占位，W4 联调时根据真实页面调整。
    """

    name = "ccdb-browser"

    SELECTOR_TABLE = ".tea-table tbody tr"
    SELECTOR_FALLBACKS = (
        ".tea-table tbody tr",
        ".ant-table-row",
        "table tbody tr",
    )
    DEFAULT_WAIT_AFTER_GOTO_MS = 3500

    # ── 列序占位（W4 联调时根据真实页面调整）──
    # TODO(W4): 拿到真实 CCDB 列表页 cells 后修正下面所有 COL_* 索引
    COL_ASSET_ID = 1
    COL_IP = 2
    COL_ZONE = 3
    COL_MODULE = 4
    COL_CUSTOMER = 5
    COL_APP_ID = 6
    COL_MACHINE_TYPE = 7
    COL_STATUS = 8
    COL_IDC = 9
    COL_CABINET = 10
    COL_HAS_TPC = 11

    def __init__(self) -> None:
        self._settings = get_settings()

    # ──────────────── public ────────────────

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        if not asset_id:
            return None
        if not BrowserSession.is_login_valid():
            log.warning(
                "ccdb_browser.login_state_expired_or_missing",
                hint="若浏览器弹窗请扫码登录；profile 路径见 settings.browser_profile_dir",
            )
        url = self._build_search_url(asset_id)
        rows = await self._fetch_rows(url, target_keyword=asset_id)
        if not rows:
            return None
        return self._parse_row(rows[0])

    async def get_by_ip(self, ip: str) -> dict[str, Any] | None:
        if not ip:
            return None
        url = self._build_search_url(ip)
        rows = await self._fetch_rows(url, target_keyword=ip)
        if not rows:
            return None
        return self._parse_row(rows[0])

    async def list_by_zone(self, zone: str, limit: int = 100) -> list[dict[str, Any]]:
        if not zone:
            return []
        url = self._build_zone_url(zone)
        rows = await self._fetch_rows(url)
        if not rows:
            return []
        # 去掉表头/空行干扰，最多取 limit
        parsed = [self._parse_row(r) for r in rows[:limit]]
        # 过滤掉 asset_id 为空的（通常是表头）
        return [p for p in parsed if p.get("asset_id")]

    async def close(self) -> None:
        return None

    # ──────────────── 内部 ────────────────

    def _build_search_url(self, key: str) -> str:
        """构造按 key（固资号/IP）搜索 URL。

        Note:
            TODO(W4): 真实 CCDB 的 search 路径可能不是 ``/search`` —— 联调时改
        """
        base = self._settings.ccdb_base_url.rstrip("/")
        return f"{base}/search?{urlencode({'key': key})}"

    def _build_zone_url(self, zone: str) -> str:
        """按 zone 列出母机的 URL。

        Note:
            TODO(W4): 真实 CCDB 的 zone 列表入口待联调
        """
        base = self._settings.ccdb_base_url.rstrip("/")
        return f"{base}/zone?{urlencode({'zone': zone})}"

    async def _fetch_rows(
        self,
        url: str,
        target_keyword: str = "",
    ) -> list[list[str]]:
        """打开 URL → 等渲染 → 提取 ``.tea-table tbody tr`` 行。"""
        timeout_ms = self._settings.browser_page_timeout_ms

        async with BrowserSession.page() as page:
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as exc:  # noqa: BLE001
                log.debug("ccdb_browser.goto_networkidle_warn", error=str(exc))

            await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)

            current_url = page.url
            if is_login_url(current_url):
                log.warning("ccdb_browser.auth_expired", url=current_url)
                raise BrowserAuthExpired("CCDB 登录态失效（被踢回 SSO），请重新扫码登录")

            rows: list[list[str]] = []
            for selector in self.SELECTOR_FALLBACKS:
                try:
                    rows = await page.eval_on_selector_all(
                        selector,
                        """rows => rows.slice(0, 200).map(r =>
                            Array.from(r.cells || r.children || []).slice(0, 16).map(
                                c => (c.innerText || '').trim()
                            )
                        )""",
                    )
                except Exception as exc:  # noqa: BLE001
                    log.debug("ccdb_browser.selector_failed", selector=selector, error=str(exc))
                    continue
                if rows:
                    log.debug("ccdb_browser.selector_hit", selector=selector, count=len(rows))
                    break

            if not rows:
                log.info("ccdb_browser.no_rows", url=url)
                return []

            cleaned = [r for r in rows if any(c for c in r)]
            if target_keyword:
                hits = [r for r in cleaned if any(target_keyword.upper() in c.upper() for c in r)]
                if hits:
                    return hits
            return cleaned

    # ──────────────── 解析 ────────────────

    @classmethod
    def _safe_cell(cls, cells: list[str], idx: int) -> str | None:
        if 0 <= idx < len(cells):
            v = (cells[idx] or "").strip()
            if not v or v == "-":
                return None
            return v
        return None

    @staticmethod
    def _parse_bool(s: str | None) -> bool | None:
        if s is None:
            return None
        v = s.strip().lower()
        if v in {"true", "1", "yes", "y", "是", "有"}:
            return True
        if v in {"false", "0", "no", "n", "否", "无"}:
            return False
        return None

    @classmethod
    def _parse_row(cls, cells: list[str]) -> dict[str, Any]:
        """把 ``.tea-table tbody tr`` 一行映射到 schema。

        Note:
            列序 ``COL_*`` 为占位值，W4 联调时根据真实 CCDB 页面调整。
            当前实现保证：即便列序错，也只是字段错位，不会崩。
        """
        return {
            "asset_id": cls._safe_cell(cells, cls.COL_ASSET_ID),
            "ip": cls._safe_cell(cells, cls.COL_IP),
            "zone": cls._safe_cell(cells, cls.COL_ZONE),
            "module": cls._safe_cell(cells, cls.COL_MODULE),
            "customer": cls._safe_cell(cells, cls.COL_CUSTOMER),
            "app_id": cls._safe_cell(cells, cls.COL_APP_ID),
            "machine_type": cls._safe_cell(cells, cls.COL_MACHINE_TYPE),
            "status": cls._safe_cell(cells, cls.COL_STATUS),
            "idc": cls._safe_cell(cells, cls.COL_IDC),
            "cabinet": cls._safe_cell(cells, cls.COL_CABINET),
            "has_tpc": cls._parse_bool(cls._safe_cell(cells, cls.COL_HAS_TPC)),
            "billing_tags": {},  # TODO(W4): 真实页面如有标签列再补
            "_source": "ccdb-browser",
        }
