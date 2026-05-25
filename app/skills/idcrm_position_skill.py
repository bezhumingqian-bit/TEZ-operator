"""IDCRM 机位查询 Skill：自动化查询节点空闲虚拟化机位 + 机位上的设备。

SOP：
1. 打开 IDCRM 机位列表页
2. 筛选条件：
   - 机位逻辑区域属性 = "通用虚拟化bonding区"
   - 机房管理单元 = {idc}（从 zone_mapping 获取）
   - 机位状态 = "空闲"
3. 勾选展示项：机位放置设备(服务器)
4. 点查询 → 提取结果表格
5. 统计空闲机位数 + 提取机位上的固资号

输出：
- free_count: 空闲虚拟化机位数
- occupied_assets: 机位上有设备但状态空闲的固资号（这些设备未上线）
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class IDCRMPositionSkill:
    """数全通机位查询自动化。"""

    WAIT_AFTER_GOTO = 4
    WAIT_AFTER_FILTER = 5

    def __init__(self) -> None:
        self._settings = get_settings()

    async def query_free_positions(self, idc: str) -> dict[str, Any]:
        """查询指定机房的空闲虚拟化机位。

        Args:
            idc: 机房管理单元名称（如"南宁电信朋云路EIC1-30G-V"）

        Returns:
            {free_count, total_rows, occupied_assets, message}
        """
        base_url = self._settings.idcrm_base_url.rstrip("/") + "/db/positions"
        timeout_ms = self._settings.browser_page_timeout_ms

        async with BrowserSession.page() as page:
            # 1. 打开机位列表页
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception as exc:
                log.debug("idcrm_skill.goto_warn", error=str(exc))

            await asyncio.sleep(self.WAIT_AFTER_GOTO)

            # SSO 处理
            if is_login_url(page.url):
                log.warning("idcrm_skill.auth_expired")
                return {"free_count": None, "message": "数全通登录态失效，请扫码登录"}

            # 2. 填筛选条件
            # 机位逻辑区域属性 = 通用虚拟化bonding区
            await self._select_filter(page, "机位逻辑区域", "通用虚拟化bonding")

            # 机房管理单元
            await self._fill_filter(page, "机房管理单元", idc)

            # 机位状态 = 空闲
            await self._select_filter(page, "机位状态", "空闲")

            # 3. 勾选"机位放置设备(服务器)"展示项
            await self._toggle_display_field(page, "机位放置设备")

            await asyncio.sleep(1)

            # 4. 点查询
            try:
                btn = page.locator('button:has-text("查 询"), button:has-text("查询")').first
                await btn.click(timeout=5000)
            except Exception:
                try:
                    await page.locator(".tea-btn--primary").first.click(timeout=3000)
                except Exception:
                    pass

            await asyncio.sleep(self.WAIT_AFTER_FILTER)

            # 5. 提取结果
            rows = await self._extract_table(page)

            # 6. 统计
            free_count = len(rows)
            occupied_assets: list[str] = []
            for row in rows:
                row_text = " ".join(row)
                found = re.findall(r"TYSV[0-9A-Z]{6,}", row_text, re.IGNORECASE)
                occupied_assets.extend(found)

            occupied_assets = list(set(occupied_assets))

            return {
                "free_count": free_count,
                "total_rows": free_count,
                "occupied_assets": occupied_assets,
                "message": f"空闲虚拟化机位: {free_count}, 机位上有设备: {len(occupied_assets)} 台",
            }

    # ─── 内部辅助 ───

    async def _select_filter(self, page, label: str, value: str) -> None:
        """选择下拉筛选项。"""
        try:
            # 找到标签对应的 select/input
            selectors = [
                f'text="{label}" >> .. >> .tea-select',
                f'text="{label}" >> .. >> select',
                f'label:has-text("{label}") >> .. >> .tea-select',
            ]
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if await el.count() > 0:
                        await el.click(timeout=2000)
                        await asyncio.sleep(0.5)
                        # 在弹出的下拉中选择
                        opt = page.locator(f'.tea-select-dropdown li:has-text("{value}"), .tea-option:has-text("{value}")').first
                        if await opt.count() > 0:
                            await opt.click(timeout=2000)
                            await asyncio.sleep(0.5)
                            return
                except Exception:
                    continue
        except Exception as exc:
            log.debug("idcrm_skill.select_filter_failed", label=label, error=str(exc))

    async def _fill_filter(self, page, label: str, value: str) -> None:
        """填入文本筛选框。"""
        try:
            selectors = [
                f'text="{label}" >> .. >> input',
                f'label:has-text("{label}") >> .. >> input',
                f'[placeholder*="{label}"] ',
            ]
            for sel in selectors:
                try:
                    inp = page.locator(sel).first
                    if await inp.count() > 0 and await inp.is_visible(timeout=1000):
                        await inp.fill(value)
                        await asyncio.sleep(0.5)
                        # 如果有下拉建议，选第一个
                        try:
                            suggestion = page.locator(f'.tea-select-dropdown li:has-text("{value}")').first
                            if await suggestion.count() > 0:
                                await suggestion.click(timeout=2000)
                        except Exception:
                            pass
                        return
                except Exception:
                    continue
        except Exception as exc:
            log.debug("idcrm_skill.fill_filter_failed", label=label, error=str(exc))

    async def _toggle_display_field(self, page, field_name: str) -> None:
        """勾选展示字段。"""
        try:
            # 先展开"展开显示项"
            expand_btn = page.locator('text="展开显示项", button:has-text("展开")').first
            if await expand_btn.count() > 0:
                await expand_btn.click(timeout=2000)
                await asyncio.sleep(0.5)

            # 找到并勾选
            checkbox = page.locator(f'label:has-text("{field_name}") input[type="checkbox"], text="{field_name}" >> .. >> input[type="checkbox"]').first
            if await checkbox.count() > 0:
                checked = await checkbox.is_checked()
                if not checked:
                    await checkbox.click(timeout=2000)
        except Exception as exc:
            log.debug("idcrm_skill.toggle_field_failed", field=field_name, error=str(exc))

    async def _extract_table(self, page) -> list[list[str]]:
        """提取结果表格。"""
        selectors = [
            ".tea-table tbody tr",
            ".ant-table-row",
            "table tbody tr",
        ]
        for sel in selectors:
            try:
                rows = await page.eval_on_selector_all(
                    sel,
                    """rows => rows.slice(0, 200).map(r =>
                        Array.from(r.cells || r.children || []).slice(0, 20).map(
                            c => (c.innerText || '').trim()
                        )
                    )""",
                )
                if rows:
                    return [r for r in rows if any(c for c in r)]
            except Exception:
                continue
        return []
