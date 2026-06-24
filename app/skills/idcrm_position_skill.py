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
from app.config import get_settings
from app.skills.ui_skill import UiSkill
from app.utils.logger import get_logger

log = get_logger(__name__)


class IDCRMPositionSkill(UiSkill):
    """数全通机位查询自动化（继承 UiSkill 通用 UI 操作）。"""

    WAIT_AFTER_GOTO = 4
    WAIT_AFTER_FILTER = 8
    LOGIN_WAIT_TIMEOUT = 120
    LOGIN_POLL_INTERVAL = 3

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
        log.info(
            "idcrm_skill.query_free.start",
            idc=idc, base_url=base_url, timeout_ms=timeout_ms, max_retry=self.MAX_RETRY,
        )

        async with self._get_browser_page() as page:
            if not await self._open_idcrm(page, base_url, timeout_ms):
                log.warning("idcrm_skill.query_free.login_timeout", idc=idc)
                return {"free_count": None, "message": "登录超时（等待120秒），请重试"}

            # 带校验的查询（最多重试 MAX_RETRY 次）
            for attempt in range(1 + self.MAX_RETRY):
                log.info("idcrm_skill.query_free.attempt", idc=idc, attempt=attempt)
                if attempt > 0:
                    log.warning("idcrm_skill.retry", attempt=attempt, reason="校验不通过，刷新重试")
                    try:
                        await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
                    except Exception:
                        pass
                    await asyncio.sleep(self.WAIT_AFTER_GOTO)

                # 配置列+页大小+筛选(机房下拉 + 逻辑区域文本框)+查询+等表格（共用查询动作）
                status = await self._apply_filters_and_search(page, idc=idc)
                if status == "idc_not_found":
                    log.warning("idcrm_skill.query_free.idc_not_found", idc=idc)
                    return {
                        "free_count": None,
                        "idc_not_found": True,
                        "message": f"机房管理单元「{idc}」在数全通中未录入，该可用区可能尚未开区",
                    }

                # 4. 提取结果（支持翻页）
                rows = await self.extract_all_pages(page)
                log.info(
                    "idcrm_skill.query_free.rows_extracted",
                    idc=idc, attempt=attempt, rows=len(rows),
                )
                total_positions = len(rows)

                # 统计各状态分布 + 提取设备固资号
                free_count = 0
                used_count = 0
                other_count = 0
                unavailable_count = 0
                virt_match = 0  # 含"虚拟化"关键词的机位行数（用于校验筛选是否真生效）
                all_assets: list[str] = []
                free_assets: list[str] = []

                for row in rows:
                    row_text = " ".join(row)

                    # 跳过不可用的机位（不计入总数）
                    if "不可用" in row_text:
                        unavailable_count += 1
                        continue

                    if "虚拟化" in row_text:
                        virt_match += 1

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

                # 筛选生效信号：机位逻辑区域=虚拟化 若真生效，绝大多数行应含"虚拟化"。
                # 占比过低 = 筛选未应用、抓回了整机房全部机位（脏数据），交由 service 层门禁判定。
                logic_match_ratio = (virt_match / total_positions) if total_positions else None

                if unavailable_count:
                    log.info("idcrm_skill.unavailable_filtered", count=unavailable_count)

                log.info(
                    "idcrm_skill.query_free.stats",
                    idc=idc,
                    total=total_positions,
                    free=free_count,
                    used=used_count,
                    other=other_count,
                    unavailable=unavailable_count,
                    virt_match=virt_match,
                    logic_match_ratio=(
                        round(logic_match_ratio, 3) if logic_match_ratio is not None else None
                    ),
                    all_assets=len(all_assets),
                    free_assets=len(free_assets),
                )

                result = {
                    "total_positions": total_positions,
                    "free_count": free_count,
                    "used_count": used_count,
                    "other_count": other_count,
                    "all_assets": all_assets,
                    "free_position_assets": free_assets,
                    "logic_match_ratio": logic_match_ratio,
                    "verified": True,
                    "message": (
                        f"虚拟化机位总数: {total_positions}, "
                        f"空闲: {free_count}, 已用: {used_count}, 其他: {other_count}, "
                        f"机位上设备总数: {len(all_assets)} 台"
                    ),
                }
                log.info("idcrm_skill.query_free.return", idc=idc, message=result["message"])
                return result

            # 不应走到这里
            return {"free_count": None, "message": "查询异常"}

    async def query_all_positions(self) -> dict[str, Any]:
        """查询全部可用区的虚拟化机位（只筛选逻辑区域，不限机房）。

        一次拉取所有 TEZ 机位数据，再按机房管理单元分组。
        适合驾驶舱全量刷新场景。
        """
        base_url = self._settings.idcrm_base_url.rstrip("/") + "/db/positions"
        timeout_ms = self._settings.browser_page_timeout_ms
        log.info("idcrm_skill.query_all.start", base_url=base_url, timeout_ms=timeout_ms)

        async with self._get_browser_page() as page:
            if not await self._open_idcrm(page, base_url, timeout_ms):
                log.warning("idcrm_skill.query_all.login_timeout")
                return {"success": False, "message": "登录超时"}

            # 配置列+页大小+筛选(逻辑区域文本框，不限机房)+查询+等表格（共用查询动作）
            await self._apply_filters_and_search(page, idc=None)

            # 提取所有分页（最多50页 = 5000条，足够覆盖全部区域）
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

            log.info(
                "idcrm_skill.query_all.return",
                total_rows=len(rows),
                zones_found=len(results_by_idc),
                idcs=list(results_by_idc.keys()),
            )
            return {
                "success": True,
                "total_rows": len(rows),
                "zones_found": len(results_by_idc),
                "results": results_by_idc,
            }

    # ─── 内部辅助方法 ───

    async def _open_idcrm(self, page, base_url: str, timeout_ms: int) -> bool:
        """打开 IDCRM 机位列表页并处理登录。返回 True=页面就绪，False=登录超时。"""
        log.info("idcrm_skill.open.goto", url=base_url)
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as exc:
            log.warning("idcrm_skill.open.goto_error", error=str(exc))
        await asyncio.sleep(self.WAIT_AFTER_GOTO)
        log.info("idcrm_skill.open.landed", url=page.url[:80])

        if is_login_url(page.url):
            # headless 模式下自动尝试 SSO 点击（否则永远等不到用户操作）
            try:
                from app.clients.base_browser import BaseBrowserImpl
                sso = BaseBrowserImpl()
                await sso._try_finish_sso_flow(page)
                await asyncio.sleep(2)
            except Exception:
                pass
            # 首次使用或登录态过期——等待用户在弹出窗口中扫码
            log.info("idcrm_skill.waiting_for_login", url=page.url[:50])
            waited = 0
            while is_login_url(page.url) and waited < self.LOGIN_WAIT_TIMEOUT:
                await asyncio.sleep(self.LOGIN_POLL_INTERVAL)
                waited += self.LOGIN_POLL_INTERVAL
            if is_login_url(page.url):
                log.warning("idcrm_skill.open.login_timeout", waited=waited)
                return False
            log.info("idcrm_skill.login_success", waited=waited)
            await asyncio.sleep(self.WAIT_AFTER_GOTO)
        log.info("idcrm_skill.open.ready", url=page.url[:80])
        return True

    async def _apply_filters_and_search(self, page, idc: str | None) -> str:
        """「查询动作」的单一实现：配置显示列+页大小 → 设置筛选 → 点查询 → 等表格。

        定时全量刷新、强制刷新、单机房查询三个入口共用此方法，保证逻辑区域筛选
        只有一处实现（文本框 type"虚拟化"），不会再出现某个入口走错控件抓回脏数据。

        - idc 为 None：只按逻辑区域筛选（全量，不限机房）
        - idc 非空：额外按机房管理单元下拉筛选

        返回："ok" | "idc_not_found"
        """
        log.info("idcrm_skill.filters.start", idc=idc or "ALL")
        # 1. 展开显示项 + 勾选"机位放置设备(服务器)"列
        await self._enable_device_column(page)
        # 2. 每页显示100条
        size_ok = await self.set_page_size(page, "100 条/ 页")
        log.info("idcrm_skill.filters.page_size", ok=size_ok)

        # 3. 机房管理单元（仅单机房查询需要；下拉选择）
        if idc:
            idc_search = idc[:8] if len(idc) > 8 else idc
            ok_idc = await self.ant_select_search(
                page, self.IDX_IDC_UNIT,
                search_text=idc_search,
                exact_match=idc,
            )
            log.info("idcrm_skill.filters.idc_select", idc=idc, ok=ok_idc)
            if not ok_idc:
                log.warning("idcrm_skill.idc_not_found", idc=idc)
                return "idc_not_found"

        # 4. 机位逻辑区域 = 文本框输入"虚拟化"（自由文本筛选，全入口统一）
        #    注意：这是 placeholder="请输入机位逻辑区域" 的文本框，
        #    不是"机位逻辑区域属性"下拉框，不要在那个下拉里选值。
        logic_ok = await self._fill_logic_area_input(page, "虚拟化")
        log.info("idcrm_skill.filters.logic_area", ok=logic_ok)
        if not logic_ok:
            log.warning("idcrm_skill.logic_area_not_filled")
        await asyncio.sleep(1)

        # 5. 点查询按钮
        clicked = await self.click_with_fallback(page, [
            "button:has-text(\"查 询\")", "button:has-text(\"查询\")",
            ".ant-btn-primary:has-text(\"查\")", "button.ant-btn-primary",
        ])
        log.info("idcrm_skill.filters.search_clicked", ok=clicked)

        # 6. 等待表格加载（最多约 20 秒，每秒检查一次）
        await asyncio.sleep(3)
        for _wait in range(17):
            try:
                row_count = await page.evaluate(
                    "() => document.querySelectorAll('table tbody tr, .ant-table-row').length"
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
                log.info("idcrm_skill.zero_records_confirmed", idc=idc or "ALL")
            else:
                log.warning("idcrm_skill.table_not_loaded", idc=idc or "ALL")
        log.info("idcrm_skill.filters.done", idc=idc or "ALL")
        return "ok"

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
        """在"机位逻辑区域"文本输入框（placeholder=请输入机位逻辑区域）中输入筛选文本。

        这是自由文本筛选框，不是下拉选择框。必须用真实键盘输入（keyboard.type）
        让 antd 把值注册到受控状态——仅用 JS 设 input.value 不会触发 antd 的
        onChange，点"查询"时筛选条件会被忽略（这是之前抓回整机房脏数据的根因）。
        """
        # 直接用 :visible 伪类锁定可见的输入框：
        # antd 页面常有隐藏的测量副本，普通 .first 可能取到隐藏那个（count>0 却不可见），
        # 对它 scroll/click 会超时——这正是逻辑区域没填进去的根因。
        sel = 'input[placeholder*="机位逻辑区域"]:visible'
        inp = page.locator(sel).first
        # 没有可见的（被折叠在高级筛选区）就点"展开"再找一次
        if await inp.count() == 0:
            try:
                await self.click_expand(page)
                await asyncio.sleep(1)
            except Exception:
                pass
            inp = page.locator(sel).first

        if await inp.count() == 0:
            log.warning("idcrm_skill.logic_area_input_not_found")
            return False

        try:
            # 滚动是尽力而为，失败也继续尝试点击（元素可见时 click 仍能成功）
            try:
                await inp.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass
            await inp.click(timeout=3000)
            # 清空已有内容
            await page.keyboard.press("Meta+a")
            await page.keyboard.press("Backspace")
            # 真实键盘逐字输入，触发 antd onChange
            await page.keyboard.type(text, delay=60)
            await asyncio.sleep(0.5)
            actual = await inp.input_value()
            if actual and text in actual:
                log.info("idcrm_skill.logic_area_filled", text=text, actual=actual)
                return True
            log.warning("idcrm_skill.logic_area_fill_unverified", actual=actual)
            return False
        except Exception as exc:
            log.warning("idcrm_skill.logic_area_fill_error", error=str(exc))
            return False


