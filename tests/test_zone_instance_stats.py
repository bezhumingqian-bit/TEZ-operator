from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.host_service import HostService


@pytest.mark.asyncio
async def test_zone_instance_stats_service_mock(monkeypatch) -> None:
    monkeypatch.setenv("TEZ_CMDB_MODE", "mock")
    monkeypatch.setenv("TEZ_TCUM_MODE", "mock")
    monkeypatch.setenv("TEZ_IDCRM_MODE", "mock")
    from app.config import get_settings

    get_settings.cache_clear()

    service = HostService()

    stats = await service.get_zone_instance_stats(["zone_a", "zone_b"])

    assert len(stats) == 2
    assert stats[0].zone == "zone_a"
    assert stats[0].online_instances > 0
    assert stats[0].total_instances >= stats[0].online_instances
    assert stats[0].by_machine_type
    assert stats[0].by_customer


@pytest.mark.asyncio
async def test_zone_instance_stats_api() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/zones/instances/stats", params={"zones": "zone_a,zone_b"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 0
    assert data["total_zones"] == 2
    assert data["total_instances"] >= data["online_instances"]
    assert data["items"][0]["zone"] == "zone_a"


@pytest.mark.asyncio
async def test_zone_instance_stats_rejects_invalid_zone() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/zones/instances/stats", params={"zones": "bad-zone"})

    assert resp.status_code == 400
