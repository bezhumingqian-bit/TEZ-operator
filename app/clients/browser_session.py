"""BrowserSession —— Playwright 单例 BrowserContext。

设计要点
========
- 整个应用只持有 1 个 ``BrowserContext``，多个 Impl（TCUMBrowser / CMDBBrowser…）
  通过 ``new_page()`` 共享登录态（iOA SSO 已验证可跨平台复用，docs/15）。
- 使用 ``launch_persistent_context(user_data_dir=...)``，cookies / localStorage
  自动持久化在 ``data/playwright-profile``（已 .gitignore）。
- 启动延迟：``async with BrowserSession.get() as ctx:`` 第一次使用时才启动。
- 关闭：在 FastAPI lifespan 的 finally 段调用 ``await BrowserSession.close()``。
- 登录态有效性：通过 ``Cookies`` 文件 mtime 在 N 天内（默认 7 天）判断。
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import get_settings
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

log = get_logger(__name__)


class BrowserSession:
    """全局单例 BrowserContext。"""

    _ctx: BrowserContext | None = None
    _playwright = None  # type: ignore[var-annotated]
    _lock = asyncio.Lock()
    _operation_lock = asyncio.Lock()  # 防止并发页面操作冲突

    # ──────────────── 启动 / 关闭 ────────────────

    @classmethod
    async def _ensure(cls) -> BrowserContext:
        if cls._ctx is not None:
            return cls._ctx
        async with cls._lock:
            if cls._ctx is not None:
                return cls._ctx
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "playwright 未安装，请先 `pip install playwright` 并 "
                    "`python -m playwright install chromium`"
                ) from exc

            s = get_settings()
            profile_dir = Path(s.browser_profile_dir).resolve()
            profile_dir.mkdir(parents=True, exist_ok=True)
            log.info(
                "browser.launch",
                profile_dir=str(profile_dir),
                headless=s.browser_headless,
                ignore_https_errors=s.browser_ignore_https_errors,
            )

            cls._playwright = await async_playwright().start()
            # 若启用 headless，追加 --headless=new 以使用 Chromium 新 headless 模式
            # （旧 headless 使用简化引擎，无法复用 SAML / iOA 登录态；新 headless 与 headful 共用引擎）
            args = ["--disable-blink-features=AutomationControlled"]
            if s.browser_headless:
                args.append("--headless=new")
            cls._ctx = await cls._playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=s.browser_headless,
                ignore_https_errors=s.browser_ignore_https_errors,
                viewport={"width": 1440, "height": 900},
                args=args,
            )
        return cls._ctx

    @classmethod
    async def close(cls) -> None:
        """关闭浏览器上下文（lifespan finally 调用）。"""
        async with cls._lock:
            if cls._ctx is not None:
                try:
                    await cls._ctx.close()
                except Exception as exc:  # noqa: BLE001
                    log.warning("browser.close_failed", error=str(exc))
                cls._ctx = None
            if cls._playwright is not None:
                try:
                    await cls._playwright.stop()
                except Exception as exc:  # noqa: BLE001
                    log.warning("browser.playwright_stop_failed", error=str(exc))
                cls._playwright = None

    # ──────────────── page 工具 ────────────────

    @classmethod
    @asynccontextmanager
    async def page(cls, *, audit_platform: str = "", audit_operation: str = "") -> AsyncIterator:
        """打开一个新 page，使用完自动关闭。

        使用 _operation_lock 确保同一时间只有一个页面操作，
        防止并发 Playwright 操作导致冲突。

        Args:
            audit_platform: 可选，平台名（tcum/cmdb/idcrm/yunxiao），启用浏览器审计
            audit_operation: 可选，操作名（search/sync/batch），启用浏览器审计
        """
        from app.core.observability import BrowserAuditLogger

        auditor = BrowserAuditLogger(platform=audit_platform, operation=audit_operation) if audit_platform else None

        async with cls._operation_lock:
            ctx = await cls._ensure()
            page = await ctx.new_page()

            if auditor:
                auditor.mark_start()

            try:
                yield page
                # 正常退出 → 标记成功
                if auditor:
                    auditor.mark_success(screenshot=page)
            except Exception as exc:
                if auditor:
                    auditor.mark_failure(error=str(exc), screenshot=page)
                raise
            finally:
                try:
                    await page.close()
                except Exception:  # pragma: no cover  # noqa: BLE001
                    pass

    # ──────────────── 登录态有效性 ────────────────

    @staticmethod
    def is_login_valid() -> bool:
        """通过 Cookies 文件 mtime 判断登录态是否在 N 天内仍有效。

        - 路径：``<profile>/Default/Cookies``（Chromium 标准位置）
        - 阈值：``settings.browser_login_valid_days``（默认 7 天）
        - 文件不存在 → False（首次使用，需要扫码）
        """
        s = get_settings()
        profile_dir = Path(s.browser_profile_dir)
        cookies_file = profile_dir / "Default" / "Cookies"
        if not cookies_file.exists():
            return False
        try:
            mtime = cookies_file.stat().st_mtime
        except OSError:
            return False
        import time

        age_days = (time.time() - mtime) / 86400
        return age_days < s.browser_login_valid_days

    @staticmethod
    def profile_exists() -> bool:
        """profile 目录是否存在 cookies 文件（哪怕过期）。"""
        s = get_settings()
        return (Path(s.browser_profile_dir) / "Default" / "Cookies").exists()


def is_login_url(url: str | None) -> bool:
    """判断 URL 是否落在 SSO / 登录页（被踢回登录的信号）。

    与 PoC 脚本 ``poc_step1_login.py:is_login_page`` 保持一致。
    """
    if not url:
        return True
    lower = url.lower()
    keywords = ("passport", "login", "sso", "auth", "bcp.", "wwlogin")
    return any(k in lower for k in keywords)


async def is_doc_login_page(page) -> bool:
    """判断腾讯文档是否落在企业微信扫码登录页。

    企微登录页 URL 仍为 doc.weixin.qq.com（不含 passport/login 关键词），
    需要检查页面文本来判断。
    """
    if is_login_url(page.url):
        return True
    try:
        text = await page.text_content("body", timeout=3000) or ""
        login_signals = ("企业微信扫码登录", "企业身份登录", "扫描二维码登录", "请使用企业微信")
        return any(s in text for s in login_signals)
    except Exception:
        return False


async def auto_iOA_login(page, *, deadline: float | None = None, prefix: str = "browser") -> bool:
    """在 SSO 登录页自动点击 iOA 快速登录按钮（无需扫码）。

    适用范围：CMDB / TCUM / IDCRM / YunXiao 等通过 iOA SSO 认证的内网平台。

    流程：
    1. 检测到 SSO 登录页 → 查找"IOA 登录"按钮
    2. 点击按钮 → iOA 客户端弹出确认框
    3. 等待页面离开 SSO 域（iOA 确认后自动回调）

    与 BaseBrowserImpl._try_finish_sso_flow 的区别：
    - 该函数是独立的全局工具函数，任何 client 可以直接调用
    - 返回 bool 表示是否成功，不抛异常
    - 只点击一次 IOA 登录按钮，然后等待回调（不重复点击）

    Returns:
        True 表示登录成功（已离开 SSO 页面），False 表示超时或失败。
    """
    import asyncio

    # Step 1: 找到并点击"IOA 登录"按钮（只点一次）
    ioa_terms = ("IOA 登录", "iOA 登录", "手机 iOA", "一键认证", "快速登录", "iOA快速登录")

    if deadline is None:
        deadline = asyncio.get_running_loop().time() + 60  # 60 秒足够

    loop = asyncio.get_running_loop()
    clicked = False

    for term in ioa_terms:
        locators = (
            page.get_by_role("button", name=term),
            page.get_by_role("link", name=term),
            page.locator(f'button:has-text("{term}")').first,
            page.locator(f'[class*="loginBtn"]').first,
            page.locator(f'[class*="login"] button').first,
        )
        for loc in locators:
            try:
                count = await loc.count()
                if count > 0 and await loc.first.is_visible(timeout=1000):
                    log.info(f"{prefix}.auto_iOA.click", term=term)
                    await loc.first.click(timeout=3000)
                    clicked = True
                    break
            except Exception as exc:
                log.debug(f"{prefix}.auto_iOA.click_failed", term=term, error=str(exc))
        if clicked:
            break

    if not clicked:
        log.warning(f"{prefix}.auto_iOA.no_button_found", url=page.url)
        return False

    # Step 2: 等待页面离开 SSO 域（iOA 确认后自动跳转）
    log.info(f"{prefix}.auto_iOA.waiting_for_callback")
    while is_login_url(page.url) and loop.time() < deadline:
        await asyncio.sleep(2)

    # 最终检查
    if is_login_url(page.url):
        log.warning(f"{prefix}.auto_iOA.timeout", url=page.url[:120])
        return False
    log.info(f"{prefix}.auto_iOA.success", url=page.url[:120])
    return True


# 便于其他模块复用 os.environ 读取（避免循环 import）
__all__ = [
    "BrowserSession",
    "is_login_url",
    "is_doc_login_page",
    "auto_iOA_login",
    "os",
]
