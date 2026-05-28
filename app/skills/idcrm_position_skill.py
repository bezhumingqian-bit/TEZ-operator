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

from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class IDCRMPositionSkill:
    """数全通机位查询自动化。"""

    WAIT_AFTER_GOTO = 4
    WAIT_AFTER_FILTER = 8
    LOGIN_WAIT_TIMEOUT = 120  # 等待登录最多 120 秒
    LOGIN_POLL_INTERVAL = 3   # 每 3 秒检查一次

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

        async with BrowserSession.page() as page:
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
                await self._set_page_size(page, "100 条/ 页")

                # 2. 填筛选条件（不限机位状态，查全量虚拟化机位）
                ok1 = await self._ant_select_with_search(
                    page, self.IDX_LOGIC_AREA,
                    search_text=self.LOGIC_AREA_VALUE,
                    exact_match=self.LOGIC_AREA_VALUE,
                )
                idc_search = idc[:8] if len(idc) > 8 else idc
                ok2 = await self._ant_select_with_search(
                    page, self.IDX_IDC_UNIT,
                    search_text=idc_search,
                    exact_match=idc,
                )
                # 不再筛选机位状态，查全量

                await asyncio.sleep(1)

                # 2.5 如果机房管理单元选择失败，说明该机房在数全通未录入，直接返回
                if not ok2:
                    log.warning("idcrm_skill.idc_not_found", idc=idc)
                    return {
                        "free_count": None,
                        "idc_not_found": True,
                        "message": f"机房管理单元「{idc}」在数全通中未录入，该可用区可能尚未开区",
                    }

                # 2.6 校验：读取 select 选中值（只校验前两个，不再校验状态）
                verify_ok = await self._verify_selections_no_status(page, idc)
                if not verify_ok:
                    log.error(
                        "idcrm_skill.verify_failed",
                        attempt=attempt + 1,
                        select_ok=[ok1, ok2],
                    )
                    if attempt < self.MAX_RETRY:
                        continue  # 重试
                    else:
                        return {
                            "free_count": None,
                            "message": f"筛选条件校验失败（重试{self.MAX_RETRY}次），请检查数全通页面状态",
                        }

                # 3. 点查询按钮
                await self._click_query_button(page)
                await asyncio.sleep(self.WAIT_AFTER_FILTER)

                # 4. 提取结果（支持翻页）
                rows = await self._extract_all_pages(page)
                total_positions = len(rows)

                # 统计各状态分布 + 提取设备固资号
                free_count = 0
                used_count = 0
                other_count = 0
                all_assets: list[str] = []
                free_assets: list[str] = []

                for row in rows:
                    row_text = " ".join(row)
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

                all_assets = list(set(all_assets))
                free_assets = list(set(free_assets))

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

        async with BrowserSession.page() as page:
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
            await self._set_page_size(page, "100 条/ 页")

            # 3. 只筛选逻辑区域 = 通用虚拟化bonding区（不筛选具体机房）
            await self._ant_select_with_search(
                page, self.IDX_LOGIC_AREA,
                search_text=self.LOGIC_AREA_VALUE,
                exact_match=self.LOGIC_AREA_VALUE,
            )
            await asyncio.sleep(1)

            # 4. 点查询
            await self._click_query_button(page)
            await asyncio.sleep(self.WAIT_AFTER_FILTER)

            # 5. 提取所有分页（最多50页 = 5000条，足够覆盖全部区域）
            rows = await self._extract_all_pages(page, max_pages=50)
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

    async def _set_page_size(self, page, size_text: str = "100 条/ 页") -> None:
        """将分页大小设置为指定值（如100条/页），确保一次获取全部数据。"""
        try:
            page_size_el = page.locator("text=/条.*页/").first
            if await page_size_el.count() > 0:
                current = (await page_size_el.inner_text()).strip()
                if current == size_text:
                    log.debug("idcrm_skill.page_size_already_set", size=size_text)
                    return
                await page_size_el.click(timeout=3000)
                await asyncio.sleep(1)
                opt = page.locator(".ant-select-dropdown-menu-item").filter(has_text=size_text).first
                if await opt.count() > 0:
                    await opt.click(timeout=3000)
                    await asyncio.sleep(1)
                    log.info("idcrm_skill.page_size_set", size=size_text)
        except Exception as exc:
            log.warning("idcrm_skill.set_page_size_error", error=str(exc))

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

    async def _ant_select_with_search(
        self, page, idx: int, search_text: str, exact_match: str
    ) -> bool:
        """操作搜索型 Ant Design Select：点击展开 → type 输入搜索词 → 精确点选选项。
        
        如果首次搜索未找到精确匹配，会尝试用更短的前缀重新搜索。
        """
        # 生成搜索词候选列表（从长到短）
        search_candidates = [search_text]
        if search_text != exact_match:
            search_candidates.append(exact_match)
        # 对于较长的精确值，生成更短的前缀候选
        if len(exact_match) > 6:
            for prefix_len in [len(exact_match), 10, 6, 4]:
                candidate = exact_match[:prefix_len]
                if candidate not in search_candidates:
                    search_candidates.append(candidate)

        for attempt_search in search_candidates:
            try:
                sel = page.locator(".ant-select").nth(idx)
                await sel.click(timeout=3000)
                await asyncio.sleep(0.5)
                inp = sel.locator("input").first
                # 先清空之前可能残留的输入
                await inp.press("Control+a")
                await inp.press("Backspace")
                await asyncio.sleep(0.3)
                await inp.type(attempt_search, delay=50)
                await asyncio.sleep(2)

                # 精确匹配选项
                items = await page.locator(".ant-select-dropdown-menu-item").all()
                for item in items:
                    text = (await item.inner_text()).strip()
                    if text == exact_match:
                        await item.click(timeout=3000)
                        await asyncio.sleep(1)
                        log.info("idcrm_skill.select_search_ok", idx=idx, value=exact_match, search=attempt_search)
                        return True

                # 退而求其次：包含匹配
                for item in items:
                    text = (await item.inner_text()).strip()
                    if exact_match in text:
                        await item.click(timeout=3000)
                        await asyncio.sleep(1)
                        log.info("idcrm_skill.select_search_approx", idx=idx, value=text, search=attempt_search)
                        return True

                # 当前搜索词没匹配到，关闭下拉菜单，尝试下一个候选
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                log.debug("idcrm_skill.select_search_miss", idx=idx, search=attempt_search)

            except Exception as exc:
                log.error("idcrm_skill.select_search_error", idx=idx, search=attempt_search, error=str(exc))

        log.warning("idcrm_skill.select_search_failed", idx=idx, exact_match=exact_match)
        return False

    async def _ant_select_direct(self, page, idx: int, exact_match: str) -> bool:
        """操作简单 Ant Design Select：点击展开 → 直接点选选项（不输入搜索词）。"""
        try:
            sel = page.locator(".ant-select").nth(idx)
            await sel.click(timeout=3000)
            await asyncio.sleep(1)

            items = await page.locator(".ant-select-dropdown-menu-item").all()
            for item in items:
                text = (await item.inner_text()).strip()
                if text == exact_match:
                    await item.click(timeout=3000)
                    await asyncio.sleep(1)
                    log.info("idcrm_skill.select_direct_ok", idx=idx, value=exact_match)
                    return True

            log.warning("idcrm_skill.select_direct_failed", idx=idx, target=exact_match)
            return False
        except Exception as exc:
            log.error("idcrm_skill.select_direct_error", idx=idx, error=str(exc))
            return False

    async def _click_query_button(self, page) -> bool:
        """点击查询按钮，多策略确保点到。"""
        query_selectors = [
            'button:has-text("查 询")',
            'button:has-text("查询")',
            '.ant-btn-primary:has-text("查")',
            'button.ant-btn-primary',
        ]
        for sel in query_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click(timeout=5000)
                    log.info("idcrm_skill.query_btn_clicked", selector=sel)
                    return True
            except Exception:
                continue

        # 兜底：回车
        log.warning("idcrm_skill.query_btn_not_found, trying Enter")
        await page.keyboard.press("Enter")
        return False

    async def _extract_all_pages(self, page, max_pages: int = 10) -> list[list[str]]:
        """提取所有分页的表格数据。如果超过100条会自动翻页。"""
        all_rows: list[list[str]] = []

        for page_num in range(max_pages):
            rows = await self._extract_table(page)
            if not rows:
                break
            all_rows.extend(rows)

            # 检查是否有下一页按钮且可点击
            try:
                next_btn = page.locator(".ant-pagination-next").first
                if await next_btn.count() == 0:
                    break
                # 检查是否禁用
                is_disabled = await next_btn.evaluate(
                    "el => el.classList.contains('ant-pagination-disabled')"
                )
                if is_disabled:
                    break
                # 翻页
                await next_btn.click(timeout=3000)
                await asyncio.sleep(3)
                log.info("idcrm_skill.next_page", page=page_num + 2, rows_so_far=len(all_rows))
            except Exception:
                break

        log.info("idcrm_skill.extract_complete", total_rows=len(all_rows))
        return all_rows

    async def _extract_table(self, page) -> list[list[str]]:
        """提取结果表格（排除操作列等无效行）。"""
        selectors = [
            "table tbody tr",
            ".ant-table-row",
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
                    # 过滤掉无效行（如只有"操作日志 编辑 删除"等操作按钮的行）
                    valid = []
                    for r in rows:
                        if any(c for c in r) and not all("操作" in c or "编辑" in c or "删除" in c for c in r if c):
                            valid.append(r)
                    if valid:
                        return valid
            except Exception:
                continue
        return []
