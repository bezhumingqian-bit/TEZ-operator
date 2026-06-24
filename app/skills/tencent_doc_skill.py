"""腾讯文档在线表格写入 Skill：自动化向 OnePage 追加工单数据。

核心操作流程（已校准 2026-05-27）：
1. 打开 OnePage 腾讯文档 URL
2. 切换到目标 Sheet（搬迁记录 / 投放记录）
3. Cmd+End 跳到末尾 → Home 回A列 → ArrowDown 到空行
4. 逐列输入数据（普通列用 Formula Bar，下拉列用专用方法）
5. Tab 跳下一列，腾讯文档自动保存

===== 腾讯文档技术架构（2026-05 调研） =====

渲染层：
- BoardCanvas: 静态背景层（单元格网格、文本内容）
- FeatureCanvas: 动态交互层（选区、高亮、hover）
- DOM 层: 仅用于文本输入和浮层弹窗（下拉菜单等）

关键 DOM 元素：
- Sheet Tab: .tab-bar-item-container
- Name Box: input.bar-label
- Formula Bar: .formula-bar（读取/输入单元格内容）
- 单元格编辑器: #alloy-simple-text-editor（双击或F2后出现的textarea）
- 下拉箭头: 选中有数据验证的单元格后出现（具体class待确认）
- 下拉菜单浮层: 绝对定位高z-index的DOM浮层

数据验证列（下拉单选）操作方式：
- ❌ Formula Bar 输入 + Tab：下拉框拦截，值丢失
- ❌ Alt+ArrowDown：Mac 上浏览器拦截，不可靠
- ✅ F2 进入编辑 → #alloy-simple-text-editor 输入精确匹配文本 → Tab 确认
- ✅ 点击下拉箭头 → 点击 DOM 浮层中的选项

快捷键（Mac）：
| 功能 | 键 |
|------|-----|
| 移至工作表结尾 | Cmd+End |
| 移至工作表开头 | Cmd+Home |
| 进入编辑模式 | F2 |
| 确认并下移 | Enter |
| 确认并右移 | Tab |
| 取消编辑 | Escape |
| 单元格内换行 | Alt+Enter |
| 向上插入行 | Alt+Shift+= |

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

数据验证列（下拉单选）：
- 投放记录: [2]=需求类型(8选项), [5]=投放流程重装(3选项)
- 搬迁记录: [2]=是否紧急, [11]=交付类型(3选项)

投放记录-需求类型选项（截图确认 2026-05-27）：
  ECM导出转到搬迁模块 | ECM-投放计算母机 | TEZ-投放计算母机
  ECM-重装计算母机 | TEZ-投放支撑母机 | TEZ-重装支撑母机

投放记录-投放流程重装选项：
  需要（已确认有带外）| 不需要 已经重装过 | 需要（无带外需要线下重装）

搬迁记录-交付类型选项：
  ECM | TEZ | TEZ裸金属
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.clients.browser_session import BrowserSession, is_login_url, is_doc_login_page
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


# OnePage 文档 URL（从环境变量读取，避免敏感信息入仓）
_settings = get_settings()
ONEPAGE_URL = _settings.tencent_doc_url

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

            # 企微扫码登录检测（URL 不含 login 关键词，需检查页面文本）
            if await is_doc_login_page(page):
                log.warning("tencent_doc.login_expired", url=page.url[:60])
                # 尝试临时弹有头浏览器让用户扫码
                relogin_ok = await self._relogin_with_headful()
                if not relogin_ok:
                    return {
                        "success": False,
                        "message": "腾讯文档登录态失效，自动弹窗扫码超时，请手动处理",
                    }
                # 扫码成功，当前 page 已关闭（BrowserSession 被重建），
                # 需要在新的 page 上重新操作 — 返回特殊标记让调用方重试
                log.info("tencent_doc.relogin_success_retry")

            # 重新检查（扫码后 page 可能已过时，重新 goto）
            if await is_doc_login_page(page):
                try:
                    await page.goto(ONEPAGE_URL, wait_until="domcontentloaded", timeout=timeout_ms)
                    await asyncio.sleep(self.WAIT_AFTER_GOTO)
                except Exception:
                    pass
                if await is_doc_login_page(page):
                    return {"success": False, "message": "腾讯文档登录态仍然失效，请手动扫码"}

            # 2. 切换到目标 Sheet
            switched = await self._switch_sheet(page, sheet_name)
            if not switched:
                return {"success": False, "message": f"无法切换到 Sheet: {sheet_name}"}

            name_box = page.locator("input.bar-label")
            formula_bar = page.locator(".formula-bar").first

            # 3. 定位到 A 列连续数据块末尾的下一个空行
            #    腾讯文档不支持 Cmd+ArrowDown 跳到连续块末尾，
            #    改用二分查找法：在 A 列中找到第一个空行的位置。
            name_box = page.locator("input.bar-label")
            formula_bar = page.locator(".formula-bar").first

            # 先用 Cmd+End 获取数据区域的大致范围
            await page.keyboard.press("Meta+End")
            await asyncio.sleep(2)
            last_cell = await name_box.input_value()
            import re
            row_match = re.search(r"(\d+)", last_cell)
            max_row = int(row_match.group(1)) if row_match else 500

            # 二分查找：找 A 列从第 2 行开始第一个空行
            target_row = await self._binary_search_first_empty_row(
                page, name_box, formula_bar, start=2, end=max_row + 1
            )
            log.info("tencent_doc.binary_search_result", target_row=target_row)

            # 如果目标行 >= max_row，说明表格已满，需要先在底部添加新行
            if target_row >= max_row:
                log.info("tencent_doc.table_full, adding rows", target=target_row, max=max_row)
                added = await self._add_rows_at_bottom(page)
                if not added:
                    # 备选方案：通过底部"在底部添加 N 行"输入框
                    try:
                        add_input = page.locator('input[placeholder*="行"]').last
                        if await add_input.count() > 0:
                            await add_input.fill("10")
                            add_confirm = page.get_by_text("添加").last
                            await add_confirm.click(timeout=3000)
                            await asyncio.sleep(2)
                            log.info("tencent_doc.rows_added_by_input")
                            added = True
                    except Exception:
                        pass
                if not added:
                    return {
                        "success": False,
                        "message": f"表格已满（{max_row}行），且自动添加行失败，请手动在腾讯文档底部添加行",
                    }
                await asyncio.sleep(1)

            # 导航到目标行
            await name_box.click(timeout=2000)
            await asyncio.sleep(0.3)
            await name_box.fill(f"A{target_row}")
            await name_box.press("Enter")
            await asyncio.sleep(1)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            target_cell = await name_box.input_value()

            # 提取行号
            actual_row = target_row

            # 安全检查：确认目标行 A 列为空
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
                            await self._dismiss_overlays(page)
                            await formula_bar.click(timeout=5000, force=True)
                            await asyncio.sleep(0.5)
                            await page.keyboard.type(str(value), delay=20)
                            await asyncio.sleep(0.5)
                        # 下拉选择后可能有覆盖层残留，先清理
                        await self._dismiss_overlays(page)
                    else:
                        # 普通列：formula bar 输入
                        await self._dismiss_overlays(page)
                        await formula_bar.click(timeout=5000, force=True)
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

            # 7. 腾讯文档自动保存
            await asyncio.sleep(2)

            # 8. 写入后校验：回到写入行首列，逐列回读对比
            await name_box.click(timeout=2000)
            await asyncio.sleep(0.3)
            await name_box.fill(f"A{actual_row}")
            await name_box.press("Enter")
            await asyncio.sleep(1)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)

            # 逐列读取并对比（只验证有值的列）
            mismatches = []
            col_letter = 'A'
            for i, expected in enumerate(row_data):
                cell_val = (await formula_bar.inner_text()).strip()

                if expected:
                    # 对比：去掉换行符后比较（单元格内换行在formula bar可能显示不同）
                    expected_flat = expected.replace("\n", " ").strip()
                    actual_flat = cell_val.replace("\n", " ").strip()
                    if expected_flat and actual_flat and expected_flat not in actual_flat and actual_flat not in expected_flat:
                        mismatches.append({
                            "col": col_letter,
                            "expected": expected_flat[:30],
                            "actual": actual_flat[:30],
                        })

                # Tab 到下一列读取
                await page.keyboard.press("Tab")
                await asyncio.sleep(0.3)
                col_letter = chr(ord(col_letter) + 1)

                # 只检查前15列（避免超出数据范围）
                if i >= 14:
                    break

            if mismatches:
                log.warning("tencent_doc.dom_mismatch", sheet=sheet_name, row=actual_row, count=len(mismatches))

            # wecom-cli 附加验证（始终执行，综合判断）
            cli_result = await self._verify_via_wecom_cli(sheet_name, row_data, actual_row)
            if cli_result:
                mismatches.extend(cli_result)
                log.warning("tencent_doc.cli_mismatch", sheet=sheet_name, count=len(cli_result))

            if mismatches:
                return {
                    "success": True,
                    "message": f"已写入 {sheet_name} 第 {actual_row} 行，但部分列可能未正确填入",
                    "row": actual_row,
                    "mismatches": mismatches,
                    "warning": f"{len(mismatches)} 列内容可能不一致：" + ", ".join(
                        f"{m['col']}列(期望:{m['expected']})" for m in mismatches[:3]
                    ),
                }

            log.info("tencent_doc.write_verified", sheet=sheet_name, row=actual_row)
            return {
                "success": True,
                "message": f"已成功写入并验证 {sheet_name} 第 {actual_row} 行",
                "row": actual_row,
                "verified": True,
            }

    @staticmethod
    async def _write_op_log(
        action: str, target: str, status: str, message: str = "",
        detail: dict | None = None, workorder_no: str = "",
    ) -> None:
        """写一条运维操作日志到数据库。"""
        try:
            from app.deps import _get_session_factory
            from app.models.op_log import OperationLog
            factory = _get_session_factory()
            async with factory() as session:
                entry = OperationLog(
                    action=action,
                    target=target,
                    status=status,
                    message=message[:500] if message else None,
                    detail=detail,
                    workorder_no=workorder_no or None,
                )
                session.add(entry)
                await session.commit()
        except Exception:
            pass  # 日志写入失败不阻塞主流程

    async def _verify_via_wecom_cli(
        self, sheet_name: str, row_data: list[str], actual_row: int
    ) -> list[dict] | None:
        """用 wecom-cli 读腾讯文档，对比写入的数据是否正确。

        返回 mismatches 列表，如果全部匹配或 CLI 不可用返回 None。
        """
        import json
        import subprocess
        import time
        url = ONEPAGE_URL
        try:
            # 调 wecom-cli（类型 2 获取表格内容）
            p = subprocess.run(
                ["wecom-cli", "doc", "get_doc_content", json.dumps({"url": url, "type": 2})],
                capture_output=True, text=True, timeout=30,
            )
            # 解析 MCP 包装
            outer = json.loads(p.stdout)
            text = outer["result"]["content"][0]["text"]
            inner = json.loads(text) if isinstance(text, str) else text
            if inner.get("errcode") != 0 or not inner.get("content"):
                return None

            # 轮询直到 task_done
            task_id = inner.get("task_id")
            for _ in range(10):
                if inner.get("task_done"):
                    break
                time.sleep(2)
                p2 = subprocess.run(
                    ["wecom-cli", "doc", "get_doc_content",
                     json.dumps({"url": url, "type": 2, "task_id": task_id})],
                    capture_output=True, text=True, timeout=30,
                )
                text2 = json.loads(p2.stdout)["result"]["content"][0]["text"]
                inner = json.loads(text2) if isinstance(text2, str) else text2

            content = inner.get("content", "")
            if not content:
                return None

            # 找 sheet section
            lines = content.split("\n")
            section_start = None
            for i, line in enumerate(lines):
                if line.strip() == sheet_name:
                    section_start = i
                    break
            if section_start is None:
                return None

            # 找最后一行数据（section_start 后第3行开始是数据）
            data_lines = []
            for i in range(section_start + 3, len(lines)):
                line = lines[i].strip()
                if not line or not line.startswith("|"):
                    if data_lines:
                        break
                    continue
                data_lines.append(line)

            if not data_lines:
                return None

            # 取最后一行并解析列值
            last_row = data_lines[-1]
            cols = [c.strip() for c in last_row.split("|")[1:-1]]

            # 对比关键列
            mismatches = []
            key_indices = {0: "日期", 1: "是否紧急", 2: "需求类型", 3: "固资",
                           6: "设备型号", 7: "关联需求", 9: "可用区"}
            for idx, label in key_indices.items():
                if idx >= len(cols):
                    continue
                cli_val = cols[idx].replace("\t", " ").strip()
                expected_val = (row_data[idx] if idx < len(row_data) else "").replace("\t", " ").strip()
                if not expected_val:
                    continue
                if expected_val and cli_val and expected_val not in cli_val and cli_val not in expected_val:
                    mismatches.append({
                        "col": chr(65 + idx),
                        "label": label,
                        "expected": expected_val[:40],
                        "actual": cli_val[:40],
                    })

            log.info("tencent_doc.wecom_cli_verify", sheet=sheet_name, row=actual_row,
                     mismatches=len(mismatches))
            return mismatches if mismatches else None
        except Exception as exc:
            log.debug("tencent_doc.wecom_cli_verify_failed", error=str(exc))
            return None

    async def _binary_search_first_empty_row(
        self, page, name_box, formula_bar, start: int, end: int
    ) -> int:
        """二分查找 A 列中从 start 行开始第一个空行的行号。

        假设数据从 start 行连续到某一行，之后为空。
        通过 Name Box 导航 + 读取 formula_bar 来检查每行。
        约 log2(n) 次检查，500 行约 9 次 ≈ 18 秒。
        """
        low, high = start, end

        while low < high:
            mid = (low + high) // 2
            has_data = await self._check_cell_has_data(page, name_box, formula_bar, f"A{mid}")

            if has_data:
                # mid 有数据 → 第一个空行在 mid+1 ~ high
                low = mid + 1
            else:
                # mid 为空 → 第一个空行在 low ~ mid
                high = mid

        return low

    async def _check_cell_has_data(self, page, name_box, formula_bar, cell: str) -> bool:
        """通过 Name Box 导航到指定单元格，检查是否有数据。"""
        await name_box.click(timeout=2000)
        await asyncio.sleep(0.2)
        await name_box.fill(cell)
        await name_box.press("Enter")
        await asyncio.sleep(0.8)
        value = (await formula_bar.inner_text()).strip()
        return bool(value)

    async def _add_rows_at_bottom(self, page) -> bool:
        """点击腾讯文档底部的"添加"按钮来新增行。"""
        try:
            # 先滚动到底部
            await page.keyboard.press("Meta+End")
            await asyncio.sleep(2)

            # 方法1：找底部的"添加"按钮
            add_btn = page.locator('button:has-text("添加"), a:has-text("添加")').last
            if await add_btn.count() > 0 and await add_btn.is_visible():
                await add_btn.click(timeout=3000)
                await asyncio.sleep(2)
                log.info("tencent_doc.rows_added_by_button")
                return True
        except Exception as exc:
            log.debug("tencent_doc.add_rows_button_v1_failed", error=str(exc))

        try:
            # 方法2：通过 JS 找底部添加区域并点击
            clicked = await page.evaluate("""() => {
                // 找包含"添加"文字的可点击元素
                const els = [...document.querySelectorAll('*')];
                const addEl = els.find(el => {
                    const text = el.innerText || '';
                    return text.includes('添加') && el.offsetHeight > 0 && el.offsetHeight < 50;
                });
                if (addEl) { addEl.click(); return true; }
                return false;
            }""")
            if clicked:
                await asyncio.sleep(2)
                log.info("tencent_doc.rows_added_by_js")
                return True
        except Exception as exc:
            log.debug("tencent_doc.add_rows_button_v2_failed", error=str(exc))

        return False

    async def _dismiss_overlays(self, page) -> None:
        """关闭可能遮挡 formula bar 的覆盖层/弹窗。

        已知会遮挡的元素：
        - #doc-sharebox-container > .content-dialog-container
        注意：不能用 Escape，会取消单元格的输入值！直接用 JS 隐藏。
        """
        try:
            # 隐藏 sharebox dialog（通过 JS 直接隐藏，不影响单元格状态）
            await page.evaluate("""() => {
                const sharebox = document.querySelector('#doc-sharebox-container');
                if (sharebox) sharebox.style.display = 'none';
                // 其他可能的遮挡层
                const dialogs = document.querySelectorAll('.content-dialog-container');
                dialogs.forEach(d => { if (d.offsetParent !== null) d.style.display = 'none'; });
            }""")
            await asyncio.sleep(0.3)
        except Exception:
            pass

    async def _relogin_with_headful(self, timeout: int = 180) -> bool:
        """临时启动有头浏览器让用户扫码登录腾讯文档。

        流程：
        1. 关闭当前无头 BrowserSession（释放 profile 锁）
        2. 启动有头 Chromium 打开腾讯文档（弹窗给用户扫码）
        3. 轮询等待扫码完成（最多 timeout 秒）
        4. 关闭有头浏览器
        5. BrowserSession 下次使用时会自动以无头模式重建

        登录态已持久化进 profile，后续无头浏览器直接复用。
        """
        from pathlib import Path

        log.info("tencent_doc.relogin_headful.start", timeout=timeout)

        # 1. 关闭当前无头浏览器（释放 profile 锁）
        await BrowserSession.close()
        await asyncio.sleep(2)

        # 清理可能残留的 SingletonLock
        profile_dir = Path(self._settings.browser_profile_dir).resolve()
        for lock_file in profile_dir.glob("Singleton*"):
            try:
                lock_file.unlink()
            except Exception:
                pass

        # 2. 启动有头浏览器
        try:
            from playwright.async_api import async_playwright

            pw = await async_playwright().start()
            ctx = await pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,  # 强制有头，弹窗给用户看
                ignore_https_errors=self._settings.browser_ignore_https_errors,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"],
            )

            page = await ctx.new_page()
            await page.goto(ONEPAGE_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # 3. 轮询等待扫码
            waited = 0
            poll_interval = 3
            while waited < timeout:
                if not await is_doc_login_page(page):
                    log.info("tencent_doc.relogin_headful.success", waited=waited)
                    await asyncio.sleep(2)  # 等 cookie 持久化
                    await page.close()
                    await ctx.close()
                    await pw.stop()
                    return True
                await asyncio.sleep(poll_interval)
                waited += poll_interval
                if waited % 30 == 0:
                    log.info("tencent_doc.relogin_headful.waiting", waited=waited)

            # 超时
            log.warning("tencent_doc.relogin_headful.timeout", waited=waited)
            await page.close()
            await ctx.close()
            await pw.stop()
            return False

        except Exception as exc:
            log.error("tencent_doc.relogin_headful.error", error=str(exc))
            return False

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
        """对数据验证列（下拉单选），选择匹配的选项。

        腾讯文档下拉面板结构（来自实际截图 2026-05-27）：
        ┌─────────────────────┐
        │ 搜索选项             │  ← 搜索输入框
        │                     │
        │ 单选                 │  ← 类型标签
        │                     │
        │ [选项A]  [选项B]     │  ← 彩色 pill 按钮（可点击）
        │ [选项C]  ...        │
        └─────────────────────┘

        触发方式：选中单元格后右侧出现 ▼ 箭头，点击箭头打开面板。

        策略：
        1. 点击 ▼ 箭头（DOM 元素）打开下拉面板
        2. 确认面板已打开（通过"单选"文字判断）
        3. 在面板中 get_by_text 点击匹配选项
        4. 降级：F2 进入编辑器直接输入
        """
        try:
            # ─── 步骤1：打开下拉面板 ───
            panel_opened = await self._open_dropdown_panel(page)

            if panel_opened:
                # ─── 步骤2：点击匹配选项 ───
                selected = await self._click_panel_option(page, value)
                if selected:
                    await asyncio.sleep(0.5)
                    return True
                # 没选中，关闭面板
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)

            # ─── 降级：F2 + alloy-simple-text-editor ───
            log.info("tencent_doc.dropdown_fallback_editor", value=value[:20])
            return await self._try_editor_input(page, value)

        except Exception as exc:
            log.error("tencent_doc.dropdown_error", value=value[:20], error=str(exc))
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await asyncio.sleep(0.3)
            return False

    async def _open_dropdown_panel(self, page) -> bool:
        """打开数据验证下拉面板。

        方法：找到 ▼ 箭头并点击，或用其他方式触发。
        验证：面板打开后应能看到 "单选" 文字。
        """
        # 先确保焦点回到表格（从 formula bar 脱离）
        # Escape 退出可能残留的编辑/formula bar 状态
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)
        # 再按一下方向键确保在目标单元格（Escape 不会移动光标）
        # 但 Escape 可能取消了 Tab 的移动？不会，Tab 已经确认了。

        # 方法1：直接找 ▼ 箭头 DOM 元素
        arrow_selectors = [
            "[class*='arrow']",
            "[class*='trigger']",
            "[class*='dropdown'] svg",
            "[class*='select-icon']",
            "[class*='cell-drop']",
            "[class*='dv-trigger']",
            "[class*='validation']",
        ]

        for selector in arrow_selectors:
            try:
                arrows = page.locator(selector)
                count = await arrows.count()
                for idx in range(count):
                    arrow = arrows.nth(idx)
                    if await arrow.is_visible():
                        await arrow.click(timeout=1500)
                        await asyncio.sleep(0.8)
                        # 验证面板是否打开
                        if await self._is_panel_open(page):
                            log.info("tencent_doc.panel_opened", selector=selector)
                            return True
            except Exception:
                continue

        # 方法2：直接单击当前选中单元格区域（可能触发下拉）
        # 因为单元格在 Canvas 上，尝试点击 name_box 中显示的单元格位置
        # 这不太可靠，跳过

        # 方法3：按 Space（某些下拉可以用空格触发）
        await page.keyboard.press("Space")
        await asyncio.sleep(0.8)
        if await self._is_panel_open(page):
            log.info("tencent_doc.panel_opened_by_space")
            return True
        # Space 可能输入了空格，按 Escape 取消
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)

        # 方法4：F2 进入编辑模式（可能自动弹出下拉）
        await page.keyboard.press("F2")
        await asyncio.sleep(0.8)
        if await self._is_panel_open(page):
            log.info("tencent_doc.panel_opened_by_f2")
            return True

        log.warning("tencent_doc.panel_open_failed")
        return False

    async def _is_panel_open(self, page) -> bool:
        """检查下拉面板是否已打开。

        标志：页面中可见 "单选" 文字（下拉面板的类型标签）。
        """
        try:
            # "单选" 是下拉面板中的固定标签文字
            label = page.get_by_text("单选", exact=True)
            if await label.count() > 0:
                for i in range(await label.count()):
                    if await label.nth(i).is_visible():
                        return True
        except Exception:
            pass
        return False

    async def _click_panel_option(self, page, value: str) -> bool:
        """在已打开的下拉面板中，点击匹配的选项 pill。"""
        try:
            # 精确文本匹配
            option = page.get_by_text(value, exact=True)
            count = await option.count()
            for idx in range(count):
                el = option.nth(idx)
                if await el.is_visible():
                    # 排除非面板元素（如 sheet tab、formula bar）
                    # 面板选项通常不是 input/textarea
                    tag = await el.evaluate("el => el.tagName")
                    if tag.lower() in ("input", "textarea"):
                        continue
                    await el.click(timeout=2000)
                    log.info("tencent_doc.option_clicked", value=value[:20])
                    return True

            # 尝试部分匹配（选项文字可能有首尾空格）
            option_partial = page.get_by_text(value)
            count = await option_partial.count()
            for idx in range(count):
                el = option_partial.nth(idx)
                if await el.is_visible():
                    tag = await el.evaluate("el => el.tagName")
                    if tag.lower() in ("input", "textarea"):
                        continue
                    text = (await el.inner_text()).strip()
                    if text == value:
                        await el.click(timeout=2000)
                        log.info("tencent_doc.option_clicked_partial", value=value[:20])
                        return True

            log.warning("tencent_doc.option_not_found", value=value[:20])
        except Exception as exc:
            log.error("tencent_doc.option_click_error", value=value[:20], error=str(exc))
        return False

    async def _try_editor_input(self, page, value: str) -> bool:
        """降级策略：F2 进入编辑 → alloy-simple-text-editor 输入文本。

        腾讯文档双击/F2 后生成 textarea#alloy-simple-text-editor，
        输入精确匹配数据验证选项的文本，Tab 确认时应通过验证。
        """
        try:
            # 确保进入编辑模式（如果还没有的话）
            editor = page.locator("#alloy-simple-text-editor")
            if not (await editor.count() > 0 and await editor.is_visible()):
                await page.keyboard.press("F2")
                await asyncio.sleep(0.8)

            editor = page.locator("#alloy-simple-text-editor")
            if await editor.count() > 0 and await editor.is_visible():
                await editor.fill("")
                await asyncio.sleep(0.2)
                await editor.fill(value)
                await asyncio.sleep(0.5)
                log.info("tencent_doc.editor_input_done", value=value[:20])
                # 外层循环会按 Tab 确认
                return True

            # editor 没出现，用 keyboard.type 作为最后手段
            log.info("tencent_doc.editor_not_found_typing")
            await page.keyboard.type(value, delay=30)
            await asyncio.sleep(0.5)
            return True

        except Exception as exc:
            log.error("tencent_doc.editor_input_failed", value=value[:20], error=str(exc))
            await page.keyboard.press("Escape")
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
