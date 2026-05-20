"""TCUM Browser 实现 —— 通过 Playwright 自动化爬 TCUM 资源检索页面。

设计来源
========
- PoC 验证报告 docs/15 § 一：``.tea-table tbody tr`` 选择器一次命中
- PoC 实测 12 列顺序（详见 ``_parse_row``）
- 单查 3.6s 平均，登录态 25 cookies 复用稳定

错误处理
========
- 被踢回 SSO 登录页 → 抛 ``BrowserAuthExpired``，HostService 会降级 + 告警
- 选择器超时 → 返回 None（说明无结果或页面结构变化）
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.clients.base import BrowserAuthExpired
from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class TCUMBrowserImpl:
    """TCUM 浏览器自动化实现。

    Note:
        基础 URL 必须从 ``.env`` 的 ``TEZ_TCUM_BASE_URL`` 读取，**不**硬编码内网域名。
    """

    name = "tcum-browser"

    # PoC 已验证（docs/15）
    SELECTOR_TABLE = ".tea-table tbody tr"
    # 备选：万一页面切到 ant-table 也能命中
    SELECTOR_FALLBACKS = (
        ".tea-table tbody tr",
        ".ant-table-row",
        "table tbody tr",
    )

    DEFAULT_WAIT_AFTER_GOTO_MS = 3500  # SPA 渲染等待

    def __init__(self) -> None:
        self._settings = get_settings()

    # ──────────────── public ────────────────

    async def get_by_asset(self, asset_id: str) -> dict[str, Any] | None:
        if not asset_id:
            return None

        # 优先做一次本地登录态快速判断（不阻塞，仅日志）
        if not BrowserSession.is_login_valid():
            log.warning(
                "tcum_browser.login_state_expired_or_missing",
                hint="若浏览器弹窗请扫码登录；profile 路径见 settings.browser_profile_dir",
            )

        url = self._build_search_url(asset_id)
        rows = await self._fetch_rows(url, target_keyword=asset_id)
        if not rows:
            return None
        # 只取第一条（PoC 表明同 asset_id 只会有 1 行）
        return self._parse_row(rows[0])

    async def search_by_ip(self, ip: str) -> dict[str, Any] | None:
        if not ip:
            return None
        url = self._build_search_url(ip)
        rows = await self._fetch_rows(url, target_keyword=ip)
        if not rows:
            return None
        return self._parse_row(rows[0])

    async def close(self) -> None:
        # BrowserSession 是全局单例，由 lifespan 统一关闭
        return None

    # ──────────────── 内部 ────────────────

    def _build_search_url(self, key: str) -> str:
        base = self._settings.tcum_base_url.rstrip("/")
        return f"{base}/cmdb/product/search?key={key}"

    async def _fetch_rows(
        self,
        url: str,
        target_keyword: str = "",
    ) -> list[list[str]]:
        """打开 URL → 等渲染 → 提取 ``.tea-table tbody tr`` 行。

        返回每行的 cells 文本数组。失败 / 无结果 → ``[]``。
        """
        timeout_ms = self._settings.browser_page_timeout_ms

        async with BrowserSession.page() as page:
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception as exc:  # noqa: BLE001
                # networkidle 经常 timeout 但页面其实加载完了，PoC 也是这么处理
                log.debug("tcum_browser.goto_networkidle_warn", error=str(exc))

            # SPA 渲染留点时间
            await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)

            current_url = page.url
            if is_login_url(current_url):
                log.warning("tcum_browser.auth_expired", url=current_url)
                raise BrowserAuthExpired("TCUM 登录态失效（被踢回 SSO），请重新扫码登录")

            # 多选择器降级
            rows: list[list[str]] = []
            for selector in self.SELECTOR_FALLBACKS:
                try:
                    rows = await page.eval_on_selector_all(
                        selector,
                        """rows => rows.slice(0, 16).map(r =>
                            Array.from(r.cells || r.children || []).slice(0, 16).map(
                                c => (c.innerText || '').trim()
                            )
                        )""",
                    )
                except Exception as exc:  # noqa: BLE001
                    log.debug("tcum_browser.selector_failed", selector=selector, error=str(exc))
                    continue
                if rows:
                    log.debug("tcum_browser.selector_hit", selector=selector, count=len(rows))
                    break

            if not rows:
                log.info("tcum_browser.no_rows", url=url)
                return []

            # 过滤掉空行 / 表头干扰
            cleaned = [r for r in rows if any(c for c in r)]
            if target_keyword:
                # 优先返回包含目标关键字的行，避免拿到无关的表头/空行
                hits = [r for r in cleaned if any(target_keyword.upper() in c.upper() for c in r)]
                if hits:
                    return hits
            return cleaned

    # ──────────────── 解析 ────────────────

    @staticmethod
    def _strip_year_suffix(s: str) -> float | None:
        """``"5.9年"`` → ``5.9``。无法解析返回 None。"""
        if not s:
            return None
        cleaned = s.strip().rstrip("年").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _split_backup_owners(s: str) -> list[str]:
        """分号 / 中文分号分隔的备负责人列表。"""
        if not s:
            return []
        # 多种分隔符
        items: list[str] = []
        for chunk in s.replace("；", ";").split(";"):
            v = chunk.strip()
            if v:
                items.append(v)
        return items

    @classmethod
    def _safe_cell(cls, cells: list[str], idx: int) -> str | None:
        if 0 <= idx < len(cells):
            v = (cells[idx] or "").strip()
            # "-" 视为空
            if not v or v == "-":
                return None
            return v
        return None

    @classmethod
    def _parse_row(cls, cells: list[str]) -> dict[str, Any]:
        """把 ``.tea-table tbody tr`` 一行的 cells 映射到 schema。

        列序（PoC 已验证，详见内部文档）：
            [0]  -                 -- 通常是复选框 / 空
            [1]  ip                例如 10.0.0.10（脱敏占位）
            [2]  module            例如 [模块A]-[业务A]
            [3]  asset_id          TYSV...
            [4]  owner             OA 英文名
            [5]  backup_owners     ;-分隔的备负责人列表
            [6]  machine_type      MOCK-1G（脱敏占位）
            [7]  city              城市名
            [8]  -                 占位
            [9]  server_type       Server
            [10] status            运营中 / 维护中 ...
            [11] zone              可用区中文名
            [12] -                 占位
            [13] use_years         "5.9年"

        实际 cells 长度可能不到 14（PoC 报告 cells 截到 12 就停了），所以全部走 ``_safe_cell``。
        """
        ip = cls._safe_cell(cells, 1)
        module = cls._safe_cell(cells, 2)
        asset_id = cls._safe_cell(cells, 3)
        owner = cls._safe_cell(cells, 4)
        backup_owners_raw = cls._safe_cell(cells, 5) or ""
        machine_type = cls._safe_cell(cells, 6)
        city = cls._safe_cell(cells, 7)
        server_type = cls._safe_cell(cells, 9)
        status = cls._safe_cell(cells, 10)
        zone = cls._safe_cell(cells, 11)
        use_years_raw = cls._safe_cell(cells, 13) or ""

        return {
            "asset_id": asset_id,
            "ip": ip,
            "idc": zone,  # TCUM 的 zone 列即"机房 / 可用区"，给 HostInfo.idc 用
            "zone": None,  # 内部规范的 zone（如 ap-shanghai-tea-3）由 CCDB 提供
            "cabinet": None,  # TCUM 不直接给机柜
            "machine_type": machine_type,
            "module": module,
            "status": status,
            "city": city,
            "server_type": server_type,
            "owner": owner,
            "backup_owners": cls._split_backup_owners(backup_owners_raw),
            "use_years": cls._strip_year_suffix(use_years_raw),
            "history": [],  # 列表页不含历史，详情页另抓（W3）
            "_source": "tcum-browser",
        }
