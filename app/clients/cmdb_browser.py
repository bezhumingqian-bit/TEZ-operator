"""CMDB Browser 实现 —— 通过 Playwright 自动化爬 CMDB（公司 CMDB）页面。

设计来源
========
- PoC 验证（docs/15）：CMDB 也是 Tea Design 框架，``.tea-table tbody tr`` 一次命中
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
- 基础 URL 必须从 ``.env`` 的 ``TEZ_CMDB_BASE_URL`` 读取，不入仓任何真实内网域名
- mock 路径 / api 路径 / browser 路径三态切换由 settings.cmdb_mode 决定
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


class CMDBBrowserImpl:
    """CMDB 浏览器自动化实现。

    Note:
        所有字段索引（``COL_*``）都是占位，W4 联调时根据真实页面调整。
    """

    name = "cmdb-browser"

    SELECTOR_TABLE = ".tea-table tbody tr"
    SELECTOR_FALLBACKS = (
        ".tea-table tbody tr",
        ".ant-table-row",
        "table tbody tr",
    )
    DEFAULT_WAIT_AFTER_GOTO_MS = 3500

    # ── 列序（W4 真实页面样本：/server/query 表头）──
    # 0 服务器固资编号 / 2 固资编号 / 4 状态 / 5 内网IPV4 / 7 维护人
    # 8 备份维护人 / 9 业务模块 / 10 Module / 11 可用区 / 12 机房管理单元
    COL_ASSET_ID = 2
    COL_STATUS = 4
    COL_IP = 5
    COL_OWNER = 7
    COL_BACKUP_OWNERS = 8
    COL_MODULE = 10
    COL_ZONE = 11
    COL_IDC = 12
    COL_CUSTOMER = -1
    COL_APP_ID = -1
    COL_MACHINE_TYPE = -1
    COL_CABINET = -1
    COL_HAS_TPC = -1

    def __init__(self) -> None:
        self._settings = get_settings()

    # ──────────────── public ────────────────

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        if not asset_id:
            return None
        if not BrowserSession.is_login_valid():
            log.warning(
                "cmdb_browser.login_state_expired_or_missing",
                hint="若浏览器弹窗请扫码登录；profile 路径见 settings.browser_profile_dir",
            )
        rows = await self._search_by_form(asset_id)
        if not rows:
            return None
        return self._parse_row(rows[0])

    async def get_by_ip(self, ip: str) -> dict[str, Any] | None:
        if not ip:
            return None
        rows = await self._search_by_form(ip)
        if not rows:
            return None
        return self._parse_row(rows[0])

    async def list_by_zone(self, zone: str, limit: int = 100) -> list[dict[str, Any]]:
        if not zone:
            return []
        rows = await self._search_by_form(zone)
        if not rows:
            return []
        parsed = [self._parse_row(r) for r in rows[:limit]]
        return [p for p in parsed if p.get("asset_id")]

    async def close(self) -> None:
        return None

    async def get_instance_stats_by_zone(self, zone: str) -> dict[str, Any]:
        """区域实例统计 — browser 模式暂不支持（云霄数据源待接入）。"""

        raise NotImplementedError(
            "CMDB browser mode does not support instance stats yet; "
            "cloud instance data source (yunxiao) is not accessible via browser automation"
        )

    # ──────────────── 内部 ────────────────

    def _base_query_url(self) -> str:
        return self._settings.cmdb_base_url.rstrip("/") + "/server/query"

    async def _search_by_form(
        self,
        keyword: str,
    ) -> list[list[str]]:
        """通过表单操作搜索：填输入框 + 点查询按钮 + 读表格。

        CMDB 前端接口 payload 加密（_encData），无法直接 httpx 调用；
        必须走 Playwright 模拟用户操作。
        """

        timeout_ms = self._settings.browser_page_timeout_ms

        async with BrowserSession.page() as page:
            try:
                await page.goto(self._base_query_url(), wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception as exc:  # noqa: BLE001
                log.debug("cmdb_browser.goto_warn", error=str(exc))

            # 等 SPA 渲染
            await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)

            # SSO 中转处理（同 TCUM 逻辑）
            await self._try_finish_sso_flow(page)

            current_url = page.url
            if is_login_url(current_url):
                log.warning("cmdb_browser.auth_expired", url=current_url)
                raise BrowserAuthExpired("CMDB 登录态失效（被踢回 SSO），请重新扫码登录")

            # 填入搜索关键词
            filled = False
            for sel in ('input[placeholder*="多个"]', '.t-input__inner', '.t-textarea__inner', 'textarea'):
                try:
                    inp = page.locator(sel).first
                    if await inp.is_visible(timeout=2000):
                        await inp.fill(keyword)
                        filled = True
                        log.debug("cmdb_browser.input_filled", selector=sel)
                        break
                except Exception:  # noqa: BLE001
                    continue

            if not filled:
                log.warning("cmdb_browser.input_not_found")
                return []

            await asyncio.sleep(0.5)

            # 点查询按钮
            clicked = False
            for sel in ('button:has-text("查询")', 'button:has-text("搜索")', '.t-button--primary'):
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click(timeout=3000)
                        clicked = True
                        break
                except Exception:  # noqa: BLE001
                    continue
            if not clicked:
                # 尝试 Enter
                try:
                    inp = page.locator('input[placeholder*="多个"]').first
                    await inp.press("Enter")
                except Exception:  # noqa: BLE001
                    pass

            # 等查询结果加载
            await asyncio.sleep(5)

            # 提取表格行
            rows: list[list[str]] = []
            for selector in self.SELECTOR_FALLBACKS:
                try:
                    rows = await page.eval_on_selector_all(
                        selector,
                        """rows => rows.slice(0, 200).map(r =>
                            Array.from(r.cells || r.children || []).slice(0, 32).map(
                                c => (c.innerText || '').trim()
                            )
                        )""",
                    )
                except Exception as exc:  # noqa: BLE001
                    log.debug("cmdb_browser.selector_failed", selector=selector, error=str(exc))
                    continue
                if rows:
                    log.debug("cmdb_browser.selector_hit", selector=selector, count=len(rows))
                    break

            if not rows:
                log.info("cmdb_browser.no_rows")
                return []

            # 过滤空行
            cleaned = [r for r in rows if any(c for c in r)]
            # 按关键词过滤目标行
            if keyword:
                hits = [r for r in cleaned if any(keyword.upper() in c.upper() for c in r)]
                if hits:
                    return hits
            return cleaned

    async def _try_finish_sso_flow(self, page) -> None:
        """处理扫码后还需点击确认的 SSO 中转流程。"""

        import re as _re

        click_terms = ("登录", "确认", "确定", "继续", "继续访问", "进入", "进入系统", "授权", "同意")
        deadline = asyncio.get_running_loop().time() + 30
        while is_login_url(page.url) and asyncio.get_running_loop().time() < deadline:
            clicked = False
            for term in click_terms:
                locators = (
                    page.get_by_role("button", name=_re.compile(term, _re.I)),
                    page.get_by_text(_re.compile(term, _re.I)),
                )
                for loc in locators:
                    try:
                        if await loc.count() > 0 and await loc.first.is_visible(timeout=500):
                            await loc.first.click(timeout=3000)
                            await asyncio.sleep(3)
                            clicked = True
                            break
                    except Exception:  # noqa: BLE001
                        pass
                if clicked:
                    break
            if not clicked:
                await asyncio.sleep(3)

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

    @staticmethod
    def _split_people(s: str | None) -> list[str]:
        if not s:
            return []
        import re

        return [x.strip() for x in re.split(r"[;,；、\\s]+", s) if x.strip()]

    @classmethod
    def _parse_row(cls, cells: list[str]) -> dict[str, Any]:
        """把 ``.tea-table tbody tr`` 一行映射到 schema。

        Note:
            列序 ``COL_*`` 为占位值，W4 联调时根据真实 CMDB 页面调整。
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
            "owner": cls._safe_cell(cells, cls.COL_OWNER),
            "backup_owners": cls._split_people(cls._safe_cell(cells, cls.COL_BACKUP_OWNERS)),
            "has_tpc": cls._parse_bool(cls._safe_cell(cells, cls.COL_HAS_TPC)),
            "billing_tags": {},  # TODO(W4): 真实页面如有标签列再补
            "_source": "cmdb-browser",
        }
