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
    async def page(cls) -> AsyncIterator:
        """打开一个新 page，使用完自动关闭。

        使用 _operation_lock 确保同一时间只有一个页面操作，
        防止并发 Playwright 操作导致冲突。
        """
        async with cls._operation_lock:
            ctx = await cls._ensure()
            page = await ctx.new_page()
            try:
                yield page
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


# 便于其他模块复用 os.environ 读取（避免循环 import）
__all__ = ["BrowserSession", "is_login_url", "is_doc_login_page", "os"]
