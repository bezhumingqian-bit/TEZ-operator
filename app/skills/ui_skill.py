"""UI 自动化基类：抽象浏览器自动化通用操作。

将所有 Skill 中重复的 Playwright 操作模式抽取到本基类，包括：
- Ant Design 组件（Select / Pagination / Table / Button）
- 导航与登录检测
- 等待与重试
- 截图与调试
- BrowserSession 生命周期

子类只需关注业务逻辑，通用 UI 操作全部继承。
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Optional

from app.clients.browser_session import BrowserSession, is_login_url
from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)

_CACHE_DIR = Path("data/ui_skill_screenshots")
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class UiSkill:
    """浏览器自动化 UI 操作基类。

    子类使用方式：
        class MySkill(UiSkill):
            async def do_something(self):
                page = await self.open_page("https://example.com")
                rows = await self.extract_table(page)
                ...

    登录态：首次使用需在弹出浏览器中手动扫码，之后 cookies 持久化复用。
    """

    # ── 等待时间常量（子类可覆盖） ──
    WAIT_AFTER_GOTO = 5
    WAIT_AFTER_INPUT = 0.3
    WAIT_TABLE_LOAD = 20
    LOGIN_TIMEOUT = 120

    def __init__(self) -> None:
        self._settings = get_settings()

    # ══════════════════════════════════════════════════
    # 一、页面生命周期
    # ══════════════════════════════════════════════════

    async def open_page(self, url: str) -> Any:
        """打开页面并等待加载，自动检测登录态。

        返回 Playwright Page 对象。
        如果当前在登录页，等待用户扫码（最多 LOGIN_TIMEOUT 秒）。
        """
        timeout_ms = self._settings.browser_page_timeout_ms
        page = await self._get_browser_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
        await asyncio.sleep(self.WAIT_AFTER_GOTO)

        if is_login_url(page.url):
            log.info("ui_skill.waiting_for_login")
            waited = 0
            while is_login_url(page.url) and waited < self.LOGIN_TIMEOUT:
                await asyncio.sleep(3)
                waited += 3
            if is_login_url(page.url):
                raise RuntimeError("登录超时，请重试")
            await asyncio.sleep(self.WAIT_AFTER_GOTO)

        return page

    def _get_browser_page(self):
        """获取 BrowserSession.page() 上下文管理器。
        
        子类使用方式：
            async with self._get_browser_page() as page:
                ...
        """
        return BrowserSession.page()

    # ══════════════════════════════════════════════════
    # 二、Ant Design Select 组件
    # ══════════════════════════════════════════════════

    async def ant_select_search(
        self, page, index: int, search_text: str, exact_match: str
    ) -> bool:
        """操作 Ant Design 搜索型 Select（多级搜索候选降级）。

        参数：
            page: Playwright Page
            index: .ant-select 在页面上的索引（0-based）
            search_text: 搜索关键词（通常为精确值的前缀）
            exact_match: 最终要精确匹配的选项文本

        返回是否成功选中。
        """
        # 生成候选搜索词（从长到短）
        candidates = []
        if search_text and search_text != exact_match:
            candidates.append(search_text)
        candidates.append(exact_match)
        # 前缀候选
        for length in [10, 8, 6, 4]:
            prefix = exact_match[:length]
            if prefix not in candidates:
                candidates.append(prefix)

        for candidate in candidates:
            try:
                select = page.locator(".ant-select").nth(index)
                await select.click(timeout=3000)
                await asyncio.sleep(0.5)

                # 找到内部 input 并输入搜索词
                input_el = select.locator("input").first
                if await input_el.count() > 0:
                    await input_el.click(timeout=2000)
                    await input_el.press("Meta+a")
                    await asyncio.sleep(0.1)
                    await input_el.press("Backspace")
                    await input_el.fill(candidate)
                    await asyncio.sleep(2)

                # 在下拉列表中匹配
                items = page.locator(".ant-select-dropdown-menu-item")
                count = await items.count()
                if count == 0:
                    await page.keyboard.press("Escape")
                    continue

                for idx in range(count):
                    item = items.nth(idx)
                    if await item.is_visible():
                        text = (await item.inner_text()).strip()
                        if text == exact_match:
                            await item.click(timeout=2000)
                            await asyncio.sleep(0.5)
                            return True

                # 精确匹配失败，尝试包含匹配
                for idx in range(count):
                    item = items.nth(idx)
                    if await item.is_visible():
                        text = (await item.inner_text()).strip()
                        if exact_match in text and text:
                            await item.click(timeout=2000)
                            await asyncio.sleep(0.5)
                            return True

                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)

            except Exception:
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass

        log.warning("ui_skill.ant_select_not_found", index=index, exact_match=exact_match[:30])
        return False

    async def ant_select_direct(
        self, page, index: int, exact_match: str
    ) -> bool:
        """操作 Ant Design 普通 Select（非搜索型，选项较少时使用）。

        返回是否成功选中。
        """
        try:
            select = page.locator(".ant-select").nth(index)
            await select.click(timeout=3000)
            await asyncio.sleep(0.8)

            items = page.locator(".ant-select-dropdown-menu-item")
            count = await items.count()
            for idx in range(count):
                item = items.nth(idx)
                if await item.is_visible():
                    text = (await item.inner_text()).strip()
                    if text == exact_match:
                        await item.click(timeout=2000)
                        return True

            log.warning("ui_skill.ant_select_direct_not_found",
                        index=index, exact_match=exact_match[:30])
        except Exception:
            pass
        return False

    # ══════════════════════════════════════════════════
    # 三、Ant Design 表格操作
    # ══════════════════════════════════════════════════

    async def set_page_size(self, page, size_text: str = "100 条/ 页") -> bool:
        """设置 Ant Design 表格分页大小。返回是否成功。"""
        try:
            # 找分页选择器
            pagers = page.locator("text=/条.*页/")
            if await pagers.count() == 0:
                return False

            pager = pagers.first
            current_text = await pager.inner_text()
            if size_text in current_text.replace(" ", ""):
                return True  # 已经是目标值

            await pager.click(timeout=2000)
            await asyncio.sleep(0.8)

            # 在出现的下拉菜单中选目标
            items = page.locator(".ant-select-dropdown-menu-item")
            count = await items.count()
            for idx in range(count):
                item = items.nth(idx)
                if await item.is_visible():
                    text = (await item.inner_text()).strip()
                    if size_text in text:
                        await item.click(timeout=2000)
                        return True
        except Exception:
            pass
        return False

    async def extract_table(self, page) -> list[list[str]]:
        """提取当前页表格数据。返回二维数组 [行][列]（纯文本）。"""
        try:
            return await page.evaluate("""() => {
                const rows = [];
                const trs = document.querySelectorAll('table tbody tr, .ant-table-row');
                for (let i = 0; i < Math.min(trs.length, 200); i++) {
                    const tds = trs[i].querySelectorAll('td, th');
                    const row = [];
                    for (let j = 0; j < Math.min(tds.length, 20); j++) {
                        row.push((tds[j].textContent || '').trim());
                    }
                    if (row.length === 0) continue;
                    // 跳过纯操作列的行
                    if (row.length === 1 && ['操作','编辑','删除'].includes(row[0])) continue;
                    rows.push(row);
                }
                return rows;
            }""")
        except Exception:
            return []

    async def extract_all_pages(
        self, page, max_pages: int = 10
    ) -> list[list[str]]:
        """提取 Ant Design 表格所有分页数据（自动翻页）。"""
        all_rows: list[list[str]] = []
        seen = set()

        for _page_num in range(max_pages):
            rows = await self.extract_table(page)
            for row in rows:
                key = "|".join(row)
                if key not in seen:
                    seen.add(key)
                    all_rows.append(row)

            # 检查是否有下一页
            try:
                next_btn = page.locator(".ant-pagination-next")
                if await next_btn.count() == 0:
                    break
                if await next_btn.locator(".ant-pagination-disabled").count() > 0:
                    break
                await next_btn.click(timeout=3000)
                await asyncio.sleep(3)
            except Exception:
                break

        return all_rows

    async def wait_table_rows(self, page, timeout: int = 20) -> int:
        """等待表格出现数据行，返回行数（超时返回 0）。"""
        for waited in range(timeout):
            try:
                count = await page.evaluate(
                    "() => document.querySelectorAll('table tbody tr, .ant-table-row').length"
                )
                if count > 0:
                    await asyncio.sleep(0.5)
                    return count
            except Exception:
                pass
            await asyncio.sleep(1)

        # 检查是否 "共 0 条"
        try:
            body = await page.evaluate("() => document.body.innerText")
            if "共 0 条" in body:
                log.info("ui_skill.zero_records")
        except Exception:
            pass
        return 0

    # ══════════════════════════════════════════════════
    # 四、按钮与元素点击
    # ══════════════════════════════════════════════════

    async def click_with_fallback(
        self, page, selectors: list[str]
    ) -> bool:
        """多策略点击按钮：依次尝试选择器列表，返回是否成功。"""
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=3000)
                    return True
            except Exception:
                continue

        # 兜底：按 Enter
        try:
            await page.keyboard.press("Enter")
            return True
        except Exception:
            return False

    async def click_expand(self, page) -> bool:
        """点击"展开"按钮（常见于筛选项列表底部）。返回是否成功。"""
        # 策略1：locator 定位
        try:
            for tag in ["a", "span", "button"]:
                btn = page.locator(f'{tag}:has-text("展开")').first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=2000)
                    return True
        except Exception:
            pass

        # 策略2：JS 遍历
        try:
            clicked = await page.evaluate("""() => {
                const els = [...document.querySelectorAll('*')];
                const el = els.find(e => e.innerText?.trim() === '展开' && e.offsetHeight > 0);
                if (el) { el.click(); return true; }
                return false;
            }""")
            if clicked:
                return True
        except Exception:
            pass

        return False

    # ══════════════════════════════════════════════════
    # 五、覆盖层处理
    # ══════════════════════════════════════════════════

    async def dismiss_overlays(self, page) -> None:
        """关闭可能遮挡操作区域的覆盖层/弹窗。

        用 JS 直接隐藏（不用 Escape，避免取消编辑状态）。
        """
        try:
            await page.evaluate("""() => {
                const sharebox = document.querySelector('#doc-sharebox-container');
                if (sharebox) sharebox.style.display = 'none';
                const dialogs = document.querySelectorAll('.content-dialog-container, .ant-modal-mask');
                dialogs.forEach(d => { d.style.display = 'none'; });
            }""")
            await asyncio.sleep(0.3)
        except Exception:
            pass

    # ══════════════════════════════════════════════════
    # 六、重试与调试
    # ══════════════════════════════════════════════════

    async def retry(
        self,
        func,
        *args,
        max_attempts: int = 3,
        on_failure=None,
        **kwargs,
    ) -> Any:
        """调用 func(*args, **kwargs)，失败重试最多 max_attempts 次。"""
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < max_attempts:
                    log.info("ui_skill.retry", attempt=attempt, func=func.__name__)
                    if on_failure:
                        await on_failure()
        raise last_error  # type: ignore

    async def take_screenshot(self, page, name: str) -> Optional[str]:
        """截图保存到 data/ui_skill_screenshots/，返回文件路径。"""
        try:
            filepath = _CACHE_DIR / f"{name}_{int(asyncio.get_event_loop().time() * 1000)}.png"
            await page.screenshot(path=str(filepath))
            return str(filepath)
        except Exception:
            return None

    # ══════════════════════════════════════════════════
    # 七、表单输入
    # ══════════════════════════════════════════════════

    async def fill_input_by_placeholder(
        self, page, placeholder: str, value: str
    ) -> bool:
        """通过 placeholder 定位并填写输入框。返回是否成功。"""
        try:
            inp = page.locator(f'input[placeholder*="{placeholder}"]').first
            if await inp.count() > 0:
                await inp.fill(value)
                await asyncio.sleep(0.3)
                actual = await inp.input_value()
                return bool(actual)
        except Exception:
            pass
        return False

    async def fill_input_by_label(
        self, page, label_text: str, value: str
    ) -> bool:
        """通过相邻 label 文本定位并填写输入框。返回是否成功。"""
        try:
            return await page.evaluate(f"""(value) => {{
                const labels = [...document.querySelectorAll('span, label, div')];
                const label = labels.find(el => el.innerText?.trim().includes('{label_text}'));
                if (!label) return false;
                let parent = label.parentElement;
                for (let i = 0; i < 4 && parent; i++) {{
                    const input = parent.querySelector('input');
                    if (input) {{
                        const setter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        setter.call(input, value);
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    parent = parent.parentElement;
                }}
                return false;
            }}""", value)
        except Exception:
            return False
