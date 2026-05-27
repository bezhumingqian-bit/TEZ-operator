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

        列顺序（Tab跳转）：
        A: 日期 | B: 相关需求 | C: 是否紧急 | D: 预期交付时间
        E: 搬迁前可用区 | F: 搬迁前机房管理单元
        G: 目的机房管理单元（VLOOKUP公式自动填，跳过）
        H: 目的可用区 | I: 搬迁数量 | J: 设备型号
        K: 设备明细（固资号）| L: 交付类型 | M: 重装需求
        N: 搬迁到位交付模块 | O: 备注
        """
        # M列（重装需求）：TEZ类型固定值
        reinstall_text = data.get("reinstall", "")
        if not reinstall_text or reinstall_text == "否":
            if data.get("delivery_type", "") == "TEZ":
                reinstall_text = "需要安装【tlinux2.2-kvm3.0_kernel-for_qcloud_test】操作系统"

        # N列（搬迁到位交付模块）：TEZ类型固定值（含单元格内换行）
        target_module = data.get("target_module", "")
        if not target_module and data.get("delivery_type", "") == "TEZ":
            target_module = (
                "[N][腾讯云边缘可用区] - [公有云] - [TEZ] - [线下资源][待上线]\n"
                "主备负责人:nalexzhao;cecixxzhang\n"
                "运维部门:腾讯云宿主机部\n"
                "业务部门:互联网业务系统"
            )

        # 构造行数据（按Tab列顺序）
        row_data = [
            data.get("date", ""),              # A: 日期
            data.get("requirement", ""),        # B: 相关需求
            data.get("urgent", "否"),           # C: 是否紧急
            data.get("expected_date", ""),      # D: 预期交付时间
            data.get("from_zone", ""),          # E: 搬迁前可用区
            data.get("from_idc", ""),           # F: 搬迁前机房管理单元
            data.get("to_idc", ""),             # G: 目的机房管理单元（直接传入）
            data.get("to_zone", ""),            # H: 目的可用区
            data.get("quantity", ""),           # I: 搬迁数量
            data.get("device_model", ""),       # J: 设备型号
            data.get("assets", ""),             # K: 设备明细（固资号）
            data.get("delivery_type", "TEZ"),   # L: 交付类型
            reinstall_text,                     # M: 重装需求
            target_module,                      # N: 搬迁到位交付模块
            data.get("remark", ""),             # O: 备注
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
        """核心方法：打开文档 → 切换Sheet → 定位到最后一行下方空行 → 逐列写入数据。

        操作流程（已校准 2026-05-26）：
        1. 打开文档
        2. 切换到目标 Sheet
        3. Cmd+End 跳到最后有数据的单元格
        4. Home 回到该行 A 列
        5. ArrowDown 到下一空行
        6. 逐列输入数据（Tab 跳转下一列）
        7. Enter 确认
        """
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

            name_box = page.locator("input.bar-label")
            formula_bar = page.locator(".formula-bar").first

            # 3. Cmd+End 跳到最后有数据的单元格
            await page.keyboard.press("Meta+End")
            await asyncio.sleep(2)
            last_cell = await name_box.input_value()
            log.info("tencent_doc.last_cell", cell=last_cell)

            # 4. Home 回到该行 A 列
            await page.keyboard.press("Home")
            await asyncio.sleep(1)
            target_cell = await name_box.input_value()
            log.info("tencent_doc.last_data_row", cell=target_cell)

            # 5. 检查当前行 A 列是否有数据（等待 formula bar 充分加载）
            await asyncio.sleep(1)  # 额外等待确保 formula bar 更新
            cell_value = (await formula_bar.inner_text()).strip()
            # 多次读取确认（避免 formula bar 延迟加载导致误判）
            for _ in range(3):
                await asyncio.sleep(0.5)
                check = (await formula_bar.inner_text()).strip()
                if check:
                    cell_value = check
                    break

            if cell_value:
                # A列有数据 → 必须到下一行
                prev_cell = target_cell
                await page.keyboard.press("ArrowDown")
                await asyncio.sleep(1)
                new_cell = await name_box.input_value()

                if new_cell == prev_cell:
                    # ArrowDown 没移动——到了表格末尾
                    # 用 Option+Shift+= 在当前行上方插入新行
                    # 插入后原数据下移，光标跟着走，需要 ArrowUp 回到新空行
                    await page.keyboard.press("Alt+Shift+Equal")
                    await asyncio.sleep(1)
                    await page.keyboard.press("ArrowUp")
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Home")
                    await asyncio.sleep(0.5)
                else:
                    # 成功移到了下一行
                    pass

                target_cell = await name_box.input_value()
            # else: A列为空（可能是格式残留行），直接在此行写入

            # 最终安全检查：确认目标行 A 列确实为空
            await asyncio.sleep(0.5)
            final_check = (await formula_bar.inner_text()).strip()
            if final_check:
                log.error("tencent_doc.safety_abort", cell=target_cell, value=final_check[:20])
                return {
                    "success": False,
                    "message": f"安全中止：目标行 {target_cell} A列有数据 [{final_check[:20]}]，拒绝覆盖",
                }

            log.info("tencent_doc.write_target", cell=target_cell)

            # 提取行号
            import re
            row_match = re.search(r"(\d+)", target_cell)
            actual_row = int(row_match.group(1)) if row_match else 0

            # 6. 逐列输入数据
            #    普通列：formula bar click → type → Tab（确认并跳下一列）
            #    下拉验证列：打开下拉菜单 → 点击匹配选项（DOM 元素）→ Tab
            #    换行：文本中的 \n 用 Alt+Enter 实现单元格内换行
            #
            #    数据验证列索引（下拉单选）：
            #    - 投放记录: [2]=需求类型, [5]=投放流程重装
            #    - 搬迁记录: [2]=是否紧急, [11]=交付类型
            dropdown_indices = (
                {2, 5} if sheet_name == SHEET_DEPLOYMENT else {2, 11}
            )

            for i, value in enumerate(row_data):
                if value:
                    if i in dropdown_indices:
                        # 数据验证列：通过下拉菜单选择选项
                        selected = await self._select_dropdown_option(page, str(value))
                        if not selected:
                            # 降级：尝试 formula bar 方式
                            log.warning("tencent_doc.dropdown_fallback", col=i, value=str(value)[:20])
                            await formula_bar.click(timeout=3000)
                            await asyncio.sleep(0.5)
                            await page.keyboard.type(str(value), delay=20)
                            await asyncio.sleep(0.5)
                    else:
                        # 普通列：formula bar 输入
                        await formula_bar.click(timeout=3000)
                        await asyncio.sleep(0.5)
                        # 处理单元格内换行
                        parts = str(value).split("\n")
                        for j, part in enumerate(parts):
                            if j > 0:
                                await page.keyboard.press("Alt+Enter")
                                await asyncio.sleep(0.3)
                            if part:
                                await page.keyboard.type(part, delay=20)
                                await asyncio.sleep(0.3)
                        await asyncio.sleep(0.5)

                # Tab 跳到下一列（空值也需要Tab跳过该列）
                await page.keyboard.press("Tab")
                await asyncio.sleep(0.5)

            await asyncio.sleep(1)

            # 7. 无需 Enter（最后一个 Tab 已确认）
            # 腾讯文档自动保存
            await asyncio.sleep(2)

            # 8. 验证：用 Cmd+End → Home 回到最后有数据行的A列
            await page.keyboard.press("Meta+End")
            await asyncio.sleep(1)
            await page.keyboard.press("Home")
            await asyncio.sleep(0.5)
            verify_cell = await name_box.input_value()
            verify_value = (await formula_bar.inner_text()).strip()

            if verify_value:
                log.info(
                    "tencent_doc.write_success",
                    sheet=sheet_name,
                    row=actual_row,
                    cell=verify_cell,
                    first_col=verify_value[:20],
                )
                return {
                    "success": True,
                    "message": f"已成功写入 {sheet_name} 第 {actual_row} 行",
                    "row": actual_row,
                    "cell": verify_cell,
                    "verified_value": verify_value[:30],
                }
            else:
                return {
                    "success": False,
                    "message": f"写入验证失败：{sheet_name} 第 {actual_row} 行仍为空",
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

    async def _select_dropdown_option(self, page, value: str) -> bool:
        """对数据验证列（下拉单选），打开下拉菜单并点击匹配的选项。

        流程：
        1. 当前单元格已选中（通过之前的 Tab 到达）
        2. 双击单元格或按 Alt+ArrowDown 打开下拉菜单
        3. 在下拉菜单 DOM 中找到匹配文本的选项并点击
        4. 选中后单元格值即确认

        腾讯文档下拉菜单 DOM 结构（已知选择器，按优先级尝试）：
        - .dv-dropdown-list 容器下的选项元素
        - .editor-dropdown-list 容器
        - 通用 popup/popover 中匹配文本的元素
        """
        try:
            # 尝试打开下拉菜单：Alt+ArrowDown（标准快捷键）
            await page.keyboard.press("Alt+ArrowDown")
            await asyncio.sleep(1)

            # 尝试多种选择器找到下拉选项
            dropdown_selectors = [
                # 腾讯文档数据验证下拉
                ".dv-dropdown-list",
                ".dv-dropdown",
                # 通用下拉/弹出层
                ".editor-dropdown-list",
                ".dropdown-menu",
                ".popup-content",
                "[class*='dropdown']",
                "[class*='select-option']",
            ]

            dropdown_container = None
            for selector in dropdown_selectors:
                locator = page.locator(selector).first
                if await locator.count() > 0 and await locator.is_visible():
                    dropdown_container = locator
                    log.info("tencent_doc.dropdown_found", selector=selector)
                    break

            if dropdown_container:
                # 在下拉容器中找到匹配文本的选项
                option = dropdown_container.get_by_text(value, exact=True)
                if await option.count() > 0:
                    await option.first.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    log.info("tencent_doc.dropdown_selected", value=value[:20])
                    return True

                # exact match 失败，尝试 contains match
                option = dropdown_container.get_by_text(value)
                if await option.count() > 0:
                    await option.first.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    log.info("tencent_doc.dropdown_selected_partial", value=value[:20])
                    return True

            # 方案 B：没找到容器，直接在页面中找可见的匹配文本
            # （下拉菜单可能是 page-level overlay）
            visible_option = page.get_by_text(value, exact=True).first
            if await visible_option.count() > 0 and await visible_option.is_visible():
                await visible_option.click(timeout=3000)
                await asyncio.sleep(0.5)
                log.info("tencent_doc.dropdown_selected_page_level", value=value[:20])
                return True

            # 所有方式都失败
            log.warning("tencent_doc.dropdown_not_found", value=value[:20])
            # 按 Escape 关闭可能打开的下拉菜单
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            return False

        except Exception as exc:
            log.error("tencent_doc.dropdown_error", value=value[:20], error=str(exc))
            # 确保关闭下拉菜单
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await asyncio.sleep(0.3)
            return False

    async def _navigate_to_cell(self, page, cell_address: str) -> bool:
        """通过 Name Box 跳转到指定单元格。

        关键：Name Box 输入地址后按 Enter 跳转，
        然后按 Escape 关闭 Name Box 焦点，再按 F2 进入当前单元格编辑模式。
        这确保后续 type() 输入的内容进入单元格而非 Name Box。
        """
        try:
            name_box = page.locator("input.bar-label")
            await name_box.click(timeout=2000)
            await asyncio.sleep(0.2)
            await name_box.fill(cell_address)
            await name_box.press("Enter")
            await asyncio.sleep(self.WAIT_AFTER_NAVIGATE)
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
