"""IDCRMBrowserImpl 单测 —— mock playwright，不真启浏览器。"""

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


SAMPLE_CELLS = [
    "position_id_1",  # [0] 机位ID
    "idc_group_a",  # [1] 一级机房
    "idc_a",  # [2] 机房管理单元
    "cabinet_a",  # [3] 机架编号
    "position_a",  # [4] 机位编号
    "module_a",  # [5] Module
    "logic_area_a",  # [6] 机位逻辑区域
    "已占用",  # [7] 机位状态
    "port_a",  # [8] 内网交换机端口
    "",  # [9] 机位预启用时间
    "project_a",  # [10] 建设项目
    "",  # [11] 操作
]


class TestUrlBuilder:
    def test_basic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_IDCRM_BASE_URL", "http://idcrm.example.com")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = IDCRMBrowserImpl()
        url = impl._build_query_url(idc="idc_a")
        assert url == "http://idcrm.example.com/db/positions?idc=idc_a"

    def test_with_cabinet_and_asset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_IDCRM_BASE_URL", "http://idcrm.example.com/")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = IDCRMBrowserImpl()
        url = impl._build_query_url(idc="idc_a", cabinet="cabinet_a", asset_id="TYSV00000001")
        assert "idc=idc_a" in url
        assert "cabinet=cabinet_a" in url
        assert "asset_id=TYSV00000001" in url


class TestSafeCell:
    def test_basic(self) -> None:
        assert IDCRMBrowserImpl._safe_cell(["a", "b"], 0) == "a"
        assert IDCRMBrowserImpl._safe_cell(["-"], 0) is None
        assert IDCRMBrowserImpl._safe_cell([], 0) is None


def test_parse_has_tpc() -> None:
    assert IDCRMBrowserImpl._parse_has_tpc("已占用") is True
    assert IDCRMBrowserImpl._parse_has_tpc("空闲") is False
    assert IDCRMBrowserImpl._parse_has_tpc("未知") is None


class TestParseRow:
    def test_full_row(self) -> None:
        row = IDCRMBrowserImpl._parse_row(
            SAMPLE_CELLS,
            asset_id="TYSV00000001",
            fallback_idc="fallback_idc",
            fallback_cabinet="fallback_cabinet",
        )
        assert row["idc"] == "idc_a"
        assert row["cabinet"] == "cabinet_a"
        assert row["position"] == "position_a"
        assert row["has_tpc"] is True
        assert row["_source"] == "idcrm-browser"

    def test_short_row_uses_fallback(self) -> None:
        row = IDCRMBrowserImpl._parse_row([], fallback_idc="idc_a", fallback_cabinet="cabinet_a")
        assert row["idc"] == "idc_a"
        assert row["cabinet"] == "cabinet_a"
        assert row["position"] is None


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
            assert await impl.get_position("idc_a") is None

    async def test_with_rows_returns_parsed_position(self) -> None:
        impl = IDCRMBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://idcrm.example.com/q"
        page.eval_on_selector_all = AsyncMock(return_value=[SAMPLE_CELLS])

        with patch(
            "app.clients.idcrm_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            data = await impl.get_position("idc_a", "cabinet_a", "TYSV00000001")
        assert data is not None
        assert data["position"] == "position_a"

    async def test_close_no_op(self) -> None:
        await IDCRMBrowserImpl().close()
