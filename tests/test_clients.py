"""3 个客户端的 mock 路径单测。"""

from __future__ import annotations

import pytest

from app.clients.ccdb import CCDBClient
from app.clients.idcrm import IDCRMClient
from app.clients.tcum import TCUMClient


@pytest.mark.asyncio
class TestCCDBClient:
    async def test_get_by_asset(self) -> None:
        client = CCDBClient(mode="mock")
        data = await client.get_by_asset("TYSV00000001")
        assert data is not None
        assert data["asset_id"] == "TYSV00000001"
        assert data["ip"].startswith("10.0.")
        assert data["module"]
        assert data["customer"] in {"customer_a", "customer_b", "customer_c"}
        assert data["_source"] == "ccdb-mock"

    async def test_get_by_asset_empty(self) -> None:
        client = CCDBClient(mode="mock")
        assert await client.get_by_asset("") is None

    async def test_get_by_ip(self) -> None:
        client = CCDBClient(mode="mock")
        data = await client.get_by_ip("10.0.0.5")
        assert data is not None
        assert data["ip"] == "10.0.0.5"
        assert data["asset_id"]

    async def test_list_by_zone(self) -> None:
        client = CCDBClient(mode="mock")
        items = await client.list_by_zone("ap-shanghai-tea-3", limit=5)
        assert len(items) == 5
        assert all(it["zone"] == "ap-shanghai-tea-3" for it in items)

    async def test_api_mode_raises(self) -> None:
        client = CCDBClient(mode="api")
        with pytest.raises(NotImplementedError):
            await client.get_by_asset("TYSV00000001")


@pytest.mark.asyncio
class TestTCUMClient:
    async def test_get_by_asset(self) -> None:
        client = TCUMClient(mode="mock")
        data = await client.get_by_asset("TYSV00000001")
        assert data is not None
        assert data["idc"]
        assert data["cabinet"]
        assert data["machine_type"]
        assert isinstance(data["history"], list)
        assert len(data["history"]) >= 2

    async def test_search_by_ip(self) -> None:
        client = TCUMClient(mode="mock")
        data = await client.search_by_ip("10.0.0.5")
        assert data is not None
        assert data["asset_id"]

    async def test_api_mode_raises(self) -> None:
        client = TCUMClient(mode="api")
        with pytest.raises(NotImplementedError):
            await client.get_by_asset("TYSV00000001")


@pytest.mark.asyncio
class TestIDCRMClient:
    async def test_get_position(self) -> None:
        client = IDCRMClient(mode="mock")
        data = await client.get_position("示例机房A1", "A-12", "TYSV00000001")
        assert data is not None
        assert data["idc"] == "示例机房A1"
        assert data["cabinet"] == "A-12"
        assert data["position"].startswith("A-12-")
        assert data["has_tpc"] is True

    async def test_no_idc(self) -> None:
        client = IDCRMClient(mode="mock")
        assert await client.get_position("") is None
