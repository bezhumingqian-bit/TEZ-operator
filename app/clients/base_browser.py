"""浏览器自动化客户端基类。

封装三家上游平台（TCUM/CMDB/IDCRM）的公共 Playwright 操作模式：
表格数据提取、SSO 自动点击、安全取值、状态归一化等。
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.clients.base import BrowserAuthExpired
from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.normalize import normalize_status

log = get_logger(__name__)


class BaseBrowserImpl:
    """上游平台浏览器自动化基类。

    子类需要覆盖/配置：
    - ``_log_prefix``：日志前缀（如 ``tcum_browser``）
    - ``_sso_deadline``：SSO 自动点击超时（秒，默认 120）
    - ``_fetch_wait_until``：page.goto 的 wait_until 参数（默认 ``networkidle``）
    - ``_fetch_js_slice``：eval_on_selector_all 的 JS slice 上限（默认 16）
    - ``_fetch_enable_sso``：是否在 _fetch_rows 中调用 SSO 自动点击（默认 True）
    """

    # ── 类级配置（子类可覆盖）──
    SELECTOR_FALLBACKS: tuple[str, ...] = (
        ".tea-table tbody tr",
        ".ant-table-row",
        "table tbody tr",
    )
    DEFAULT_WAIT_AFTER_GOTO_MS: int = 3500

    _log_prefix: str = "base_browser"
    _sso_deadline: int = 120
    _fetch_wait_until: str = "networkidle"
    _fetch_js_slice: int = 16
    _fetch_enable_sso: bool = True

    def __init__(self) -> None:
        self._settings = get_settings()

    # ── 公共工具方法 ──

    @classmethod
    def _safe_cell(cls, cells: list[str], idx: int) -> str | None:
        """安全取下标单元格，空值/``-`` 返回 ``None``。"""
        if 0 <= idx < len(cells):
            v = (cells[idx] or "").strip()
            if not v or v == "-":
                return None
            return v
        return None

    @classmethod
    def _normalize_status(cls, raw: str | None) -> str | None:
        """状态归一化（委托到单一来源 :mod:`app.utils.normalize`）。"""
        return normalize_status(raw)

    async def close(self) -> None:
        """释放资源（默认空实现，子类按需覆盖）。"""
        return None

    # ── SSO 自动点击 ──

    async def _try_finish_sso_flow(self, page: Any) -> None:
        """在 SSO 登录页自动点击常见按钮（登录/确认/继续等）。"""
        click_terms = (
            "登录", "确认", "确定", "继续", "继续访问",
            "进入", "进入系统", "授权", "同意",
        )
        deadline = asyncio.get_running_loop().time() + self._sso_deadline
        prefix = self._log_prefix

        while is_login_url(page.url) and asyncio.get_running_loop().time() < deadline:
            clicked = False
            for term in click_terms:
                locators = (
                    page.get_by_role("button", name=term),
                    page.get_by_text(term),
                )
                for loc in locators:
                    try:
                        if await loc.count() > 0 and await loc.first.is_visible(timeout=500):
                            log.info(f"{prefix}.sso_click", text=term)
                            await loc.first.click(timeout=3000)
                            await asyncio.sleep(3)
                            clicked = True
                            break
                    except Exception as exc:
                        log.debug(f"{prefix}.sso_click_failed", text=term, error=str(exc))
                if clicked:
                    break
            if not clicked:
                await asyncio.sleep(3)

    # ── 表格数据提取骨架 ──

    async def _fetch_rows(
        self,
        url: str,
        *,
        target_keyword: str = "",
        wait_until: str | None = None,
        enable_sso: bool | None = None,
    ) -> list[list[str]]:
        """打开页面 → SSO 处理 → 提取表格行数据。

        Args:
            url: 目标页面 URL。
            target_keyword: 若提供，只返回包含该关键词的行。
            wait_until: 覆盖默认的 page.goto wait_until 策略。
            enable_sso: 覆盖默认的是否启用 SSO 自动点击。

        Returns:
            二维字符串列表，每个内层列表代表一行单元格文本。
        """
        timeout_ms = self._settings.browser_page_timeout_ms
        wait_until = wait_until or self._fetch_wait_until
        enable_sso = self._fetch_enable_sso if enable_sso is None else enable_sso
        prefix = self._log_prefix
        js_slice = self._fetch_js_slice

        async with BrowserSession.page() as page:
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            except Exception as exc:
                log.debug(f"{prefix}.goto_warn", error=str(exc))

            await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)

            if enable_sso:
                await self._try_finish_sso_flow(page)

            current_url = page.url
            if is_login_url(current_url):
                log.warning(f"{prefix}.auth_expired", url=current_url)
                raise BrowserAuthExpired(
                    f"{prefix} 登录态失效（被踢回 SSO），请重新扫码登录"
                )

            rows: list[list[str]] = []
            for selector in self.SELECTOR_FALLBACKS:
                try:
                    rows = await page.eval_on_selector_all(
                        selector,
                        f"""rows => rows.slice(0, {js_slice}).map(r =>
                            Array.from(r.cells || r.children || []).slice(0, {js_slice}).map(
                                c => (c.innerText || '').trim()
                            )
                        )""",
                    )
                except Exception as exc:
                    log.debug(f"{prefix}.selector_failed", selector=selector, error=str(exc))
                    continue
                if rows:
                    log.debug(f"{prefix}.selector_hit", selector=selector, count=len(rows))
                    break

            if not rows:
                log.info(f"{prefix}.no_rows", url=url)
                return []

            cleaned = [r for r in rows if any(c for c in r)]
            if target_keyword:
                kw = target_keyword.upper()
                hits = [r for r in cleaned if any(kw in c.upper() for c in r)]
                if hits:
                    return hits
            return cleaned
