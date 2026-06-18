"""云霄平台 — 浏览器自动化（母机管理 / 新机型库存查询）。

使用 Playwright 访问 https://yunxiao.vstation.woa.com/synergy/honeycomb-host。
继承 BaseBrowserImpl 复用 SSO 登录 + 表格提取骨架。
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from app.clients.base_browser import BaseBrowserImpl
from app.clients.browser_session import BrowserSession
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)

_HOST_URL = "https://yunxiao.vstation.woa.com/synergy/honeycomb-host"
_INVENTORY_URL = "https://yunxiao.vstation.woa.com/synergy/beacon-instance-sales-config"


class YunxiaoBrowserImpl(BaseBrowserImpl):
    """云霄平台浏览器自动化实现。

    母机管理页面查已投放母机状态（30 列）；
    新机型库存查询页面查已上线实例库存（15 列）。
    两页都是 Tea UI (.tea-table)，筛选表单是 tea-form 控件。
    """

    _log_prefix = "yunxiao_browser"
    _fetch_js_slice = 128

    async def query_host_machines(
        self,
        zone: str | None = None,
        machine_type: str | None = None,
        instance_family: str | None = None,
    ) -> list[dict]:
        """查询母机管理 — 已投放母机状态。"""
        async with BrowserSession.page() as page:
            await self._navigate_and_login(page, _HOST_URL)

            # 若当前不在母机管理页面（如被重定向），点侧边栏
            if "/honeycomb-host" not in page.url:
                await self._click_sidebar(page, "母机管理")
                await asyncio.sleep(1.5)

            # 设置筛选条件
            await self._set_tea_filter(page, zone=zone, instance_family=instance_family,
                                       machine_type=machine_type)
            await self._click_search(page)

            # 提取表格
            rows = await self._extract_tea_table_rows(page, header_count=30)
            return self._parse_host_rows(rows)

    async def query_inventory(
        self,
        zone: str | None = None,
        instance_family: str | None = None,
        instance_type: str | None = None,
    ) -> list[dict]:
        """查询新机型库存 — 已上线实例库存。"""
        async with BrowserSession.page() as page:
            await self._navigate_and_login(page, _INVENTORY_URL)

            if "/beacon-instance-sales-config" not in page.url:
                await self._click_sidebar(page, "新机型库存查询")
                await asyncio.sleep(1.5)

            await self._set_tea_filter(page, zone=zone, instance_family=instance_family,
                                       instance_type=instance_type)
            await self._click_search(page)

            rows = await self._extract_tea_table_rows(page, header_count=15)
            return self._parse_inventory_rows(rows)

    # ── 内部方法 ──

    async def _navigate_and_login(self, page: Any, url: str) -> None:
        """打开页面，处理 SSO 登录。"""
        timeout_ms = self._settings.browser_page_timeout_ms
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as exc:
            log.warning(f"{self._log_prefix}.goto_warn", error=str(exc))

        await asyncio.sleep(self.DEFAULT_WAIT_AFTER_GOTO_MS / 1000)

        # SSO 登录流
        await self._try_finish_sso_flow(page)

        # 若登录后未自动跳回目标页，重新 goto
        if url not in page.url:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await asyncio.sleep(2)

    async def _click_sidebar(self, page: Any, text: str) -> None:
        """点击侧边栏菜单项。"""
        try:
            locator = page.locator("a").filter(has_text=text).first
            await locator.click(timeout=5000)
        except Exception as exc:
            log.warning(f"{self._log_prefix}.sidebar_click_failed", text=text, error=str(exc))

    async def _set_tea_filter(
        self, page: Any, **kwargs: str | None,
    ) -> None:
        """设置 tea-form 筛选条件。

        筛选条件映射：
        - zone → 可用区下拉框
        - instance_family → 实例族下拉框
        - instance_type → 实例类型下拉框
        - machine_type → 机型输入/选择
        """
        for key, value in kwargs.items():
            if value is None:
                continue
            label_map = {
                "zone": "可用区",
                "instance_family": "实例族",
                "instance_type": "实例类型",
                "machine_type": "机型",
            }
            label = label_map.get(key, key)
            try:
                await self._fill_tea_select(page, label, value)
            except Exception as exc:
                log.warning(f"{self._log_prefix}.filter_failed", key=key, value=value, error=str(exc))

    async def _fill_tea_select(self, page: Any, label: str, value: str) -> None:
        """填写 Tea UI 下拉框或输入框。

        Tea UI 的 Select 组件通常点击触发下拉，然后在弹出层选选项；
        若为普通 input，直接 fill。
        """
        # 先尝试找到 label 对应的输入区域
        # tea-form: .tea-form__item → .tea-form__label + .tea-form__controls
        form_item = page.locator(".tea-form__item").filter(has_text=label).first
        if await form_item.count() == 0:
            # 尝试直接找含 label 文本的输入框父元素
            form_item = page.locator("label").filter(has_text=label).locator("..").first

        if await form_item.count() == 0:
            return

        # 尝试 select 组件（TeaSelect / Select 弹出层）
        select_trigger = form_item.locator(".tea-select__value, .tea-select, [role=combobox], select").first
        if await select_trigger.count() > 0:
            await select_trigger.click(timeout=3000)
            await asyncio.sleep(0.8)
            # 在弹出列表里选对应项
            option = page.locator(".tea-select__option, .tea-list__item, [role=option], li").filter(
                has_text=value
            ).first
            if await option.count() > 0:
                await option.click(timeout=3000)
                await asyncio.sleep(0.5)
            return

        # 尝试普通 input
        inp = form_item.locator("input").first
        if await inp.count() > 0:
            await inp.fill(value, timeout=3000)
            await asyncio.sleep(0.3)

    async def _click_search(self, page: Any) -> None:
        """点击查询/搜索按钮。"""
        search_terms = ("查询", "搜索", "检索")
        for term in search_terms:
            btn = page.get_by_role("button", name=term)
            if await btn.count() > 0:
                await btn.first.click(timeout=3000)
                await asyncio.sleep(2)
                return
        # 兜底
        btns = page.locator("button").filter(has_text="查询")
        if await btns.count() > 0:
            await btns.first.click(timeout=3000)
            await asyncio.sleep(2)

    async def _extract_tea_table_rows(self, page: Any, header_count: int) -> list[list[str]]:
        """提取 tea-table 表格行数据。

        返回二维列表，每行是一行单元格文本。
        """
        # 等待表格渲染
        await page.wait_for_selector(".tea-table tbody tr, .tea-table__body tr", timeout=10000)
        await asyncio.sleep(1)

        rows: list[list[str]] = []
        js_code = """
            (maxRows) => {
                const rows = document.querySelectorAll('.tea-table tbody tr');
                const result = [];
                for (let i = 0; i < Math.min(rows.length, maxRows); i++) {
                    const cells = rows[i].querySelectorAll('td');
                    const row = [];
                    for (let j = 0; j < cells.length; j++) {
                        row.push((cells[j].textContent || '').trim());
                    }
                    result.push(row);
                }
                return result;
            }
        """
        try:
            rows = await page.evaluate(js_code, self._fetch_js_slice)
        except Exception as exc:
            log.warning(f"{self._log_prefix}.table_extract_failed", error=str(exc))

        return rows

    def _parse_host_rows(self, rows: list[list[str]]) -> list[dict]:
        """解析母机管理表格行 → 结构化字典。"""
        results: list[dict] = []
        for row in rows:
            if len(row) < 6:
                continue
            entry = {
                "asset_id": self._safe_cell(row, 0),
                "ip": self._safe_cell(row, 1),
                "instance_family": self._safe_cell(row, 2),
                "device_type": self._safe_cell(row, 3),
                "zone": self._safe_cell(row, 4),
                "logical_zone": self._safe_cell(row, 5),
                "pool": self._safe_cell(row, 6),
                "sale_pool": self._safe_cell(row, 7),
                "module_label": self._safe_cell(row, 8),
                "gpu_available": self._parse_num(self._safe_cell(row, 9)),
                "gpu_total": self._parse_num(self._safe_cell(row, 9), total=True),
                "cpu_available": self._parse_num(self._safe_cell(row, 10)),
                "cpu_total": self._parse_num(self._safe_cell(row, 10), total=True),
                "mem_available": self._parse_num(self._safe_cell(row, 11)),
                "mem_total": self._parse_num(self._safe_cell(row, 11), total=True),
                "disk_available": self._parse_num(self._safe_cell(row, 14)),
                "disk_total": self._parse_num(self._safe_cell(row, 14), total=True),
                "local_disk_available": self._parse_num(self._safe_cell(row, 15)),
                "local_disk_total": self._parse_num(self._safe_cell(row, 15), total=True),
                "is_empty_host": self._safe_cell(row, 16),
                "is_cdh": self._safe_cell(row, 17),
                "exclusive_owner": self._safe_cell(row, 18),
                "tags": self._safe_cell(row, 19),
                "machine_model": self._safe_cell(row, 20),
                "health_score": self._parse_int(self._safe_cell(row, 21)),
                "online_status": self._safe_cell(row, 22),
                "kernel_version": self._safe_cell(row, 23),
                "kernel_version_id": self._safe_cell(row, 24),
                "manufacturer_module": self._safe_cell(row, 25),
                "sale_pool_type": self._safe_cell(row, 26),
                "box_type": self._safe_cell(row, 27),
                "host_updated_at": self._parse_datetime(self._safe_cell(row, 28)),
            }
            results.append(entry)
        return results

    def _parse_inventory_rows(self, rows: list[list[str]]) -> list[dict]:
        """解析新机型库存表格行 → 结构化字典。"""
        results: list[dict] = []
        for row in rows:
            if len(row) < 5:
                continue
            entry = {
                "zone": self._safe_cell(row, 0),
                "instance_family": self._safe_cell(row, 1),
                "instance_type": self._safe_cell(row, 2),
                "status": self._safe_cell(row, 3),
                "pool": self._safe_cell(row, 4),
                "billing_type": self._safe_cell(row, 5),
                "inventory": self._parse_int(self._safe_cell(row, 6)),
                "inventory_threshold": self._parse_int(self._safe_cell(row, 7)),
                "safety_quota": self._parse_int(self._safe_cell(row, 8)),
                "cpu": self._parse_int(self._safe_cell(row, 9)),
                "gpu": self._parse_int(self._safe_cell(row, 10)),
                "storage_block": self._parse_int(self._safe_cell(row, 11)),
                "mem": self._parse_int(self._safe_cell(row, 12)),
                "device_type": self._safe_cell(row, 13),
            }
            results.append(entry)
        return results

    # ── 解析工具 ──

    @staticmethod
    def _parse_num(raw: str | None, total: bool = False) -> float | None:
        """解析"可用/总量"格式，如"10/56"。"""
        if raw is None:
            return None
        parts = raw.split("/")
        idx = 1 if total else 0
        if idx >= len(parts):
            return None
        try:
            return float(parts[idx].strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_int(raw: str | None) -> int | None:
        if raw is None:
            return None
        try:
            return int(raw.strip())
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_datetime(raw: str | None) -> datetime | None:
        if raw is None:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(raw.strip(), fmt)
            except ValueError:
                continue
        return None
