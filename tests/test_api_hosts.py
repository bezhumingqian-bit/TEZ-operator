"""Hosts API 端到端测试。

用 ``httpx.ASGITransport`` 直接打到 FastAPI app，绕开网络栈。
HostService 被替换为 mock，避免真实拉浏览器 / Redis。

覆盖 reviewer 建议-10：routers/hosts.py 当前 0% 覆盖。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.deps import get_host_service, set_host_service
from app.main import create_app
from app.schemas.host import HostInfo, HostMeta


def _fake_host(asset_id: str = "TYSV00000001") -> HostInfo:
    return HostInfo(
        asset_id=asset_id,
        ip="10.0.0.1",
        zone="zone_a",
        machine_type="MOCK-1G",
        status="online",
        idc="示例机房A1",
        cabinet="A-12",
        position="A-12-3",
        module="ten1.customer_a-PRD",
        customer="customer_a",
        app_id="0000000000",
        has_tpc=True,
        billing_tags={"tag_a": "1"},
        owner="alice",
        backup_owners=["bob"],
        history=[],
        **{"_meta": HostMeta(data_sources=["cmdb", "tcum"])},
    )


@pytest.fixture
def fake_service() -> MagicMock:
    svc = MagicMock()
    svc.get_host = AsyncMock(return_value=_fake_host())
    svc.get_host_by_ip = AsyncMock(return_value=_fake_host())
    svc.list_zone_hosts = AsyncMock(return_value=[_fake_host(), _fake_host("TYSV00000002")])
    svc.list_zones = AsyncMock(return_value=["zone_a", "zone_b", "zone_c"])
    svc.batch_get_hosts = AsyncMock(return_value=[("TYSV00000001", _fake_host(), None)])

    # W3：batch_get_hosts_mixed 默认逐条返回 host
    async def _mixed(queries):
        return [
            (q, t, _fake_host(q if t == "asset_id" else "TYSV00000001"), None) for q, t in queries
        ]

    svc.batch_get_hosts_mixed = AsyncMock(side_effect=_mixed)
    svc.close = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def app(fake_service: MagicMock):
    """构造 app 并注入 fake HostService。"""
    application = create_app()
    set_host_service(fake_service)
    # 同时注入 dependency override，确保 Depends(get_host_service) 拿到 fake
    application.dependency_overrides[get_host_service] = lambda: fake_service
    yield application
    set_host_service(None)
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─────────────────────────── /health ───────────────────────────


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "tez-operator"
    assert body["version"] == "1.1.0-alpha"


@pytest.mark.asyncio
async def test_root(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200


# ─────────────────────────── search ───────────────────────────


@pytest.mark.asyncio
class TestSearch:
    async def test_search_by_asset_id(self, client: AsyncClient, fake_service: MagicMock) -> None:
        resp = await client.get("/api/v1/hosts/search?q=TYSV00000001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["query_type"] == "asset_id"
        assert body["data"]["asset_id"] == "TYSV00000001"
        fake_service.get_host.assert_awaited_with("TYSV00000001")

    async def test_search_normalizes_lowercase_asset(
        self, client: AsyncClient, fake_service: MagicMock
    ) -> None:
        resp = await client.get("/api/v1/hosts/search?q=tysv00000001")
        assert resp.status_code == 200
        # normalize_query 后传给 service 的应为大写
        fake_service.get_host.assert_awaited_with("TYSV00000001")

    async def test_search_by_ip(self, client: AsyncClient, fake_service: MagicMock) -> None:
        resp = await client.get("/api/v1/hosts/search?q=10.0.0.5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["query_type"] == "ip"
        fake_service.get_host_by_ip.assert_awaited_with("10.0.0.5")

    async def test_search_by_zone(self, client: AsyncClient, fake_service: MagicMock) -> None:
        resp = await client.get("/api/v1/hosts/search?q=zone_a")
        assert resp.status_code == 200
        body = resp.json()
        assert body["query_type"] == "zone"
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 2

    async def test_search_invalid_returns_400(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/hosts/search?q=invalid_thing")
        assert resp.status_code == 400

    async def test_search_not_found_returns_404(
        self, client: AsyncClient, fake_service: MagicMock
    ) -> None:
        fake_service.get_host = AsyncMock(return_value=None)
        resp = await client.get("/api/v1/hosts/search?q=TYSV00009999")
        assert resp.status_code == 404

    async def test_search_ip_not_found(self, client: AsyncClient, fake_service: MagicMock) -> None:
        fake_service.get_host_by_ip = AsyncMock(return_value=None)
        resp = await client.get("/api/v1/hosts/search?q=10.0.0.99")
        assert resp.status_code == 404

    async def test_search_empty_q_422(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/hosts/search?q=")
        # FastAPI Query min_length=1 → 422
        assert resp.status_code == 422


# ─────────────────────────── /hosts/{asset_id} ───────────────────────────


@pytest.mark.asyncio
class TestDetail:
    async def test_detail_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/hosts/TYSV00000001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["asset_id"] == "TYSV00000001"

    async def test_detail_invalid_asset(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/hosts/not_an_asset")
        assert resp.status_code == 400

    async def test_detail_not_found(self, client: AsyncClient, fake_service: MagicMock) -> None:
        fake_service.get_host = AsyncMock(return_value=None)
        resp = await client.get("/api/v1/hosts/TYSV00009999")
        assert resp.status_code == 404


# ─────────────────────────── /batch_search ───────────────────────────


@pytest.mark.asyncio
class TestBatchSearch:
    async def test_basic_batch(self, client: AsyncClient, fake_service: MagicMock) -> None:
        resp = await client.post(
            "/api/v1/hosts/batch_search",
            json={"queries": ["TYSV00000001", "10.0.0.5"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["success_count"] == 2

    async def test_batch_includes_invalid(
        self, client: AsyncClient, fake_service: MagicMock
    ) -> None:
        resp = await client.post(
            "/api/v1/hosts/batch_search",
            json={"queries": ["TYSV00000001", "not-an-asset-or-ip"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        # 第一条 ok，第二条 unknown 路径会带错误（不在 service 调用里）
        items = body["items"]
        assert items[0]["success"] is True
        assert items[1]["success"] is False

    async def test_batch_partial_failure(
        self, client: AsyncClient, fake_service: MagicMock
    ) -> None:
        # batch_get_hosts_mixed 返回：第一条成功，第二条 host=None err=None（"未找到"路径）
        async def _mixed(queries):
            results = []
            for i, (q, t) in enumerate(queries):
                if i == 0:
                    results.append((q, t, _fake_host(q), None))
                else:
                    results.append((q, t, None, None))
            return results

        fake_service.batch_get_hosts_mixed = AsyncMock(side_effect=_mixed)
        resp = await client.post(
            "/api/v1/hosts/batch_search",
            json={"queries": ["TYSV00000001", "TYSV00009999"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success_count"] == 1
        assert body["items"][1]["error"] == "未找到"

    async def test_batch_too_many_returns_422(self, client: AsyncClient) -> None:
        # max 100 条
        resp = await client.post(
            "/api/v1/hosts/batch_search",
            json={"queries": [f"TYSV0000{i:04d}" for i in range(101)]},
        )
        assert resp.status_code == 422

    async def test_batch_all_empty_strings_422(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v1/hosts/batch_search",
            json={"queries": ["   ", ""]},
        )
        assert resp.status_code == 422

    async def test_batch_service_exception_captured(
        self, client: AsyncClient, fake_service: MagicMock
    ) -> None:
        # batch_get_hosts_mixed 返回 error 字段非空
        async def _mixed(queries):
            return [(q, t, None, "boom") for q, t in queries]

        fake_service.batch_get_hosts_mixed = AsyncMock(side_effect=_mixed)
        resp = await client.post(
            "/api/v1/hosts/batch_search",
            json={"queries": ["TYSV00000001"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success_count"] == 0
        assert "boom" in body["items"][0]["error"]


# ─────────────────────────── /zones/{zone}/hosts ───────────────────────────


@pytest.mark.asyncio
class TestZoneHosts:
    async def test_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/zones/zone_a/hosts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["zone"] == "zone_a"
        assert body["total"] == 2

    async def test_invalid_zone(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/zones/!!!/hosts")
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestListZones:
    async def test_returns_list(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/zones")
        assert resp.status_code == 200
        body = resp.json()
        assert "zones" in body
        assert body["zones"] == ["zone_a", "zone_b", "zone_c"]


# ─────────────────────────── /export ───────────────────────────


@pytest.mark.asyncio
class TestExportXlsx:
    async def test_export_basic(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/hosts/export?asset_ids=TYSV00000001,TYSV00000002")
        assert resp.status_code == 200
        # 头部声明
        assert (
            resp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in resp.headers["content-disposition"]
        assert ".xlsx" in resp.headers["content-disposition"]
        # 实际内容是 zip，xlsx 文件以 PK 开头
        assert resp.content[:2] == b"PK"

    async def test_export_empty_400(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/hosts/export?asset_ids=")
        # FastAPI Query min_length=1 → 422
        assert resp.status_code == 422

    async def test_export_only_commas_400(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/hosts/export?asset_ids=,,,")
        assert resp.status_code == 400

    async def test_export_invalid_asset(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/hosts/export?asset_ids=TYSV00000001,not_an_asset")
        assert resp.status_code == 400

    async def test_export_too_many(self, client: AsyncClient) -> None:
        too_many = ",".join(f"TYSV0000{i:04d}" for i in range(101))
        resp = await client.get(f"/api/v1/hosts/export?asset_ids={too_many}")
        assert resp.status_code == 400
