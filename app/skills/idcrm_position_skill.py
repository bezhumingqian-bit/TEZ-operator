"""IDCRM 机位查询 Skill：自动化查询节点空闲虚拟化机位 + 机位上的设备。

SOP（已校准 2026-05-25）：
1. 打开 IDCRM 机位列表页
2. 筛选条件（页面上 .ant-select 索引）：
   - [3] 机位逻辑区域属性 = "通用虚拟化bonding区"（搜索型，用 type 输入完整值）
   - [4] 机房管理单元 = {idc}（搜索型，用 type 输入前缀）
   - [5] 机位状态 = "空闲"（少量选项，直接展开点选）
3. 点"查 询"按钮
4. 提取结果表格
5. 统计空闲机位数 + 提取机位上的固资号

输出：
- free_count: 空闲虚拟化机位数
- occupied_assets: 机位上有设备但状态空闲的固资号（这些设备未上线）
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from app.clients.browser_session import is_login_url
from app.skills.ui_skill import UiSkill
from app.utils.logger import get_logger

log = get_logger(__name__)


class IDCRMPositionSkill(UiSkill):
    """数全通机位查询自动化（继承 UiSkill 通用 UI 操作）。"""

    WAIT_AFTER_GOTO = 4
    WAIT_AFTER_FILTER = 8

    # ant-select 在页面上的索引（从0开始）
    IDX_LOGIC_AREA = 3   # 机位逻辑区域属性
    IDX_IDC_UNIT = 4     # 机房管理单元
    IDX_STATUS = 5       # 机位状态

    # 固定筛选值
    LOGIC_AREA_VALUE = "通用虚拟化bonding区"
    STATUS_VALUE = "空闲"

    MAX_RETRY = 2  # 校验失败时最多重试次数

    def __init__(self) -> None:
        self._settings = get_settings()

    async def query_free_positions(self, idc: str) -> dict[str, Any]:
        """查询指定机房的空闲虚拟化机位（带校验 + 重试）。"""
        base_url = self._settings.idcrm_base_url.rstrip("/") + "/db/positions"
        timeout_ms = self._settings.browser_page_timeout_ms

        async with self._get_browser_page() as page:
            # 1. 打开页面
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
            await asyncio.sleep(self.WAIT_AFTER_GOTO)

            if is_login_url(page.url):
                # 首次使用或登录态过期——等待用户在弹出窗口中扫码
                log.info("idcrm_skill.waiting_for_login", url=page.url[:50])
                waited = 0
                while is_login_url(page.url) and waited < self.LOGIN_WAIT_TIMEOUT:
                    await asyncio.sleep(self.LOGIN_POLL_INTERVAL)
                    waited += self.LOGIN_POLL_INTERVAL
                if is_login_url(page.url):
                    return {"free_count": None, "message": "登录超时（等待120秒），请重试"}
                # 登录成功，等待目标页面加载
                log.info("idcrm_skill.login_success", waited=waited)
                await asyncio.sleep(self.WAIT_AFTER_GOTO)

            # 带校验的查询（最多重试 MAX_RETRY 次）
            for attempt in range(1 + self.MAX_RETRY):
                if attempt > 0:
                    log.warning("idcrm_skill.retry", attempt=attempt, reason="校验不通过，刷新重试")
                    try:
                        await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
                    except Exception:
                        pass
                    await asyncio.sleep(self.WAIT_AFTER_GOTO)

                # 1.5 展开显示项 + 勾选"机位放置设备(服务器)"
                await self._enable_device_column(page)

                # 1.6 设置每页显示100条
                await self.set_page_size(page, "100 条/ 页")

                # 2. 填筛选条件
                # 2.1 选择机房管理单元（下拉选择）
                idc_search = idc[:8] if len(idc) > 8 else idc
                ok_idc = await self.ant_select_search(
                    page, self.IDX_IDC_UNIT,
                    search_text=idc_search,
                    exact_match=idc,
                )

                if not ok_idc:
                    log.warning("idcrm_skill.idc_not_found", idc=idc)
                    return {
                        "free_count": None,
                        "idc_not_found": True,
                        "message": f"机房管理单元「{idc}」在数全通中未录入，该可用区可能尚未开区",
                    }

                # 2.2 设置逻辑区（优先展开后输入，降级到 ant-select）
                logic_ok = False
                try:
                    await self.click_expand(page)
                    await asyncio.sleep(1)
                    logic_ok = await self._fill_logic_area_input(page, "虚拟化")
                except Exception:
                    pass

                if not logic_ok:
                    # 降级：直接用 ant-select 设置逻辑区
                    log.info("idcrm_skill.logic_area_fallback_to_select")
                    await self.ant_select_search(
                        page, self.IDX_LOGIC_AREA,
                        search_text="虚拟化",
                        exact_match=self.LOGIC_AREA_VALUE,
                    )
                await asyncio.sleep(1)

                # 3. 点查询按钮
                await self.click_with_fallback(page, ["button:has-text(\"查 询\")", "button:has-text(\"查询\")", ".ant-btn-primary:has-text(\"查\")", "button.ant-btn-primary"])

                # 等待表格加载（最多等 20 秒，每秒检查一次）
                await asyncio.sleep(3)
                for _wait in range(17):
                    try:
                        row_count = await page.evaluate(
                            "() => document.querySelectorAll('table tbody tr').length"
                        )
                        if row_count > 0:
                            await asyncio.sleep(1)
                            log.info("idcrm_skill.table_rows_found", count=row_count, wait_s=3 + _wait)
                            break
                    except Exception:
                        pass
                    await asyncio.sleep(1)
                else:
                    # 检查页面是否显示"共 0 条记录"
                    page_text = await page.evaluate("() => document.body.innerText")
                    if "共 0 条" in page_text:
                        log.info("idcrm_skill.zero_records_confirmed", idc=idc)
                    else:
                        log.warning("idcrm_skill.table_not_loaded", idc=idc)

                # 4. 提取结果（支持翻页）
                rows = await self.extract_all_pages(page)
                total_positions = len(rows)

                # 统计各状态分布 + 提取设备固资号
                free_count = 0
                used_count = 0
                other_count = 0
                unavailable_count = 0
                all_assets: list[str] = []
                free_assets: list[str] = []

                for row in rows:
                    row_text = " ".join(row)

                    # 跳过不可用的机位（不计入总数）
                    if "不可用" in row_text:
                        unavailable_count += 1
                        continue

                    assets = re.findall(r"TYSV[0-9A-Z]{6,}", row_text, re.IGNORECASE)
                    all_assets.extend(assets)

                    # 判断机位状态（在某一列中包含状态关键字）
                    if "空闲" in row_text:
                        free_count += 1
                        free_assets.extend(assets)
                    elif "已用" in row_text:
                        used_count += 1
                    else:
                        other_count += 1

                # 总机位数 = 排除不可用后的数量
                total_positions = free_count + used_count + other_count
                all_assets = list(set(all_assets))
                free_assets = list(set(free_assets))

                if unavailable_count:
                    log.info("idcrm_skill.unavailable_filtered", count=unavailable_count)

                return {
                    "total_positions": total_positions,
                    "free_count": free_count,
                    "used_count": used_count,
                    "other_count": other_count,
                    "all_assets": all_assets,
                    "free_position_assets": free_assets,
                    "verified": True,
                    "message": (
                        f"虚拟化机位总数: {total_positions}, "
                        f"空闲: {free_count}, 已用: {used_count}, 其他: {other_count}, "
                        f"机位上设备总数: {len(all_assets)} 台"
                    ),
                }

            # 不应走到这里
            return {"free_count": None, "message": "查询异常"}

    async def query_all_positions(self) -> dict[str, Any]:
        """查询全部可用区的虚拟化机位（只筛选逻辑区域，不限机房）。

        一次拉取所有 TEZ 机位数据，再按机房管理单元分组。
        适合驾驶舱全量刷新场景。
        """
        base_url = self._settings.idcrm_base_url.rstrip("/") + "/db/positions"
        timeout_ms = self._settings.browser_page_timeout_ms

        async with self._get_browser_page() as page:
            # 1. 打开页面
            try:
                await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
            except Exception:
                pass
            await asyncio.sleep(self.WAIT_AFTER_GOTO)

            # 等待登录
            if is_login_url(page.url):
                log.info("idcrm_skill.waiting_for_login_all")
                waited = 0
                while is_login_url(page.url) and waited < self.LOGIN_WAIT_TIMEOUT:
                    await asyncio.sleep(self.LOGIN_POLL_INTERVAL)
                    waited += self.LOGIN_POLL_INTERVAL
                if is_login_url(page.url):
                    return {"success": False, "message": "登录超时"}
                await asyncio.sleep(self.WAIT_AFTER_GOTO)

            # 2. 展开设备列 + 设置每页100
            await self._enable_device_column(page)
            await self.set_page_size(page, "100 条/ 页")

            # 3. 只筛选逻辑区域 = 通用虚拟化bonding区（不筛选具体机房）
            await self.ant_select_search(
                page, self.IDX_LOGIC_AREA,
                search_text=self.LOGIC_AREA_VALUE,
                exact_match=self.LOGIC_AREA_VALUE,
            )
            await asyncio.sleep(1)

            # 4. 点查询
            await self.click_with_fallback(page, ["button:has-text(\"查 询\")", "button:has-text(\"查询\")", ".ant-btn-primary:has-text(\"查\")", "button.ant-btn-primary"])

            # 等待表格加载
            await asyncio.sleep(3)
            for _wait in range(12):
                try:
                    row_count = await page.evaluate(
                        "() => document.querySelectorAll('table tbody tr, .ant-table-row').length"
                    )
                    if row_count > 0:
                        await asyncio.sleep(1)
                        break
                except Exception:
                    pass
                await asyncio.sleep(1)
            else:
                await asyncio.sleep(5)

            # 5. 提取所有分页（最多50页 = 5000条，足够覆盖全部区域）
            rows = await self.extract_all_pages(page, max_pages=50)
            log.info("idcrm_skill.all_positions_fetched", total=len(rows))

            # 6. 按机房分组统计
            from app.data.zone_mapping import ZONE_IDC_MAPPING
            # 反向映射 IDC → zone
            idc_to_zone = {v: k for k, v in ZONE_IDC_MAPPING.items()}

            results_by_idc: dict[str, dict] = {}
            for row in rows:
                row_text = " ".join(row)
                # 找到匹配的 IDC（检查每一列是否包含已知机房名）
                matched_idc = ""
                for idc_name in idc_to_zone:
                    if idc_name in row_text:
                        matched_idc = idc_name
                        break

                if not matched_idc:
                    continue

                if matched_idc not in results_by_idc:
                    results_by_idc[matched_idc] = {
                        "idc": matched_idc,
                        "zone": idc_to_zone.get(matched_idc, ""),
                        "total_positions": 0,
                        "free_count": 0,
                        "used_count": 0,
                        "all_assets": [],
                    }

                entry = results_by_idc[matched_idc]
                entry["total_positions"] += 1

                assets = re.findall(r"TYSV[0-9A-Z]{6,}", row_text, re.IGNORECASE)
                entry["all_assets"].extend(assets)

                if "空闲" in row_text:
                    entry["free_count"] += 1
                elif "已用" in row_text:
                    entry["used_count"] += 1

            # 去重 assets
            for entry in results_by_idc.values():
                entry["all_assets"] = list(set(entry["all_assets"]))

            return {
                "success": True,
                "total_rows": len(rows),
                "zones_found": len(results_by_idc),
                "results": results_by_idc,
            }

    # ─── 内部辅助方法 ───

    async def _enable_device_column(self, page) -> None:
        """展开显示项面板，勾选'机位放置设备(服务器)'列。"""
        try:
            # 点击"展开显示项"让 checkbox 区域可见
            expand_btn = page.locator("text=展开显示项").first
            if await expand_btn.is_visible():
                await expand_btn.click(timeout=3000)
                await asyncio.sleep(1)
                log.debug("idcrm_skill.expand_display_items")

            # 勾选"机位放置设备(服务器)"
            cb = page.locator(".ant-checkbox-wrapper").filter(has_text="机位放置设备(服务器)").first
            if await cb.is_visible():
                # 检查是否已经勾选
                is_checked = await page.evaluate('''() => {
                    const labels = document.querySelectorAll('.ant-checkbox-wrapper');
                    for (const label of labels) {
                        if (label.innerText.includes('机位放置设备')) {
                            return label.classList.contains('ant-checkbox-wrapper-checked');
                        }
                    }
                    return false;
                }''')
                if not is_checked:
                    await cb.click(timeout=3000)
                    await asyncio.sleep(0.5)
                    log.info("idcrm_skill.device_column_enabled")
                else:
                    log.debug("idcrm_skill.device_column_already_checked")
        except Exception as exc:
            log.warning("idcrm_skill.enable_device_column_error", error=str(exc))

    # ══════════════════════════════════════════════════
    async def _verify_selections(self, page, idc: str) -> bool:
        """校验 3 个筛选框的选中值是否正确。返回 True 表示全部正确。"""
        expected = {
            self.IDX_LOGIC_AREA: self.LOGIC_AREA_VALUE,
            self.IDX_IDC_UNIT: idc,
            self.IDX_STATUS: self.STATUS_VALUE,
        }
        return await self._do_verify(page, expected)

    async def _verify_selections_no_status(self, page, idc: str) -> bool:
        """校验前 2 个筛选框（不含机位状态）。"""
        expected = {
            self.IDX_LOGIC_AREA: self.LOGIC_AREA_VALUE,
            self.IDX_IDC_UNIT: idc,
        }
        return await self._do_verify(page, expected)

    async def _do_verify(self, page, expected: dict[int, str]) -> bool:
        """通用校验逻辑。"""
        all_ok = True
        for idx, expected_val in expected.items():
            try:
                sel = page.locator(".ant-select").nth(idx)
                rendered = sel.locator(".ant-select-selection__rendered").first
                actual = (await rendered.inner_text()).strip()
                # 去掉可能的换行/重复（之前发现 Ant Select 有时会显示 "值\n值"）
                actual_clean = actual.split("\n")[0].strip() if "\n" in actual else actual
                if actual_clean != expected_val:
                    log.error(
                        "idcrm_skill.verify_mismatch",
                        idx=idx,
                        expected=expected_val,
                        actual=actual_clean,
                    )
                    all_ok = False
                else:
                    log.debug("idcrm_skill.verify_ok", idx=idx, value=actual_clean)
            except Exception as exc:
                log.error("idcrm_skill.verify_error", idx=idx, error=str(exc))
                all_ok = False
        return all_ok

    async def _fill_logic_area_input(self, page, text: str = "虚拟化") -> bool:
        """在展开后的"机位逻辑区域"输入框中输入筛选文本。返回是否成功。"""
        # 展开后的筛选区有多个输入框，找"机位逻辑区域"旁边的 input
        try:
            # 方式1: 通过 placeholder 定位
            input_sel = page.locator('input[placeholder*="机位逻辑区域"]').first
            if await input_sel.count() > 0:
                await input_sel.fill(text)
                await asyncio.sleep(0.3)
                # 验证输入是否生效
                actual = await input_sel.input_value()
                if actual:
                    log.info("idcrm_skill.logic_area_filled", text=text, method="placeholder", actual=actual)
                    return True
        except Exception:
            pass

        try:
            # 方式2: 通过 label 文本 + 相邻 input
            filled = await page.evaluate(f"""() => {{
                const labels = [...document.querySelectorAll('span, label, div')];
                const label = labels.find(el => el.innerText.trim().includes('机位逻辑区域'));
                if (!label) return false;
                // 向上找父容器再找 input
                let parent = label.parentElement;
                for (let i = 0; i < 3 && parent; i++) {{
                    const input = parent.querySelector('input');
                    if (input) {{
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(input, '{text}');
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    parent = parent.parentElement;
                }}
                return false;
            }}""")
            if filled:
                log.info("idcrm_skill.logic_area_filled", text=text, method="label_sibling")
                return True
        except Exception:
            pass

        # 方式3：扫描所有 input 找 placeholder 含 "逻辑"
        try:
            inputs = page.locator('input[type="text"], input:not([type])')
            count = await inputs.count()
            for i in range(count):
                inp = inputs.nth(i)
                val = await inp.input_value()
                placeholder = await inp.get_attribute("placeholder") or ""
                if not val and ("逻辑区域" in placeholder or "逻辑" in placeholder):
                    await inp.fill(text)
                    await asyncio.sleep(0.3)
                    actual = await inp.input_value()
                    if actual:
                        log.info("idcrm_skill.logic_area_filled", text=text, method="scan", idx=i)
                        return True
        except Exception:
            pass

        log.warning("idcrm_skill.logic_area_fill_failed")
        return False

        log.warning("idcrm_skill.logic_area_input_not_found")

