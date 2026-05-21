"""CCDBBrowserImpl 单测 —— mock playwright，不真启浏览器。

参考 ``test_tcum_browser.py`` 的写法；列序占位字段映射用合成数据。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.base import BrowserAuthExpired
from app.clients.ccdb_browser import CCDBBrowserImpl


@pytest.fixture(autouse=True)
def _fast_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """加速测试：把 SPA 渲染等待从 3500ms 改成 1ms。"""
    monkeypatch.setattr(CCDBBrowserImpl, "DEFAULT_WAIT_AFTER_GOTO_MS", 1)


# 按当前 COL_* 占位生成的 cells 顺序（W4 联调可能会调整）
SAMPLE_CELLS = [
    "",  # [0]
    "TYSV00000001",  # [1] asset_id
    "10.0.0.1",  # [2] ip
    "zone_a",  # [3] zone（脱敏占位）
    "ten1.customer_a-PRD",  # [4] module
    "customer_a",  # [5] customer
    "0000000000",  # [6] app_id
    "MOCK-1G",  # [7] machine_type
    "online",  # [8] status
    "示例机房A1",  # [9] idc
    "A-12",  # [10] cabinet
    "是",  # [11] has_tpc
]


def _fake_page_ctx(page: MagicMock):
    @asynccontextmanager
    async def _ctx():
        yield page

    return MagicMock(side_effect=_ctx)


# ─────────────────────────── _safe_cell / _parse_bool ───────────────────────────


class TestParseHelpers:
    def test_safe_cell_normal(self) -> None:
        assert CCDBBrowserImpl._safe_cell(["a", "b"], 0) == "a"
        assert CCDBBrowserImpl._safe_cell(["a", "b"], 1) == "b"

    def test_safe_cell_dash_treated_as_none(self) -> None:
        assert CCDBBrowserImpl._safe_cell(["-"], 0) is None

    def test_safe_cell_out_of_range(self) -> None:
        assert CCDBBrowserImpl._safe_cell(["a"], 5) is None
        assert CCDBBrowserImpl._safe_cell([], 0) is None

    def test_safe_cell_empty_string(self) -> None:
        assert CCDBBrowserImpl._safe_cell([""], 0) is None

    def test_parse_bool(self) -> None:
        assert CCDBBrowserImpl._parse_bool("是") is True
        assert CCDBBrowserImpl._parse_bool("true") is True
        assert CCDBBrowserImpl._parse_bool("1") is True
        assert CCDBBrowserImpl._parse_bool("否") is False
        assert CCDBBrowserImpl._parse_bool("false") is False
        assert CCDBBrowserImpl._parse_bool("0") is False
        assert CCDBBrowserImpl._parse_bool(None) is None
        assert CCDBBrowserImpl._parse_bool("maybe") is None


# ─────────────────────────── _parse_row ───────────────────────────


class TestParseRow:
    def test_full_row(self) -> None:
        row = CCDBBrowserImpl._parse_row(SAMPLE_CELLS)
        assert row["asset_id"] == "TYSV00000001"
        assert row["ip"] == "10.0.0.1"
        assert row["zone"] == "zone_a"
        assert row["module"] == "ten1.customer_a-PRD"
        assert row["customer"] == "customer_a"
        assert row["app_id"] == "0000000000"
        assert row["machine_type"] == "MOCK-1G"
        assert row["status"] == "online"
        assert row["idc"] == "示例机房A1"
        assert row["cabinet"] == "A-12"
        assert row["has_tpc"] is True
        assert row["billing_tags"] == {}
        assert row["_source"] == "ccdb-browser"

    def test_short_cells_safe(self) -> None:
        # 列数不足，所有字段都安全 None
        row = CCDBBrowserImpl._parse_row(["", "TYSV00000001"])
        assert row["asset_id"] == "TYSV00000001"
        assert row["ip"] is None
        assert row["zone"] is None
        assert row["has_tpc"] is None

    def test_dashes_become_none(self) -> None:
        cells = ["-"] * 12
        cells[1] = "TYSV00000002"
        row = CCDBBrowserImpl._parse_row(cells)
        assert row["asset_id"] == "TYSV00000002"
        assert row["ip"] is None


# ─────────────────────────── _build_*_url ───────────────────────────


class TestUrlBuilders:
    def test_search_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_CCDB_BASE_URL", "http://ccdb.example.com")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = CCDBBrowserImpl()
        url = impl._build_search_url("TYSV00000001")
        assert url == "http://ccdb.example.com/search?key=TYSV00000001"
        assert impl._build_search_url("A B") == "http://ccdb.example.com/search?key=A+B"

    def test_search_url_strips_trailing_slash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_CCDB_BASE_URL", "http://ccdb.example.com/")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = CCDBBrowserImpl()
        assert impl._build_search_url("X") == "http://ccdb.example.com/search?key=X"

    def test_zone_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEZ_CCDB_BASE_URL", "http://ccdb.example.com")
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = CCDBBrowserImpl()
        url = impl._build_zone_url("zone_a")
        assert url == "http://ccdb.example.com/zone?zone=zone_a"
        assert impl._build_zone_url("zone a") == (
            "http://ccdb.example.com/zone?zone=zone+a"
        )


# ─────────────────────────── _fetch_rows ───────────────────────────


@pytest.mark.asyncio
class TestFetchRows:
    async def test_auth_expired_raises(self) -> None:
        impl = CCDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "https://passport.example.com/login"
        page.eval_on_selector_all = AsyncMock(return_value=[])

        with patch(
            "app.clients.ccdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            with pytest.raises(BrowserAuthExpired):
                await impl._fetch_rows("http://ccdb.example.com/q?key=X")

    async def test_no_rows_returns_empty(self) -> None:
        impl = CCDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://ccdb.example.com/q?key=X"
        page.eval_on_selector_all = AsyncMock(return_value=[])

        with patch(
            "app.clients.ccdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            rows = await impl._fetch_rows("http://ccdb.example.com/q?key=X")
            assert rows == []

    async def test_rows_filtered_by_keyword(self) -> None:
        impl = CCDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://ccdb.example.com/q"
        # 三行：第二行包含目标
        page.eval_on_selector_all = AsyncMock(
            return_value=[
                ["", "OTHER", "10.0.0.99"],
                SAMPLE_CELLS,
                ["", "ANOTHER", "10.0.0.50"],
            ]
        )

        with patch(
            "app.clients.ccdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            rows = await impl._fetch_rows(
                "http://ccdb.example.com/q",
                target_keyword="TYSV00000001",
            )
        assert len(rows) == 1
        assert rows[0][1] == "TYSV00000001"

    async def test_goto_failure_does_not_block(self) -> None:
        impl = CCDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock(side_effect=RuntimeError("networkidle timeout"))
        page.url = "http://ccdb.example.com/q"
        page.eval_on_selector_all = AsyncMock(return_value=[SAMPLE_CELLS])

        with patch(
            "app.clients.ccdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            rows = await impl._fetch_rows("http://ccdb.example.com/q")
        assert len(rows) == 1


# ─────────────────────────── public 方法 pipeline ───────────────────────────


@pytest.mark.asyncio
class TestPublicMethods:
    async def test_get_by_asset_full(self) -> None:
        impl = CCDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://ccdb.example.com/search?key=TYSV00000001"
        page.eval_on_selector_all = AsyncMock(return_value=[SAMPLE_CELLS])

        with patch(
            "app.clients.ccdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            data = await impl.get_by_asset("TYSV00000001")
        assert data is not None
        assert data["asset_id"] == "TYSV00000001"
        assert data["ip"] == "10.0.0.1"

    async def test_get_by_asset_empty(self) -> None:
        impl = CCDBBrowserImpl()
        assert await impl.get_by_asset("") is None

    async def test_get_by_ip_full(self) -> None:
        impl = CCDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://ccdb.example.com/search?key=10.0.0.1"
        page.eval_on_selector_all = AsyncMock(return_value=[SAMPLE_CELLS])

        with patch(
            "app.clients.ccdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            data = await impl.get_by_ip("10.0.0.1")
        assert data is not None
        assert data["ip"] == "10.0.0.1"

    async def test_get_by_ip_empty(self) -> None:
        impl = CCDBBrowserImpl()
        assert await impl.get_by_ip("") is None

    async def test_list_by_zone_filters_invalid(self) -> None:
        impl = CCDBBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://ccdb.example.com/zone?zone=zone_a"
        # 第一行没 asset_id（被过滤），第二行有
        page.eval_on_selector_all = AsyncMock(
            return_value=[
                [""] * 12,  # 全空，会被 cleaned 过滤
                SAMPLE_CELLS,
            ]
        )

        with patch(
            "app.clients.ccdb_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            items = await impl.list_by_zone("zone_a", limit=10)
        assert len(items) == 1
        assert items[0]["asset_id"] == "TYSV00000001"

    async def test_list_by_zone_empty(self) -> None:
        impl = CCDBBrowserImpl()
        assert await impl.list_by_zone("") == []

    async def test_close_no_op(self) -> None:
        impl = CCDBBrowserImpl()
        # close 不应抛
        await impl.close()
