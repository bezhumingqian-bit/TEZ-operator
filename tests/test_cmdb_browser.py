"""CMDBBrowserImpl 单测 —— mock playwright，不真启浏览器。

参考 ``test_tcum_browser.py`` 的写法；列序占位字段映射用合成数据。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.base import BrowserAuthExpired
from app.clients.cmdb_browser import CMDBBrowserImpl


@pytest.fixture(autouse=True)
def _fast_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """加速测试：把 SPA 渲染等待从 3500ms 改成 1ms。"""
    monkeypatch.setattr(CMDBBrowserImpl, "DEFAULT_WAIT_AFTER_GOTO_MS", 1)


# 按 W4 真实页面表头生成的 cells 顺序（已脱敏）
SAMPLE_CELLS = [
    "TYSV00000001",  # [0] 服务器固资编号
    "",  # [1] 异常信息
    "TYSV00000001",  # [2] 固资编号
    "SN00000001",  # [3] SN
    "online",  # [4] 状态
    "10.0.0.1",  # [5] 内网IPV4
    "ops_team",  # [6] 运维部门
    "alice",  # [7] 维护人
    "bob;carol",  # [8] 备份维护人
    "biz_module_a",  # [9] 业务模块
    "ten1.customer_a-PRD",  # [10] Module
    "zone_a",  # [11] 可用区
    "idc_a",  # [12] 机房管理单元
]


def _fake_page_ctx(page: MagicMock):
    @asynccontextmanager
    async def _ctx():
        yield page

    return MagicMock(side_effect=_ctx)


# ─────────────────────────── _safe_cell / _parse_bool ───────────────────────────


class TestParseHelpers:
    def test_safe_cell_normal(self) -> None:
        assert CMDBBrowserImpl._safe_cell(["a", "b"], 0) == "a"
        assert CMDBBrowserImpl._safe_cell(["a", "b"], 1) == "b"

    def test_safe_cell_dash_treated_as_none(self) -> None:
        assert CMDBBrowserImpl._safe_cell(["-"], 0) is None

    def test_safe_cell_out_of_range(self) -> None:
        assert CMDBBrowserImpl._safe_cell(["a"], 5) is None
        assert CMDBBrowserImpl._safe_cell([], 0) is None

    def test_safe_cell_empty_string(self) -> None:
        assert CMDBBrowserImpl._safe_cell([""], 0) is None

    def test_parse_bool(self) -> None:
        assert CMDBBrowserImpl._parse_bool("是") is True
        assert CMDBBrowserImpl._parse_bool("true") is True
        assert CMDBBrowserImpl._parse_bool("1") is True
        assert CMDBBrowserImpl._parse_bool("否") is False
        assert CMDBBrowserImpl._parse_bool("false") is False
        assert CMDBBrowserImpl._parse_bool("0") is False
        assert CMDBBrowserImpl._parse_bool(None) is None
        assert CMDBBrowserImpl._parse_bool("maybe") is None


# ─────────────────────────── _parse_row ───────────────────────────


class TestParseRow:
    def test_full_row(self) -> None:
        row = CMDBBrowserImpl._parse_row(SAMPLE_CELLS)
        assert row["asset_id"] == "TYSV00000001"
        assert row["ip"] == "10.0.0.1"
        assert row["zone"] == "zone_a"
        assert row["module"] == "ten1.customer_a-PRD"
        assert row["customer"] is None
        assert row["app_id"] is None
        assert row["machine_type"] is None
        assert row["status"] == "online"
        assert row["idc"] == "idc_a"
        assert row["cabinet"] is None
        assert row["owner"] == "alice"
        assert row["backup_owners"] == ["bob", "carol"]
        assert row["has_tpc"] is None
        assert row["billing_tags"] == {}
        assert row["_source"] == "cmdb-browser"

    def test_short_cells_safe(self) -> None:
        # 列数不足，所有字段都安全 None
        row = CMDBBrowserImpl._parse_row(["", "TYSV00000001"])
        assert row["asset_id"] is None
        assert row["ip"] is None
        assert row["zone"] is None
        assert row["has_tpc"] is None

    def test_dashes_become_none(self) -> None:
        cells = ["-"] * 13
        cells[2] = "TYSV00000002"
        row = CMDBBrowserImpl._parse_row(cells)
        assert row["asset_id"] == "TYSV00000002"
        assert row["ip"] is None


# ─────────────────────────── _build_*_url ───────────────────────────


class TestUrlBuilders:
    def test_base_query_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_CMDB_BASE_URL", "http://cmdb.example.com")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = CMDBBrowserImpl()
        url = impl._base_query_url()
        assert url == "http://cmdb.example.com/server/query"

    def test_base_query_url_strips_trailing_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_CMDB_BASE_URL", "http://cmdb.example.com/")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = CMDBBrowserImpl()
        assert impl._base_query_url() == "http://cmdb.example.com/server/query"


# ─────────────────────────── _search_by_form (mocked) ───────────────────────────


@pytest.mark.asyncio
class TestSearchByForm:
    async def test_auth_expired_raises(self) -> None:
        impl = CMDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "https://passport.example.com/login"
        page.locator = MagicMock(return_value=MagicMock(first=AsyncMock(is_visible=AsyncMock(return_value=False))))
        page.get_by_role = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))
        page.get_by_text = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))

        with patch(
            "app.clients.cmdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            with pytest.raises(BrowserAuthExpired):
                await impl._search_by_form("TYSV00000001")

    async def test_no_input_found_returns_empty(self) -> None:
        impl = CMDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://cmdb.example.com/server/query"
        # All locators return invisible
        mock_loc = MagicMock()
        mock_loc.first = MagicMock()
        mock_loc.first.is_visible = AsyncMock(return_value=False)
        page.locator = MagicMock(return_value=mock_loc)

        with patch(
            "app.clients.cmdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            rows = await impl._search_by_form("TYSV00000001")
            assert rows == []


# ─────────────────────────── public 方法 pipeline ───────────────────────────


@pytest.mark.asyncio
class TestPublicMethods:
    async def test_get_by_asset_empty_returns_none(self) -> None:
        impl = CMDBBrowserImpl()
        assert await impl.get_by_asset("") is None

    async def test_close_no_op(self) -> None:
        await CMDBBrowserImpl().close()

    async def test_get_by_asset_empty(self) -> None:
        impl = CMDBBrowserImpl()
        assert await impl.get_by_asset("") is None

    async def test_get_by_ip_empty(self) -> None:
        impl = CMDBBrowserImpl()
        assert await impl.get_by_ip("") is None

    async def test_list_by_zone_empty(self) -> None:
        impl = CMDBBrowserImpl()
        assert await impl.list_by_zone("") == []

    async def test_close_no_op(self) -> None:
        await CMDBBrowserImpl().close()
