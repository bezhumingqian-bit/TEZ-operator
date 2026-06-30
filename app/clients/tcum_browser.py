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
from urllib.parse import urlencode

from app.clients.base_browser import BaseBrowserImpl, BrowserAuthExpired
from app.clients.browser_session import BrowserSession, is_login_url
from app.utils.logger import get_logger

log = get_logger(__name__)


class TCUMBrowserImpl(BaseBrowserImpl):
    """TCUM 浏览器自动化实现。

    Note:
        基础 URL 必须从 ``.env`` 的 ``TEZ_TCUM_BASE_URL`` 读取，**不**硬编码内网域名。
    """

    name = "tcum-browser"
    _log_prefix = "tcum_browser"
    _sso_deadline = 120

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

    async def batch_search(self, asset_ids: list[str]) -> list[dict[str, Any]]:
        """批量查询多个固资号（用;拼接一次搜索），并勾选'机器状态'展示列。

        Returns:
            list of parsed row dicts, 每条包含 asset_id/ip/machine_type/status 等字段。
        """
        if not asset_ids:
            return []

        # 用分号拼接所有固资号
        search_key = ";".join(asset_ids)
        url = self._build_search_url(search_key)
        timeout_ms = self._settings.browser_page_timeout_ms

        async with BrowserSession.page(audit_platform="tcum", audit_operation="batch_search") as page:
            try:
                await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception:
                pass

            await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)

            # 自动 iOA 快速登录（无头模式也能完成）
            from app.clients.browser_session import auto_iOA_login

            login_ok = await auto_iOA_login(page, prefix="tcum_browser")
            if not login_ok:
                from app.core.observability import BrowserAuditLogger
                BrowserAuditLogger(platform="tcum", operation="batch_search").mark_login_required(screenshot=page)
                raise BrowserAuthExpired("TCUM 登录态失效（iOA 自动登录失败），请手动扫码登录")

            # 勾选"机器状态"展示列
            await self._enable_machine_status_column(page)

            await asyncio.sleep(2)

            # 设置每页50条（TCUM 最大50条/页）
            # 然后翻页获取全部
            all_rows: list[list[str]] = []
            max_pages = 10

            for page_num in range(max_pages):
                # 提取当前页
                rows: list[list[str]] = []
                for selector in self.SELECTOR_FALLBACKS:
                    try:
                        rows = await page.eval_on_selector_all(
                            selector,
                            """rows => rows.slice(0, 100).map(r =>
                                Array.from(r.cells || r.children || []).slice(0, 16).map(
                                    c => (c.innerText || '').trim()
                                )
                            )""",
                        )
                    except Exception:
                        continue
                    if rows:
                        break

                cleaned = [r for r in rows if any(c for c in r)]
                if not cleaned:
                    break
                all_rows.extend(cleaned)

                # 检查是否有下一页
                try:
                    next_btn = page.locator(
                        ".tea-pagination__btn--next, .ant-pagination-next"
                    ).first
                    if await next_btn.count() == 0:
                        break
                    is_disabled = await next_btn.evaluate(
                        "el => el.disabled || el.classList.contains('disabled') "
                        "|| el.classList.contains('tea-pagination__btn--disabled')"
                    )
                    if is_disabled:
                        break
                    await next_btn.click(timeout=3000)
                    await asyncio.sleep(2)
                    log.debug("tcum_browser.batch_next_page", page=page_num + 2)
                except Exception:
                    break

            log.info(
                "tcum_browser.batch_search_done",
                total_rows=len(all_rows),
                asset_count=len(asset_ids),
            )

            # 解析每行
            results = []
            for row in all_rows:
                parsed = self._parse_row(row)
                if parsed.get("asset_id"):
                    results.append(parsed)
            return results

    async def _enable_machine_status_column(self, page) -> None:
        """在 TCUM 结果页点击设置齿轮 → 勾选'机器状态' → 确定。"""
        try:
            # 点击齿轮/设置按钮
            gear_btn = page.locator(
                "svg[data-icon='setting'], .tea-icon-setting, button:has-text('设置')"
            ).first
            # 备选：右上角的齿轮图标
            if await gear_btn.count() == 0:
                gear_btn = page.locator("[class*='setting'], [class*='gear']").first
            if await gear_btn.count() == 0:
                # 再试试通过位置找
                gear_btn = page.locator(
                    ".tc-15-table-panel-head .tc-15-bubble-icon, .tea-icon-cog"
                ).first

            if await gear_btn.count() > 0:
                await gear_btn.click(timeout=3000)
                await asyncio.sleep(1)

                # 勾选"机器状态" checkbox
                status_cb = page.locator("text=机器状态").first
                if await status_cb.count() > 0:
                    # 检查是否已经勾选
                    is_checked = await page.evaluate('''() => {
                        const labels = document.querySelectorAll(
                            'label, .ant-checkbox-wrapper, .tea-checkbox'
                        );
                        for (const l of labels) {
                            if (l.innerText.includes('机器状态')) {
                                const input = l.querySelector('input[type=checkbox]');
                                return input ? input.checked : false;
                            }
                        }
                        return false;
                    }''')
                    if not is_checked:
                        await status_cb.click(timeout=2000)
                        await asyncio.sleep(0.5)
                        log.info("tcum_browser.machine_status_checked")

                # 点确定
                confirm_btn = page.locator("button:has-text('确定'), button:has-text('确认')").first
                if await confirm_btn.count() > 0:
                    await confirm_btn.click(timeout=3000)
                    await asyncio.sleep(2)
                    log.info("tcum_browser.settings_confirmed")
            else:
                log.debug("tcum_browser.gear_btn_not_found")
        except Exception as exc:
            log.warning("tcum_browser.enable_status_column_error", error=str(exc))

    async def search_by_ip(self, ip: str) -> dict[str, Any] | None:
        if not ip:
            return None
        url = self._build_search_url(ip)
        rows = await self._fetch_rows(url, target_keyword=ip)
        if not rows:
            return None
        return self._parse_row(rows[0])

    # ──────────────── 内部 ────────────────

    def _build_search_url(self, key: str) -> str:
        base = self._settings.tcum_base_url.rstrip("/")
        return f"{base}/cmdb/product/search?{urlencode({'key': key})}"

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
        status_raw = cls._safe_cell(cells, 10)
        zone = cls._safe_cell(cells, 11)
        use_years_raw = cls._safe_cell(cells, 13) or ""

        return {
            "asset_id": asset_id,
            "ip": ip,
            "idc": zone,  # TCUM 的 zone 列即"机房 / 可用区"，给 HostInfo.idc 用
            "zone": None,  # 内部规范的 zone（如 zone_a）由 CMDB 提供
            "cabinet": None,  # TCUM 不直接给机柜
            "machine_type": machine_type,
            "module": module,
            "status": cls._normalize_status(status_raw),  # W3：采集层归一化中→英
            "city": city,
            "server_type": server_type,
            "owner": owner,
            "backup_owners": cls._split_backup_owners(backup_owners_raw),
            "use_years": cls._strip_year_suffix(use_years_raw),
            "history": [],  # 列表页不含历史，详情页另抓（W3）
            "_source": "tcum-browser",
        }
