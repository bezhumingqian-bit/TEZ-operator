"""TCUMBrowserImpl 单测 —— 全部 mock playwright，不真启浏览器。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.base import BrowserAuthExpired
from app.clients.tcum_browser import TCUMBrowserImpl

# ── 真实 PoC 数据（来自 docs/15 § 一 + output_step1/info.json，已脱敏） ──
# 注意：cells 索引按 PoC 实测顺序（task 描述的 14 列序，前 12 列是页面表格直出）
SAMPLE_CELLS = [
    "",  # [0] checkbox
    "10.0.0.10",  # [1] ip（脱敏）
    "[模块A]-[业务A]",  # [2] module（脱敏）
    "TYSV00000001",  # [3] asset_id（脱敏）
    "alice",  # [4] owner（脱敏）
    "bob;carol;dave",  # [5] backup_owners
    "MOCK-1G",  # [6] machine_type（脱敏）
    "城市A",  # [7] city
    "-",  # [8] _
    "Server",  # [9] server_type
    "运营中",  # [10] status
    "可用区A",  # [11] zone
    "-",  # [12] _
    "5.9年",  # [13] use_years
]


class TestParseRow:
    def test_full_row(self) -> None:
        result = TCUMBrowserImpl._parse_row(SAMPLE_CELLS)
        assert result["asset_id"] == "TYSV00000001"
        assert result["ip"] == "10.0.0.10"
        assert result["module"] == "[模块A]-[业务A]"
        assert result["owner"] == "alice"
        assert result["backup_owners"] == ["bob", "carol", "dave"]
        assert result["machine_type"] == "MOCK-1G"
        assert result["city"] == "城市A"
        assert result["server_type"] == "Server"
        assert result["status"] == "online"  # W3：采集层"运营中"→"online"
        assert result["idc"] == "可用区A"
        assert result["use_years"] == 5.9
        assert result["_source"] == "tcum-browser"

    def test_dash_treated_as_none(self) -> None:
        cells = ["", "-", "-", "TYSV00000002", "-", "", "", "-", "-", "", "", "", "", ""]
        result = TCUMBrowserImpl._parse_row(cells)
        assert result["asset_id"] == "TYSV00000002"
        assert result["ip"] is None
        assert result["module"] is None
        assert result["owner"] is None

    def test_short_cells_safe(self) -> None:
        # 只有前 4 列也不能崩
        cells = ["", "10.0.0.5", "modA", "TYSV00000003"]
        result = TCUMBrowserImpl._parse_row(cells)
        assert result["asset_id"] == "TYSV00000003"
        assert result["ip"] == "10.0.0.5"
        assert result["use_years"] is None
        assert result["backup_owners"] == []

    def test_strip_year_suffix(self) -> None:
        assert TCUMBrowserImpl._strip_year_suffix("5.9年") == 5.9
        assert TCUMBrowserImpl._strip_year_suffix("0年") == 0.0
        assert TCUMBrowserImpl._strip_year_suffix("") is None
        assert TCUMBrowserImpl._strip_year_suffix("abc") is None

    def test_split_backup_owners(self) -> None:
        assert TCUMBrowserImpl._split_backup_owners("a;b;c") == ["a", "b", "c"]
        # 中文分号
        assert TCUMBrowserImpl._split_backup_owners("a；b") == ["a", "b"]
        assert TCUMBrowserImpl._split_backup_owners("") == []
        # 空段过滤
        assert TCUMBrowserImpl._split_backup_owners("a;;b;") == ["a", "b"]

    def test_normalize_status_cn_to_en(self) -> None:
        # 中文映射
        assert TCUMBrowserImpl._normalize_status("运营中") == "online"
        assert TCUMBrowserImpl._normalize_status("维护中") == "maintenance"
        assert TCUMBrowserImpl._normalize_status("故障") == "offline"
        # 已是英文
        assert TCUMBrowserImpl._normalize_status("online") == "online"
        # 空值
        assert TCUMBrowserImpl._normalize_status("") is None
        assert TCUMBrowserImpl._normalize_status(None) is None
        # 未知值 → None（不阻塞，仅 log warning）
        assert TCUMBrowserImpl._normalize_status("奇怪状态") is None


class TestUrlBuilder:
    def test_build_search_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 设置 base url
        monkeypatch.setenv("TEZ_TCUM_BASE_URL", "http://tcum.example.com")
        # 强制重新加载 settings
        from app.config import get_settings

        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl = TCUMBrowserImpl()
        url = impl._build_search_url("TYSV00000001")
        assert url == "http://tcum.example.com/cmdb/product/search?key=TYSV00000001"
        assert impl._build_search_url("A B") == (
            "http://tcum.example.com/cmdb/product/search?key=A+B"
        )
        # 末尾斜杠也能处理
        get_settings.cache_clear()  # type: ignore[attr-defined]
        monkeypatch.setenv("TEZ_TCUM_BASE_URL", "http://tcum.example.com/")
        get_settings.cache_clear()  # type: ignore[attr-defined]
        impl2 = TCUMBrowserImpl()
        assert impl2._build_search_url("X")[-len("/cmdb/product/search?key=X") :] == (
            "/cmdb/product/search?key=X"
        )


@pytest.mark.asyncio
class TestFetchRows:
    """mock BrowserSession.page() / page.goto / page.eval_on_selector_all。"""

    async def test_auth_expired_raises(self) -> None:
        impl = TCUMBrowserImpl()

        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "https://passport.example.com/login?redirect=/cmdb"
        page.eval_on_selector_all = AsyncMock(return_value=[])

        with patch(
            "app.clients.tcum_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            with pytest.raises(BrowserAuthExpired):
                await impl._fetch_rows("http://tcum.example.com/q?key=X")

    async def test_no_rows_returns_empty(self) -> None:
        impl = TCUMBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://tcum.example.com/q?key=X"
        page.eval_on_selector_all = AsyncMock(return_value=[])

        with patch(
            "app.clients.tcum_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            rows = await impl._fetch_rows("http://tcum.example.com/q?key=X")
            assert rows == []

    async def test_get_by_asset_full_pipeline(self) -> None:
        impl = TCUMBrowserImpl()
        page = MagicMock()
        page.goto = AsyncMock()
        page.url = "http://tcum.example.com/q?key=TYSV00000001"
        # 第一次选择器命中即返回我们的样例数据
        page.eval_on_selector_all = AsyncMock(return_value=[SAMPLE_CELLS])

        with patch(
            "app.clients.tcum_browser.BrowserSession.page",
            _fake_page_ctx(page),
        ):
            data = await impl.get_by_asset("TYSV00000001")
            assert data is not None
            assert data["asset_id"] == "TYSV00000001"
            assert data["ip"] == "10.0.0.10"
            assert data["use_years"] == 5.9


def _fake_page_ctx(page: MagicMock):  # noqa: ANN202
    """构造一个 ``async with BrowserSession.page() as p`` 兼容的 fake。"""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():  # noqa: ANN202
        yield page

    return MagicMock(side_effect=_ctx)


@pytest.mark.asyncio
async def test_get_by_asset_empty_returns_none() -> None:
    impl = TCUMBrowserImpl()
    assert await impl.get_by_asset("") is None
    assert await impl.search_by_ip("") is None
