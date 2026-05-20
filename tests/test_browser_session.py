"""BrowserSession 单测 —— 不真启浏览器。

主要验证：
- ``is_login_valid()`` 通过 Cookies 文件 mtime 判断登录态是否在 N 天内有效
- ``profile_exists()``
- ``is_login_url()`` 关键词识别
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from app.clients.browser_session import BrowserSession, is_login_url


class TestIsLoginUrl:
    def test_login_keywords(self) -> None:
        assert is_login_url("https://passport.example.com/login")
        assert is_login_url("https://sso.example.com/auth")
        assert is_login_url("https://bcp.example.com/login?next=/cmdb")
        assert is_login_url("")
        assert is_login_url(None)

    def test_normal_pages(self) -> None:
        assert not is_login_url("http://tcum.example.com/cmdb/index")
        assert not is_login_url("http://tcum.example.com/cmdb/product/search?key=X")


class TestIsLoginValid:
    def test_no_profile_returns_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEZ_BROWSER_PROFILE_DIR", str(tmp_path / "missing"))
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        assert BrowserSession.is_login_valid() is False
        assert BrowserSession.profile_exists() is False

    def test_fresh_cookies_valid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        profile = tmp_path / "playwright-profile"
        (profile / "Default").mkdir(parents=True)
        cookies = profile / "Default" / "Cookies"
        cookies.write_bytes(b"fake")

        monkeypatch.setenv("TEZ_BROWSER_PROFILE_DIR", str(profile))
        monkeypatch.setenv("TEZ_BROWSER_LOGIN_VALID_DAYS", "7")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        assert BrowserSession.is_login_valid() is True
        assert BrowserSession.profile_exists() is True

    def test_old_cookies_invalid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        profile = tmp_path / "playwright-profile"
        (profile / "Default").mkdir(parents=True)
        cookies = profile / "Default" / "Cookies"
        cookies.write_bytes(b"fake")

        # 改 mtime 到 30 天前
        old_ts = time.time() - 30 * 86400
        os.utime(cookies, (old_ts, old_ts))

        monkeypatch.setenv("TEZ_BROWSER_PROFILE_DIR", str(profile))
        monkeypatch.setenv("TEZ_BROWSER_LOGIN_VALID_DAYS", "7")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        assert BrowserSession.is_login_valid() is False
        # 但 profile 仍存在
        assert BrowserSession.profile_exists() is True
