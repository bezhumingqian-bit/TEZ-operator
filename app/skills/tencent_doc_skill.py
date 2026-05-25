"""腾讯文档在线表格写入 Skill：自动化向 OnePage 追加工单数据。

核心操作流程（已校准 2026-05-25）：
1. 打开 OnePage 腾讯文档 URL
2. 切换到目标 Sheet（搬迁记录 / 投放记录）
3. 通过 Name Box 跳转到目标行（追加到末尾）
4. 逐列输入数据（Tab 键跳转下一列）
5. Enter 确认行，腾讯文档自动保存

关键 DOM 元素：
- Sheet Tab: .tab-bar-item-container
- Name Box: input.bar-label
- Formula Bar: .formula-bar（读取单元格内容，用于校验）

搬迁记录列头（21列）：
  [0] 序号  [1] 相关需求  [2] 是否紧急  [3] 预期交付时间
  [4] 搬迁前可用区  [5] 搬迁前机房管理单元  [6] 目的机房管理单元
  [7] 目的可用区  [8] 搬迁数量  [9] 设备型号
  [10] 设备明细（固资号）  [11] 交付类型  [12] 重装需求
  [13] 搬迁到位交付模块  [14] 备注  [15-20] 后续跟进字段

投放记录列头（15列）：
  [0] 日期  [1] 是否紧急  [2] 需求类型  [3] 固资
  [4] 设备数量  [5] 投放流程重装  [6] 设备类型-->VS_Type
  [7] 关联需求  [8] 关联搬迁单  [9] 可用区
  [10] 备注  [11-14] 后续跟进字段
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


# OnePage 文档 URL
ONEPAGE_URL = (
    "https://doc.weixin.qq.com/sheet/e3_ARoAXAZbAKAVzsF8h3sTqONbQmUrD"
    "?scode=AJEAIQdfAAojsFN6C4ARQA7QYwAGY&tab=BB08J2"
)

# Sheet 名称
SHEET_MIGRATION = "搬迁记录"
SHEET_DEPLOYMENT = "投放记录"

# 当前已知的最后一行（需要定期更新或动态检测）
LAST_ROW_MIGRATION = 338
LAST_ROW_DEPLOYMENT = 50  # TODO: 需要实际确认


class TencentDocSkill:
    """腾讯文档在线表格自动化写入。"""

    WAIT_AFTER_GOTO = 5
    WAIT_AFTER_SWITCH_TAB = 2
    WAIT_AFTER_NAVIGATE = 1
    WAIT_AFTER_INPUT = 0.3

    def __init__(self) -> None:
        self._settings = get_settings()

    async def append_migration_record(self, data: dict[str, str]) -> dict[str, Any]:
        """向搬迁记录 Sheet 追加一行数据。

        data 字段（按列顺序）：
        - date: 日期（如 2026/5/25）
        - requirement: 相关需求
        - urgent: 是否紧急（是/否）
        - expected_date: 预期交付时间
        - from_zone: 搬迁前可用区
        - from_idc: 搬迁前机房管理单元
        - to_idc: 目的机房管理单元
        - to_zone: 目的可用区
        - quantity: 搬迁数量
        - device_model: 设备型号
        - assets: 设备明细（固资号）
        - delivery_type: 交付类型
        - reinstall: 重装需求
        - target_module: 搬迁到位交付模块
        - remark: 备注
        """
        # 构造行数据（按列顺序）
        row_data = [
            data.get("date", ""),
            data.get("requirement", ""),
            data.get("urgent", "否"),
            data.get("expected_date", ""),
            data.get("from_zone", ""),
            data.get("from_idc", ""),
            data.get("to_idc", ""),
            data.get("to_zone", ""),
            data.get("quantity", ""),
            data.get("device_model", ""),
            data.get("assets", ""),
            data.get("delivery_type", ""),
            data.get("reinstall", ""),
            data.get("target_module", ""),
            data.get("remark", ""),
        ]

        return await self._append_row(
            sheet_name=SHEET_MIGRATION,
            target_row=LAST_ROW_MIGRATION + 1,
            row_data=row_data,
        )

    async def append_deployment_record(self, data: dict[str, str]) -> dict[str, Any]:
        """向投放记录 Sheet 追加一行数据。

        data 字段（按列顺序）：
        - date: 日期
        - urgent: 是否紧急
        - type: 需求类型
        - assets: 固资
        - quantity: 设备数量
        - reinstall: 投放流程重装
        - vs_type: 设备类型-->VS_Type
        - requirement: 关联需求
        - migration_ref: 关联搬迁单
        - zone: 可用区
        - remark: 备注
        """
        row_data = [
            data.get("date", ""),
            data.get("urgent", "否"),
            data.get("type", ""),
            data.get("assets", ""),
            data.get("quantity", ""),
            data.get("reinstall", ""),
            data.get("vs_type", ""),
            data.get("requirement", ""),
            data.get("migration_ref", ""),
            data.get("zone", ""),
            data.get("remark", ""),
        ]

        return await self._append_row(
            sheet_name=SHEET_DEPLOYMENT,
            target_row=LAST_ROW_DEPLOYMENT + 1,
            row_data=row_data,
        )

    async def _append_row(
        self, sheet_name: str, target_row: int, row_data: list[str]
    ) -> dict[str, Any]:
        """核心方法：打开文档 → 切换Sheet → 跳转到目标行 → 逐列写入数据。"""
        timeout_ms = self._settings.browser_page_timeout_ms

        async with BrowserSession.page() as page:
            # 1. 打开文档
            try:
                await page.goto(ONEPAGE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
            await asyncio.sleep(self.WAIT_AFTER_GOTO)

            if is_login_url(page.url):
                return {"success": False, "message": "腾讯文档登录态失效，请重新登录"}

            # 2. 切换到目标 Sheet
            switched = await self._switch_sheet(page, sheet_name)
            if not switched:
                return {"success": False, "message": f"无法切换到 Sheet: {sheet_name}"}

            # 3. 跳转到目标单元格（A列目标行）
            navigated = await self._navigate_to_cell(page, f"A{target_row}")
            if not navigated:
                return {"success": False, "message": f"无法跳转到单元格 A{target_row}"}

            # 4. 验证目标行是否为空（避免覆盖已有数据）
            cell_value = await self._read_formula_bar(page)
            if cell_value.strip():
                # 目标行有数据，需要找到真正的空行
                log.warning(
                    "tencent_doc.target_row_not_empty",
                    row=target_row,
                    value=cell_value[:20],
                )
                # 尝试往后找空行（最多找50行）
                found_empty = False
                for offset in range(1, 51):
                    check_row = target_row + offset
                    await self._navigate_to_cell(page, f"A{check_row}")
                    val = await self._read_formula_bar(page)
                    if not val.strip():
                        target_row = check_row
                        found_empty = True
                        log.info("tencent_doc.found_empty_row", row=target_row)
                        break

                if not found_empty:
                    return {
                        "success": False,
                        "message": f"在 {sheet_name} 中未找到空行（检查了 {target_row}-{target_row+50} 行）",
                    }

            # 5. 逐列输入数据
            for i, value in enumerate(row_data):
                if i > 0:
                    # Tab 跳转到下一列
                    await page.keyboard.press("Tab")
                    await asyncio.sleep(self.WAIT_AFTER_INPUT)

                if value:
                    await page.keyboard.type(str(value), delay=30)
                    await asyncio.sleep(self.WAIT_AFTER_INPUT)

            # 6. 按 Enter 确认（腾讯文档会自动保存）
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)

            # 7. 验证写入结果
            await self._navigate_to_cell(page, f"A{target_row}")
            verify_value = await self._read_formula_bar(page)

            if verify_value.strip():
                log.info(
                    "tencent_doc.write_success",
                    sheet=sheet_name,
                    row=target_row,
                    first_col=verify_value[:20],
                )
                return {
                    "success": True,
                    "message": f"已成功写入 {sheet_name} 第 {target_row} 行",
                    "row": target_row,
                    "verified_value": verify_value.strip()[:30],
                }
            else:
                return {
                    "success": False,
                    "message": f"写入验证失败：{sheet_name} 第 {target_row} 行仍为空",
                }

    async def _switch_sheet(self, page, sheet_name: str) -> bool:
        """切换到指定的 Sheet tab。"""
        try:
            tab = page.locator(".tab-bar-item-container").filter(has_text=sheet_name).first
            if await tab.count() > 0:
                await tab.click(timeout=3000)
                await asyncio.sleep(self.WAIT_AFTER_SWITCH_TAB)
                log.info("tencent_doc.switch_sheet", sheet=sheet_name)
                return True
            log.warning("tencent_doc.sheet_not_found", sheet=sheet_name)
            return False
        except Exception as exc:
            log.error("tencent_doc.switch_sheet_error", sheet=sheet_name, error=str(exc))
            return False

    async def _navigate_to_cell(self, page, cell_address: str) -> bool:
        """通过 Name Box 跳转到指定单元格。"""
        try:
            name_box = page.locator("input.bar-label")
            await name_box.click(timeout=2000)
            await asyncio.sleep(0.2)
            await name_box.fill(cell_address)
            await name_box.press("Enter")
            await asyncio.sleep(self.WAIT_AFTER_NAVIGATE)
            # 按 Escape 确保焦点从 Name Box 回到单元格
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.2)
            log.debug("tencent_doc.navigate", cell=cell_address)
            return True
        except Exception as exc:
            log.error("tencent_doc.navigate_error", cell=cell_address, error=str(exc))
            return False

    async def _read_formula_bar(self, page) -> str:
        """读取公式栏中当前单元格的值。"""
        try:
            formula_bar = page.locator(".formula-bar").first
            text = await formula_bar.inner_text()
            return text.strip() if text else ""
        except Exception:
            return ""
