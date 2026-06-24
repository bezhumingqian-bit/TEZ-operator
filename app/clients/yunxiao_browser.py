"""云霄平台 — 浏览器自动化（母机管理 / 新机型库存查询）。

使用 Playwright 访问 https://yunxiao.vstation.woa.com/synergy/honeycomb-host。
继承 BaseBrowserImpl 复用 SSO 登录 + 表格提取骨架。

抓取质量三要素（2026-06-22 补强，对齐 IDCRMPositionSkill 成熟模式）：
1. 登录显式等待：SSO 后轮询 is_login_url，最多 120s，避免登录态未就绪就抓空表。
2. 翻页全量抓取：设置每页最大 + Tea 分页翻页累积去重，不再受单页 128 行上限。
3. 筛选校验 + 重试：选完下拉后回读选中值校验，不一致刷新重试最多 2 次。
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from app.clients.base_browser import BaseBrowserImpl
from app.clients.browser_session import BrowserSession, is_login_url
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

    # ── 抓取行为常量（对齐 IDCRM skill）──
    LOGIN_WAIT_TIMEOUT = 120   # 登录轮询总超时（秒）
    LOGIN_POLL_INTERVAL = 3    # 登录轮询间隔（秒）
    WAIT_AFTER_GOTO = 3.5      # goto 后等待（秒）
    WAIT_AFTER_SEARCH = 2.5    # 点查询后等待（秒）
    MAX_FILTER_RETRY = 2       # 筛选校验失败重试次数
    MAX_PAGES = 50             # 翻页上限（50 页 ≈ 数千行，足够覆盖单区母机）
    MAX_COLS = 40              # 单行最多取列数（覆盖母机 30 列 + 余量）

    async def query_host_machines(
        self,
        zone: str | None = None,
        zones: list[str] | None = None,
        region: str | None = None,
        machine_type: str | None = None,
        instance_family: str | None = None,
        is_empty_host: bool = False,
    ) -> list[dict]:
        """查询母机管理 — 已投放母机状态。

        Args:
            zone / zones: 可用区（需搭配 region 使用，否则筛选不生效）。
            region: 地域（如"华东地区(上海)"），必须传才能正确定位可用区。
        """
        filters = {"zone": zone, "instance_family": instance_family, "machine_type": machine_type}
        rows = await self._query_with_filters(
            _HOST_URL, "母机管理", "/honeycomb-host",
            filters, region=region, zones=zones,
        )
        results = self._parse_host_rows(rows)
        if is_empty_host:
            results = [r for r in results if self._is_truthy(r.get("is_empty_host"))]
        return results

    async def query_inventory(
        self,
        zone: str | None = None,
        zones: list[str] | None = None,
        region: str | None = None,
        instance_family: str | None = None,
        instance_type: str | None = None,
    ) -> list[dict]:
        """查询新机型库存 — 已上线实例库存。"""
        filters = {"zone": zone, "instance_family": instance_family, "instance_type": instance_type}
        rows = await self._query_with_filters(
            _INVENTORY_URL, "新机型库存查询", "/beacon-instance-sales-config",
            filters, region=region, zones=zones,
        )
        return self._parse_inventory_rows(rows)

    async def query_host_by_keyword(self, keyword: str) -> list[dict]:
        """按固资号 / IP 精确查单台（或少数）母机。

        优先使用母机页顶部的关键字搜索框；搜不到时降级为全量抓取后本地匹配。
        """
        keyword = (keyword or "").strip()
        if not keyword:
            return []

        async with BrowserSession.page() as page:
            await self._navigate_and_login(page, _HOST_URL)
            if "/honeycomb-host" not in page.url:
                await self._click_sidebar(page, "母机管理")
                await asyncio.sleep(1.5)

            searched = await self._fill_keyword_search(page, keyword)
            await self._click_search(page)
            rows = await self._extract_all_tea_rows(page)

        results = self._parse_host_rows(rows)
        # 无论页面搜索是否生效，最终都按 keyword 在固资号/IP 上做精确兜底过滤
        kw = keyword.upper()
        filtered = [
            r for r in results
            if kw in (r.get("asset_id") or "").upper() or kw in (r.get("ip") or "").upper()
        ]
        log.info(
            f"{self._log_prefix}.keyword_query_done",
            keyword=keyword, page_search=searched, raw=len(results), matched=len(filtered),
        )
        return filtered

    # ── 查询编排（登录等待 + 筛选校验重试 + 翻页全量）──

    async def _query_with_filters(
        self, url: str, sidebar_text: str, url_keyword: str,
        filters: dict[str, str | None],
        region: str | None = None,
        zones: list[str] | None = None,
    ) -> list[list[str]]:
        """TEZ 专用查询编排：地域→可用区+系统+资源池→查询。

        截图确认流程（2026-06-24）：
        1. 点"更多搜索"展开额外筛选
        2. 地域选 Region（如"西南地区(成都)"）
        3. 可用区多选 TEZ 边缘区（如"成都边缘二区"）
        4. 系统多选"虚拟机"+"裸金属"
        5. 资源池选"qcloud_cdc"
        6. 点查询
        """
        async with BrowserSession.page() as page:
            await self._navigate_and_login(page, url)

            for attempt in range(1 + self.MAX_FILTER_RETRY):
                if attempt > 0:
                    log.warning(f"{self._log_prefix}.filter_retry", attempt=attempt)
                    try:
                        await page.goto(url, wait_until="domcontentloaded",
                                        timeout=self._settings.browser_page_timeout_ms)
                    except Exception:
                        pass
                    await asyncio.sleep(self.WAIT_AFTER_GOTO)

                if url_keyword not in page.url:
                    await self._click_sidebar(page, sidebar_text)
                    await asyncio.sleep(1.5)

                # Step 1: 展开"更多搜索"（tea-accordion）
                try:
                    more_btn = page.locator(
                        ".tea-accordion__header:has-text('更多搜索')"
                    ).first
                    if await more_btn.count() > 0:
                        # bounding box 很宽，中心落在遮挡元素上；
                        # 点左侧文字位置（x+20）避开遮挡
                        box = await more_btn.bounding_box()
                        if box:
                            await page.mouse.click(box["x"] + 20, box["y"] + box["height"] / 2)
                            await asyncio.sleep(1.5)
                    log.info(f"{self._log_prefix}.expanded_more_search")
                except Exception as exc:
                    log.warning(f"{self._log_prefix}.expand_more_failed", error=str(exc))

                # Step 2: 地域（Region）
                if region:
                    await self._fill_tea_select(page, "地域", region)
                    await asyncio.sleep(1.5)  # 等可用区联动刷新

                # Step 3: 可用区（逐个选，复用已验证的单选方法）
                if zones:
                    for z in zones:
                        await self._fill_tea_select(page, "可用区", z)
                        await asyncio.sleep(0.8)

                # Step 4: 系统（逐个选：虚拟机 + 裸金属）
                for sys_val in ["虚拟机", "裸金属"]:
                    await self._fill_tea_select(page, "系统", sys_val)
                    await asyncio.sleep(0.8)

                # Step 5: 资源池选 qcloud_cdc
                await self._fill_tea_select(page, "资源池", "qcloud_cdc")

                # Step 6: 查询
                await self._click_search(page)
                break

            return await self._extract_all_tea_rows(page)

    # ── 内部方法 ──

    async def _navigate_and_login(self, page: Any, url: str) -> None:
        """打开页面，处理 SSO 登录（含显式轮询等待）。"""
        timeout_ms = self._settings.browser_page_timeout_ms
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as exc:
            log.warning(f"{self._log_prefix}.goto_warn", error=str(exc))

        await asyncio.sleep(self.WAIT_AFTER_GOTO)

        # SSO 自动点击（基类）
        await self._try_finish_sso_flow(page)

        # 显式轮询等待登录态就绪（首次扫码 / 登录态过期场景）
        if is_login_url(page.url):
            log.info(f"{self._log_prefix}.waiting_for_login", url=page.url[:60])
            waited = 0
            while is_login_url(page.url) and waited < self.LOGIN_WAIT_TIMEOUT:
                await asyncio.sleep(self.LOGIN_POLL_INTERVAL)
                waited += self.LOGIN_POLL_INTERVAL
            if is_login_url(page.url):
                log.warning(f"{self._log_prefix}.login_timeout", waited=waited)
            else:
                log.info(f"{self._log_prefix}.login_success", waited=waited)
                await asyncio.sleep(self.WAIT_AFTER_GOTO)

        # 若登录后未自动跳回目标页，重新 goto
        if url not in page.url and not is_login_url(page.url):
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await asyncio.sleep(2)

    async def _click_sidebar(self, page: Any, text: str) -> None:
        """点击侧边栏菜单项。"""
        try:
            locator = page.locator("a").filter(has_text=text).first
            await locator.click(timeout=5000)
        except Exception as exc:
            log.warning(f"{self._log_prefix}.sidebar_click_failed", text=text, error=str(exc))

    async def _set_tea_filter(self, page: Any, region_label: str = "", **kwargs: str | None) -> bool:
        """设置 tea-form 筛选条件，并校验是否真正选中。"""
        label_map: dict[str, str] = {
            "region": region_label or "地域",
            "zone": "可用区",
            "instance_family": "实例族",
            "instance_type": "实例类型",
            "machine_type": "机型",
            "system": "系统",
            "pool": "资源池",
        }
        all_ok = True
        for key, value in kwargs.items():
            if value is None:
                continue
            label = label_map.get(key, key)
            try:
                await self._fill_tea_select(page, label, value)
                if not await self._verify_tea_filter(page, label, value):
                    all_ok = False
                    log.warning(f"{self._log_prefix}.filter_verify_failed", key=key, value=value)
            except Exception as exc:
                all_ok = False
                log.warning(f"{self._log_prefix}.filter_failed", key=key, value=value, error=str(exc))
        return all_ok

    async def _fill_tea_select(self, page: Any, label: str, value: str) -> None:
        """填写 Tea UI 下拉框或输入框。"""
        form_item = page.locator(".tea-form__item").filter(has_text=label).first
        if await form_item.count() == 0:
            form_item = page.locator("label").filter(has_text=label).locator("..").first
        if await form_item.count() == 0:
            # 调试：dump 所有可见 label 文本
            try:
                all_labels = await page.locator(".tea-form__item label, .tea-form__label").evaluate_all(
                    "els => els.map(e => e.textContent.trim()).filter(t => t)"
                )
                log.warning(f"{self._log_prefix}.filter_label_not_found", label=label, available=all_labels[:10])
            except Exception:
                log.warning(f"{self._log_prefix}.filter_label_not_found", label=label)
            return

        # 尝试 select/dropdown 组件
        select_trigger = form_item.locator(
            ".tea-select__value, .tea-select, .tea-dropdown__header, "
            ".tea-dropdown-btn, [role=combobox], select"
        ).first
        if await select_trigger.count() > 0:
            # 可见元素用常规 click，不可见则 scroll 后 click
            try:
                await select_trigger.scroll_into_view_if_needed(timeout=2000)
                await select_trigger.click(timeout=3000)
            except Exception:
                # 兜底：dispatch_event
                await select_trigger.dispatch_event("click")
            await asyncio.sleep(1.5)

            # 搜索框在弹窗顶部；优先用简短关键词过滤
            search_input = page.locator(
                ".tea-dropdown-popup input[type=text], "
                ".tea-dropdown-box input[type=text], "
                ".tea-select__popup input[type=text], "
                ".tea-search__input input, "
                "input[placeholder*='搜索'], input[placeholder*='输入']"
            ).first
            search_term = value[:3] if len(value) > 6 else value  # 如"南昌边缘一区"→"南昌边"
            if await search_input.count() > 0 and await search_input.is_visible():
                try:
                    await search_input.fill("", timeout=2000)
                    await search_input.fill(search_term, timeout=2000)
                    await asyncio.sleep(1.2)
                except Exception:
                    pass

            # 在全局可见 li 中找匹配
            try:
                lis = page.locator("li")
                count = await lis.count()
                for i in range(min(count, 50)):
                    li = lis.nth(i)
                    text = (await li.inner_text()).strip()
                    if value in text or (len(value) > 6 and value[:4] in text):
                        await li.click(timeout=3000)
                        await asyncio.sleep(0.5)
                        return
            except Exception:
                pass

            # 兜底：直接点第一个包含关键词的 li
            fallback = page.locator("li").filter(has_text=value[:3]).first
            if await fallback.count() > 0:
                await fallback.click(timeout=3000)
                await asyncio.sleep(0.5)
            return

        # 普通 input
        inp = form_item.locator("input").first
        if await inp.count() > 0:
            await inp.fill(value, timeout=3000)
            await asyncio.sleep(0.3)

    async def _fill_tea_multi_select(self, page: Any, label: str, values: list[str]) -> None:
        """多选 Tea UI 下拉框：先取消全选，再逐个勾选指定的选项。

        操作流程（针对云霄可用区多选）：
        1. 点击下拉触发器打开弹出层
        2. 如有"全选"checkbox 且已勾选，先取消全选
        3. 在搜索框逐个搜索 values 中的关键词，勾选匹配项
        4. 点击空白处关闭弹出层
        """
        form_item = page.locator(".tea-form__item").filter(has_text=label).first
        if await form_item.count() == 0:
            form_item = page.locator("label").filter(has_text=label).locator("..").first
        if await form_item.count() == 0:
            log.warning(f"{self._log_prefix}.multi_select_form_not_found", label=label)
            return

        # 打开下拉（tea-dropdown 和 tea-select 都支持）
        select_trigger = form_item.locator(
            ".tea-select__value, .tea-select, .tea-dropdown__header, "
            ".tea-dropdown-btn, [role=combobox]"
        ).first
        if await select_trigger.count() > 0:
            await select_trigger.click(timeout=3000, force=True)
            await asyncio.sleep(1.5)

        # 搜索框（弹窗内的 input）
        search_box = page.locator(
            "input[type=text]:visible"
        ).first

        selected_count = 0
        for value in values:
            try:
                search_term = value[:3] if len(value) > 6 else value
                # 搜索过滤
                if await search_box.count() > 0 and await search_box.is_visible():
                    await search_box.fill("", timeout=1000)
                    await asyncio.sleep(0.2)
                    await search_box.fill(search_term, timeout=2000)
                    await asyncio.sleep(1)

                # 在全局可见 li 中精确匹配
                lis = page.locator("li")
                count = await lis.count()
                for i in range(min(count, 80)):
                    li = lis.nth(i)
                    if not await li.is_visible():
                        continue
                    text = (await li.inner_text()).strip()
                    if value == text or value in text or text in value:
                        await li.click(timeout=2000, force=True)
                        await asyncio.sleep(0.3)
                        selected_count += 1
                        break
            except Exception as exc:
                log.debug(f"{self._log_prefix}.multi_select_item_failed", value=value, error=str(exc))
                log.debug(f"{self._log_prefix}.multi_select_item_failed", value=value, error=str(exc))

        # 清空搜索框并关闭弹出层（点击页面空白处）
        try:
            if await search_box.count() > 0:
                await search_box.fill("", timeout=1000)
                await asyncio.sleep(0.3)
        except Exception:
            pass
        try:
            await page.locator("body").click(position={"x": 10, "y": 10})
            await asyncio.sleep(0.5)
        except Exception:
            pass

        log.info(
            f"{self._log_prefix}.multi_select_done",
            label=label, requested=len(values), selected=selected_count,
        )

    async def _verify_tea_filter(self, page: Any, label: str, value: str) -> bool:
        """回读筛选项当前值，校验是否包含期望值。"""
        try:
            form_item = page.locator(".tea-form__item").filter(has_text=label).first
            if await form_item.count() == 0:
                return True  # 找不到表单项，无法校验，不阻塞流程

            # select 显示值
            shown = form_item.locator(".tea-select__value, .tea-select__single").first
            if await shown.count() > 0:
                text = (await shown.inner_text()).strip()
                return value in text or value[:4] in text

            # input 值
            inp = form_item.locator("input").first
            if await inp.count() > 0:
                actual = (await inp.input_value()).strip()
                return value in actual or value[:4] in actual
        except Exception:
            return True  # 校验异常不阻塞
        return True

    async def _fill_keyword_search(self, page: Any, keyword: str) -> bool:
        """在母机页关键字搜索框输入固资号/IP。返回是否成功填入。"""
        selectors = (
            ".tea-search__input input",
            "input.tea-input[placeholder*='固资']",
            "input.tea-input[placeholder*='IP']",
            "input.tea-input[placeholder*='搜索']",
            "input[placeholder*='固资']",
            "input[placeholder*='IP']",
            "input[placeholder*='搜索']",
        )
        for sel in selectors:
            try:
                inp = page.locator(sel).first
                if await inp.count() > 0 and await inp.is_visible(timeout=800):
                    await inp.fill(keyword, timeout=2000)
                    await asyncio.sleep(0.4)
                    await inp.press("Enter")
                    await asyncio.sleep(0.8)
                    log.info(f"{self._log_prefix}.keyword_filled", selector=sel)
                    return True
            except Exception:
                continue
        log.warning(f"{self._log_prefix}.keyword_search_not_found", keyword=keyword)
        return False

    async def _click_search(self, page: Any) -> None:
        """点击查询/搜索按钮。"""
        for term in ("查询", "搜索", "检索"):
            btn = page.get_by_role("button", name=term)
            if await btn.count() > 0:
                await btn.first.click(timeout=3000)
                await asyncio.sleep(self.WAIT_AFTER_SEARCH)
                return
        btns = page.locator("button").filter(has_text="查询")
        if await btns.count() > 0:
            await btns.first.click(timeout=3000)
            await asyncio.sleep(self.WAIT_AFTER_SEARCH)

    # ── 翻页全量抓取 ──

    async def _extract_all_tea_rows(self, page: Any) -> list[list[str]]:
        """提取 tea-table 全部分页数据（设置每页最大 + 翻页累积去重）。"""
        try:
            await page.wait_for_selector(".tea-table tbody tr, .tea-table__body tr", timeout=10000)
        except Exception:
            log.info(f"{self._log_prefix}.no_table_rows")
            return []
        await asyncio.sleep(1)

        await self._set_tea_page_size_max(page)

        all_rows: list[list[str]] = []
        seen: set[str] = set()
        for page_num in range(self.MAX_PAGES):
            rows = await self._extract_current_tea_page(page)
            new_count = 0
            for row in rows:
                key = "|".join(row)
                if key not in seen:
                    seen.add(key)
                    all_rows.append(row)
                    new_count += 1
            if not await self._goto_next_tea_page(page):
                break
            if new_count == 0 and page_num > 0:
                break  # 翻页后无新数据，防止死循环

        log.info(f"{self._log_prefix}.extract_done", total=len(all_rows))
        return all_rows

    async def _extract_current_tea_page(self, page: Any) -> list[list[str]]:
        """抓取当前页 tea-table 全部行（列数限制 MAX_COLS）。"""
        js_code = """
            (maxCols) => {
                const trs = document.querySelectorAll('.tea-table tbody tr');
                const result = [];
                for (let i = 0; i < trs.length; i++) {
                    const cells = trs[i].querySelectorAll('td');
                    const row = [];
                    for (let j = 0; j < Math.min(cells.length, maxCols); j++) {
                        row.push((cells[j].textContent || '').trim());
                    }
                    if (row.some(c => c)) result.push(row);
                }
                return result;
            }
        """
        try:
            return await page.evaluate(js_code, self.MAX_COLS)
        except Exception as exc:
            log.warning(f"{self._log_prefix}.page_extract_failed", error=str(exc))
            return []

    async def _set_tea_page_size_max(self, page: Any) -> None:
        """把 Tea 分页每页条数设为最大可选值，减少翻页次数。"""
        try:
            pager = page.locator(".tea-pagination__pagesize, .tea-pagination select").first
            if await pager.count() == 0:
                return
            await pager.click(timeout=2000)
            await asyncio.sleep(0.6)
            # 弹出条数选项，选最大（通常 50/100）
            options = page.locator(".tea-select__option, .tea-list__item, [role=option], li")
            count = await options.count()
            best_val, best_loc = -1, None
            for i in range(count):
                opt = options.nth(i)
                try:
                    if not await opt.is_visible():
                        continue
                    text = (await opt.inner_text()).strip()
                    m = re.search(r"(\d+)", text)
                    if m and int(m.group(1)) > best_val:
                        best_val, best_loc = int(m.group(1)), opt
                except Exception:
                    continue
            if best_loc is not None:
                await best_loc.click(timeout=2000)
                await asyncio.sleep(1.5)
                log.info(f"{self._log_prefix}.page_size_set", size=best_val)
        except Exception as exc:
            log.debug(f"{self._log_prefix}.page_size_skip", error=str(exc))

    async def _goto_next_tea_page(self, page: Any) -> bool:
        """点击 Tea 分页下一页。返回 False 表示已是最后一页/无下一页。"""
        try:
            next_btn = page.locator(
                ".tea-pagination__nav-next, "
                "button[title='下一页'], "
                ".tea-pagination button:has-text('下一页')"
            ).first
            if await next_btn.count() == 0:
                return False
            # 禁用判断
            disabled = await next_btn.get_attribute("disabled")
            cls = await next_btn.get_attribute("class") or ""
            if disabled is not None or "disabled" in cls or "is-disabled" in cls:
                return False
            if not await next_btn.is_visible(timeout=800):
                return False
            await next_btn.click(timeout=3000)
            await asyncio.sleep(self.WAIT_AFTER_SEARCH)
            return True
        except Exception:
            return False

    # ── 解析（字段对齐，保持不变）──

    def _parse_host_rows(self, rows: list[list[str]]) -> list[dict]:
        """解析母机管理表格行 → 结构化字典。"""
        results: list[dict] = []
        for row in rows:
            # 母机表格首列为复选框（空值），导致整体右移 1 列；剥离后下标对齐
            if row and not (row[0] or "").strip():
                row = row[1:]
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
    def _is_truthy(raw: str | None) -> bool:
        """判断"空母机"等是否为真值。"""
        if raw is None:
            return False
        return raw.strip() in ("是", "true", "True", "1", "yes", "Y")

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
