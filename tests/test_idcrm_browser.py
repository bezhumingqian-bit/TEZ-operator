"""IDCRMBrowserImpl 单测 —— 框架占位，验证 URL/结构/异常路径。

由于 ``_parse_row`` 当前 raise NotImplementedError（W4 联调时填实），
本文件只测：URL 构造 / fetch 流程异常处理 / get_position 在 fetch 后会触发未实现错误。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.base import BrowserAuthExpired
from app.clients.idcrm_browser import IDCRMBrowserImpl


@pytest.fixture(autouse=True)
def _fast_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(IDCRMBrowserImpl, "DEFAULT_WAIT_AFTER_GOTO_MS", 1)


def _fake_page_ctx(page: MagicMock):
    @asynccontextmanager
    async def _ctx():
        yield page

    return MagicMock(side_effect=_ctx)


class TestUrlBuilder:
    def test_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_IDCRM_BASE_URL", "http://idcrm.example.com")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = IDCRMBrowserImpl()
        url = impl._build_query_url(idc="示例机房A1")
        assert url == "http://idcrm.example.com/query?idc=示例机房A1"

    def test_with_cabinet_and_asset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_IDCRM_BASE_URL", "http://idcrm.example.com/")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = IDCRMBrowserImpl()
        url = impl._build_query_url(idc="示例机房A1", cabinet="A-12", asset_id="TYSV00000001")
        assert "idc=示例机房A1" in url
        assert "cabinet=A-12" in url
        assert "asset_id=TYSV00000001" in url


class TestSafeCell:
    def test_basic(self) -> None:
        assert IDCRMBrowserImpl._safe_cell(["a", "b"], 0) == "a"
        assert IDCRMBrowserImpl._safe_cell(["-"], 0) is None
        assert IDCRMBrowserImpl._safe_cell([], 0) is None


@pytest.mark.asyncio
class TestFetchRows:
    async def test_auth_expired(self) -> None:
        impl = IDCRMBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "https://sso.example.com/auth"
        page.eval_on_selector_all = AsyncMock(return_value=[])

        with patch(
            "app.clients.idcrm_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            with pytest.raises(BrowserAuthExpired):
                await impl._fetch_rows("http://idcrm.example.com/q")

    async def test_no_rows(self) -> None:
        impl = IDCRMBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://idcrm.example.com/q"
        page.eval_on_selector_all = AsyncMock(return_value=[])

        with patch(
            "app.clients.idcrm_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            assert await impl._fetch_rows("http://idcrm.example.com/q") == []


class TestParseRowNotImplemented:
    """W4 真实页面到位前应保持 NotImplementedError 占位。"""

    def test_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            IDCRMBrowserImpl._parse_row(["a"] * 5)


@pytest.mark.asyncio
class TestGetPosition:
    async def test_empty_idc_returns_none(self) -> None:
        impl = IDCRMBrowserImpl()
        assert await impl.get_position("") is None

    async def test_no_rows_returns_none(self) -> None:
        impl = IDCRMBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://idcrm.example.com/q"
        page.eval_on_selector_all = AsyncMock(return_value=[])

        with patch(
            "app.clients.idcrm_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            assert await impl.get_position("示例机房A1") is None

    async def test_with_rows_raises_not_implemented(self) -> None:
        """fetch 拿到行后 _parse_row 应报 NotImplementedError（W4 之前的预期行为）。"""
        impl = IDCRMBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://idcrm.example.com/q"
        page.eval_on_selector_all = AsyncMock(return_value=[["示例机房A1", "A-12", "A-12-3", "是"]])

        with patch(
            "app.clients.idcrm_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            with pytest.raises(NotImplementedError):
                await impl.get_position("示例机房A1")

    async def test_close_no_op(self) -> None:
        await IDCRMBrowserImpl().close()
