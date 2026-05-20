"""HostService 单测：mock 三个 client 验证融合 / 缓存 / 降级 / 批量。

覆盖范围：
- _merge() 字段合并优先级（CCDB 优先 / TCUM 次之 / IDC 仅补机位）
- get_host: 缓存未命中走 client → 写缓存
- get_host: 缓存命中直返
- get_host: BrowserAuthExpired 降级 partial
- get_host: 全失败返回 None
- get_host_by_ip 路径
- list_zone_hosts 路径
- batch_get_hosts: 单条失败不影响其他
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.clients.base import BrowserAuthExpired
from app.schemas.host import HostInfo
from app.services.cache_service import CacheService
from app.services.host_service import CACHE_KEY_HOST, HostService

# ─────────────────────────── helpers ───────────────────────────


def _ccdb_payload(asset_id: str = "TYSV00000001") -> dict:
    return {
        "asset_id": asset_id,
        "ip": "10.0.0.1",
        "zone": "zone_a",
        "module": "ten1.customer_a-PRD",
        "customer": "customer_a",
        "app_id": "0000000000",
        "machine_type": "MOCK-CCDB",
        "status": "online",
        "has_tpc": True,
        "billing_tags": {"tag_a": "1"},
        "_source": "ccdb-mock",
    }


def _tcum_payload(asset_id: str = "TYSV00000001") -> dict:
    return {
        "asset_id": asset_id,
        "ip": "10.0.0.99",  # 应被 CCDB 覆盖
        "idc": "示例机房A1",
        "cabinet": "A-12",
        "machine_type": "MOCK-TCUM",  # 应被 CCDB 覆盖
        "owner": "alice",
        "backup_owners": ["bob", "carol"],
        "city": "城市A",
        "server_type": "Server",
        "use_years": 5.9,
        "history": [
            {
                "event_type": "投放",
                "event_at": "2025-01-01T00:00:00+00:00",
                "to_module": "ten1.customer_a-PRD",
                "source": "tcum",
            }
        ],
        "_source": "tcum-mock",
    }


def _idc_payload() -> dict:
    return {
        "idc": "示例机房A1",
        "cabinet": "A-12",
        "position": "A-12-3",
        "has_tpc": True,
        "_source": "idcrm-mock",
    }


def _make_service(
    ccdb_resp=None,
    tcum_resp=None,
    idc_resp=None,
    ccdb_exc=None,
    tcum_exc=None,
    idc_exc=None,
    cache: CacheService | None = None,
) -> HostService:
    """构造一个三 client 全 mock 的 HostService。"""
    ccdb = MagicMock()
    if ccdb_exc is not None:
        ccdb.get_by_asset = AsyncMock(side_effect=ccdb_exc)
        ccdb.get_by_ip = AsyncMock(side_effect=ccdb_exc)
        ccdb.list_by_zone = AsyncMock(side_effect=ccdb_exc)
    else:
        ccdb.get_by_asset = AsyncMock(return_value=ccdb_resp)
        ccdb.get_by_ip = AsyncMock(return_value=ccdb_resp)
        ccdb.list_by_zone = AsyncMock(return_value=ccdb_resp if isinstance(ccdb_resp, list) else [])
    ccdb.close = AsyncMock(return_value=None)

    tcum = MagicMock()
    if tcum_exc is not None:
        tcum.get_by_asset = AsyncMock(side_effect=tcum_exc)
        tcum.search_by_ip = AsyncMock(side_effect=tcum_exc)
    else:
        tcum.get_by_asset = AsyncMock(return_value=tcum_resp)
        tcum.search_by_ip = AsyncMock(return_value=tcum_resp)
    tcum.close = AsyncMock(return_value=None)

    idcrm = MagicMock()
    if idc_exc is not None:
        idcrm.get_position = AsyncMock(side_effect=idc_exc)
    else:
        idcrm.get_position = AsyncMock(return_value=idc_resp)
    idcrm.close = AsyncMock(return_value=None)

    return HostService(ccdb=ccdb, tcum=tcum, idcrm=idcrm, cache=cache or CacheService())


# ─────────────────────────── _merge 优先级 ───────────────────────────


class TestMerge:
    def test_ccdb_overrides_tcum_for_machine_type(self) -> None:
        svc = _make_service()
        merged = svc._merge(
            "TYSV00000001",
            _ccdb_payload(),
            _tcum_payload(),
            _idc_payload(),
            errors={},
        )
        # CCDB 的 machine_type 应优先（_merge 第一个 or）
        assert merged.machine_type == "MOCK-CCDB"
        # CCDB 的 ip 优先
        assert merged.ip == "10.0.0.1"

    def test_tcum_owner_kept_when_ccdb_no_owner(self) -> None:
        svc = _make_service()
        merged = svc._merge(
            "TYSV00000001",
            _ccdb_payload(),
            _tcum_payload(),
            _idc_payload(),
            errors={},
        )
        # owner 只有 TCUM 提供
        assert merged.owner == "alice"
        assert merged.backup_owners == ["bob", "carol"]
        assert merged.city == "城市A"

    def test_idc_supplies_position(self) -> None:
        svc = _make_service()
        merged = svc._merge(
            "TYSV00000001",
            _ccdb_payload(),
            _tcum_payload(),
            _idc_payload(),
            errors={},
        )
        assert merged.position == "A-12-3"
        # cabinet 优先 IDC，再 TCUM 再 CCDB
        assert merged.cabinet == "A-12"

    def test_data_sources_recorded(self) -> None:
        svc = _make_service()
        merged = svc._merge(
            "TYSV00000001",
            _ccdb_payload(),
            _tcum_payload(),
            _idc_payload(),
            errors={},
        )
        assert "ccdb" in merged.meta.data_sources
        assert "tcum" in merged.meta.data_sources
        assert "idcrm" in merged.meta.data_sources

    def test_partial_when_errors(self) -> None:
        svc = _make_service()
        merged = svc._merge(
            "TYSV00000001",
            _ccdb_payload(),
            None,
            None,
            errors={"tcum": "boom"},
        )
        assert merged.meta.partial is True
        assert merged.meta.errors == {"tcum": "boom"}

    def test_history_parsed(self) -> None:
        svc = _make_service()
        merged = svc._merge(
            "TYSV00000001",
            _ccdb_payload(),
            _tcum_payload(),
            None,
            errors={},
        )
        assert len(merged.history) == 1
        assert merged.history[0].event_type == "投放"

    def test_history_invalid_skipped(self) -> None:
        svc = _make_service()
        tcum = _tcum_payload()
        tcum["history"] = [
            {"bad": "no event_at"},  # 非法
            {  # 合法
                "event_type": "维修",
                "event_at": "2025-02-01T00:00:00+00:00",
                "source": "tcum",
            },
        ]
        merged = svc._merge("TYSV00000001", None, tcum, None, errors={})
        assert len(merged.history) == 1
        assert merged.history[0].event_type == "维修"


# ─────────────────────────── get_host 路径 ───────────────────────────


@pytest.mark.asyncio
class TestGetHost:
    async def test_full_three_sources(self) -> None:
        svc = _make_service(
            ccdb_resp=_ccdb_payload(),
            tcum_resp=_tcum_payload(),
            idc_resp=_idc_payload(),
        )
        host = await svc.get_host("TYSV00000001")
        assert host is not None
        assert host.asset_id == "TYSV00000001"
        assert host.position == "A-12-3"
        assert host.meta.partial is False
        assert host.meta.from_cache is False

    async def test_cache_hit_returns_from_cache(self) -> None:
        cache = CacheService()
        # 预填缓存
        await cache.set(
            CACHE_KEY_HOST.format(asset_id="TYSV00000001"),
            {
                "asset_id": "TYSV00000001",
                "ip": "10.0.0.1",
                "_meta": {"from_cache": False, "data_sources": ["ccdb"]},
            },
        )
        svc = _make_service(
            ccdb_resp=_ccdb_payload(),
            tcum_resp=_tcum_payload(),
            cache=cache,
        )
        host = await svc.get_host("TYSV00000001")
        assert host is not None
        assert host.meta.from_cache is True
        # 命中缓存 → client 不应被调用
        svc.ccdb.get_by_asset.assert_not_called()  # type: ignore[attr-defined]

    async def test_one_client_fails_partial(self) -> None:
        # tcum 失败，ccdb 成功
        svc = _make_service(
            ccdb_resp=_ccdb_payload(),
            tcum_exc=RuntimeError("tcum boom"),
        )
        host = await svc.get_host("TYSV00000001")
        assert host is not None
        assert host.meta.partial is True
        assert "tcum" in host.meta.errors
        assert host.machine_type == "MOCK-CCDB"

    async def test_browser_auth_expired_handled_as_partial(self) -> None:
        svc = _make_service(
            ccdb_resp=_ccdb_payload(),
            tcum_exc=BrowserAuthExpired("login expired"),
        )
        host = await svc.get_host("TYSV00000001")
        assert host is not None
        assert host.meta.partial is True
        assert host.meta.errors.get("tcum") == "browser_auth_expired"

    async def test_all_fail_returns_none(self) -> None:
        svc = _make_service(
            ccdb_exc=RuntimeError("c boom"),
            tcum_exc=RuntimeError("t boom"),
        )
        host = await svc.get_host("TYSV00000001")
        assert host is None

    async def test_empty_asset_id(self) -> None:
        svc = _make_service()
        assert await svc.get_host("") is None

    async def test_writes_cache_after_miss(self) -> None:
        cache = CacheService()
        svc = _make_service(
            ccdb_resp=_ccdb_payload(),
            tcum_resp=_tcum_payload(),
            idc_resp=_idc_payload(),
            cache=cache,
        )
        await svc.get_host("TYSV00000001")
        # 缓存里应有此 key
        cached = await cache.get(CACHE_KEY_HOST.format(asset_id="TYSV00000001"))
        assert cached is not None
        # raw_json 应被排除（reviewer 建议-2）
        assert "raw_json" not in cached


# ─────────────────────────── get_host_by_ip 路径 ───────────────────────────


@pytest.mark.asyncio
class TestGetHostByIp:
    async def test_full_path(self) -> None:
        svc = _make_service(
            ccdb_resp=_ccdb_payload(),
            tcum_resp=_tcum_payload(),
            idc_resp=_idc_payload(),
        )
        host = await svc.get_host_by_ip("10.0.0.1")
        assert host is not None
        assert host.asset_id == "TYSV00000001"

    async def test_empty_ip(self) -> None:
        svc = _make_service()
        assert await svc.get_host_by_ip("") is None

    async def test_not_found(self) -> None:
        svc = _make_service(ccdb_resp=None, tcum_resp=None)
        assert await svc.get_host_by_ip("10.0.0.99") is None

    async def test_cache_hit_by_ip(self) -> None:
        cache = CacheService()
        from app.services.host_service import CACHE_KEY_HOST_BY_IP

        await cache.set(
            CACHE_KEY_HOST_BY_IP.format(ip="10.0.0.1"),
            {"asset_id": "TYSV00000001", "ip": "10.0.0.1"},
        )
        svc = _make_service(cache=cache)
        host = await svc.get_host_by_ip("10.0.0.1")
        assert host is not None
        assert host.meta.from_cache is True

    async def test_idcrm_failure_does_not_block(self) -> None:
        svc = _make_service(
            ccdb_resp=_ccdb_payload(),
            tcum_resp=_tcum_payload(),
            idc_exc=RuntimeError("idc boom"),
        )
        host = await svc.get_host_by_ip("10.0.0.1")
        assert host is not None
        assert host.meta.partial is True
        assert "idcrm" in host.meta.errors


# ─────────────────────────── list_zone_hosts 路径 ───────────────────────────


@pytest.mark.asyncio
class TestListZoneHosts:
    async def test_returns_hosts(self) -> None:
        svc = _make_service(ccdb_resp=[_ccdb_payload(), _ccdb_payload("TYSV00000002")])
        hosts = await svc.list_zone_hosts("zone_a")
        assert len(hosts) == 2
        assert all(isinstance(h, HostInfo) for h in hosts)

    async def test_empty_zone(self) -> None:
        svc = _make_service()
        assert await svc.list_zone_hosts("") == []

    async def test_ccdb_failure_returns_empty(self) -> None:
        svc = _make_service(ccdb_exc=RuntimeError("boom"))
        assert await svc.list_zone_hosts("zone_a") == []

    async def test_zone_cache_hit(self) -> None:
        cache = CacheService()
        from app.services.host_service import CACHE_KEY_ZONE

        await cache.set(
            CACHE_KEY_ZONE.format(zone="zone_a"),
            [{"asset_id": "TYSV00000001"}],
        )
        svc = _make_service(cache=cache)
        hosts = await svc.list_zone_hosts("zone_a")
        assert len(hosts) == 1
        assert hosts[0].meta.from_cache is True


@pytest.mark.asyncio
class TestListZones:
    async def test_returns_mock(self) -> None:
        svc = _make_service()
        zones = await svc.list_zones()
        assert "zone_a" in zones
        assert "zone_b" in zones
        # 严格脱敏：不应有真实命名格式
        assert all("ap-" not in z for z in zones)

    async def test_caches(self) -> None:
        cache = CacheService()
        svc = _make_service(cache=cache)
        z1 = await svc.list_zones()
        z2 = await svc.list_zones()
        assert z1 == z2


# ─────────────────────────── batch_get_hosts 路径 ───────────────────────────


@pytest.mark.asyncio
class TestBatchGetHosts:
    async def test_one_fails_others_succeed(self) -> None:
        ccdb = MagicMock()
        ccdb.close = AsyncMock(return_value=None)

        async def _ccdb(asset_id: str):
            if asset_id == "TYSV00000002":
                raise RuntimeError("boom")
            return _ccdb_payload(asset_id)

        ccdb.get_by_asset = AsyncMock(side_effect=_ccdb)

        tcum = MagicMock()
        tcum.get_by_asset = AsyncMock(return_value=None)
        tcum.close = AsyncMock(return_value=None)
        idcrm = MagicMock()
        idcrm.get_position = AsyncMock(return_value=None)
        idcrm.close = AsyncMock(return_value=None)

        svc = HostService(ccdb=ccdb, tcum=tcum, idcrm=idcrm, cache=CacheService())
        results = await svc.batch_get_hosts(["TYSV00000001", "TYSV00000002", "TYSV00000003"])

        assert len(results) == 3
        # 第 1、3 条成功，第 2 条 client 异常被 _unwrap 吞 → host 仍存在但 partial=True
        # （注意：当前实现 _unwrap 把 client 异常变 partial，host 仍非 None）
        ids = [r[0] for r in results]
        assert ids == ["TYSV00000001", "TYSV00000002", "TYSV00000003"]


# ─────────────────────────── close ───────────────────────────


@pytest.mark.asyncio
async def test_close_calls_each_client() -> None:
    svc = _make_service()
    await svc.close()
    svc.ccdb.close.assert_awaited()  # type: ignore[attr-defined]
    svc.tcum.close.assert_awaited()  # type: ignore[attr-defined]
    svc.idcrm.close.assert_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_get_host_unwrap_non_dict_treated_as_none() -> None:
    """_unwrap 对非 dict 结果应返回 None。"""
    svc = _make_service(
        ccdb_resp="not-a-dict",  # type: ignore[arg-type]
        tcum_resp=_tcum_payload(),
    )
    host = await svc.get_host("TYSV00000001")
    # ccdb 给的非 dict → 被当成 None 处理；tcum 仍提供数据
    assert host is not None
    assert host.owner == "alice"  # tcum 数据保留
