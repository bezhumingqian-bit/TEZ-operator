"""性能基准测试 — 全 mock 模式，验证关键路径耗时门槛。

默认 ``@pytest.mark.slow`` 跳过；显式 ``pytest -m slow`` 才运行。
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.host import HostInfo, HostMeta
from app.services.cache_service import CacheService
from app.services.host_service import HostService

pytestmark = pytest.mark.slow  # CI 默认 -m "not slow"


def _fake_host(asset_id: str = "TYSV00000001") -> HostInfo:
    return HostInfo(
        asset_id=asset_id,
        ip="10.0.0.1",
        zone="zone_a",
        machine_type="MOCK-1G",
        status="online",
        owner="alice",
        **{"_meta": HostMeta(data_sources=["cmdb"])},
    )


def _make_service() -> HostService:
    cmdb = MagicMock()
    cmdb.get_by_asset = AsyncMock(side_effect=lambda x: {"asset_id": x, "ip": "10.0.0.1"})
    cmdb.get_by_ip = AsyncMock(return_value={"asset_id": "TYSV00000001"})
    cmdb.list_by_zone = AsyncMock(return_value=[])
    cmdb.close = AsyncMock(return_value=None)

    tcum = MagicMock()
    tcum.get_by_asset = AsyncMock(return_value=None)
    tcum.search_by_ip = AsyncMock(return_value=None)
    tcum.close = AsyncMock(return_value=None)

    idcrm = MagicMock()
    idcrm.get_position = AsyncMock(return_value=None)
    idcrm.close = AsyncMock(return_value=None)

    return HostService(cmdb=cmdb, tcum=tcum, idcrm=idcrm, cache=CacheService())


@pytest.mark.asyncio
async def test_single_query_under_1s() -> None:
    """mock 模式下单条查询 < 1s。"""
    svc = _make_service()
    t0 = time.perf_counter()
    host = await svc.get_host("TYSV00000001")
    elapsed = time.perf_counter() - t0
    assert host is not None
    assert elapsed < 1.0, f"单条查询 {elapsed:.3f}s 超过 1s 门槛"


@pytest.mark.asyncio
async def test_batch_100_under_30s() -> None:
    """mock 模式下批量 100 条 < 30s（实际应 < 1s）。"""
    svc = _make_service()
    ids = [f"TYSV0000{i:04d}" for i in range(100)]
    t0 = time.perf_counter()
    results = await svc.batch_get_hosts(ids)
    elapsed = time.perf_counter() - t0
    assert len(results) == 100
    assert elapsed < 30.0, f"批量 100 条 {elapsed:.3f}s 超过 30s 门槛"


@pytest.mark.asyncio
async def test_concurrent_under_load() -> None:
    """50 个独立请求 asyncio.gather，验证不会因为锁争抢卡死。"""
    svc = _make_service()
    t0 = time.perf_counter()
    results = await asyncio.gather(*(svc.get_host(f"TYSV0000{i:04d}") for i in range(50)))
    elapsed = time.perf_counter() - t0
    assert all(r is not None for r in results)
    assert elapsed < 5.0, f"50 并发 {elapsed:.3f}s 超过 5s 门槛"
