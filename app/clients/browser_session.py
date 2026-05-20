"""BrowserSession —— Playwright 单例 BrowserContext。

设计要点
========
- 整个应用只持有 1 个 ``BrowserContext``，多个 Impl（TCUMBrowser / CCDBBrowser…）
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
            )

            cls._playwright = await async_playwright().start()
            cls._ctx = await cls._playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=s.browser_headless,
                ignore_https_errors=True,
                viewport={"width": 1440, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
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
        """打开一个新 page，使用完自动关闭。"""
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
    keywords = ("passport", "login", "sso", "auth", "bcp.")
    return any(k in lower for k in keywords)


# 便于其他模块复用 os.environ 读取（避免循环 import）
__all__ = ["BrowserSession", "is_login_url", "os"]
