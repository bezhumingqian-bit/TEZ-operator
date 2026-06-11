"""HostService：核心融合逻辑。

数据流（11 文档 § 3.1）：
    1. 缓存优先
    2. 并发拉 TCUM + CMDB
    3. 用 TCUM 拿到的 idc/cabinet 再去 IDCRM 补机位
    4. _merge() 融合（CMDB > TCUM > IDC）
    5. 写回缓存

W2 增强：
    - 处理 ``BrowserAuthExpired`` —— TCUM 浏览器登录态失效时降级 + 告警
    - 缓存 round-trip 显式 ``exclude={"raw_json"}``（reviewer 建议-2）
    - meta.last_sync_at 改用 UTC 时区（可选-1）
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.clients.base import BrowserAuthExpired
from app.clients.cmdb import CMDBClient
from app.clients.idcrm import IDCRMClient
from app.clients.tcum import TCUMClient
from app.config import get_settings
from app.schemas.host import HostHistoryEvent, HostInfo, HostMeta, ZoneInstanceStat
from app.services.cache_service import CacheService
from app.services.cache_service import cache as default_cache
from app.utils.alert import alert_fire_and_forget
from app.utils.logger import get_logger

log = get_logger(__name__)

CACHE_KEY_HOST = "host:{asset_id}"
CACHE_KEY_HOST_BY_IP = "host:ip:{ip}"
CACHE_KEY_ZONE = "zone:{zone}:hosts"
CACHE_KEY_ZONES_LIST = "zones:list"
CACHE_KEY_ZONE_INSTANCE_STATS = "zone:{zone}:instance_stats"

CACHE_DUMP_KW = {"by_alias": True, "mode": "json", "exclude": {"raw_json"}}

from app.utils.normalize import normalize_status

# ── 占位 zone 列表（mock 模式时 GET /api/v1/zones 用）──
# 严格脱敏：不带任何真实城市/产品代号（docs/16 § 二），
# 与前端 W3 约定的 zone_a~zone_e 占位保持一致。
# W4 切真实 CMDB 后由 CMDBClient.list_zones() 提供
MOCK_ZONES: list[str] = [
    "zone_a",
    "zone_b",
    "zone_c",
    "zone_d",
    "zone_e",
]


class HostService:
    """主机查询融合服务。"""

    def __init__(
        self,
        cmdb: CMDBClient | None = None,
        tcum: TCUMClient | None = None,
        idcrm: IDCRMClient | None = None,
        cache: CacheService | None = None,
    ) -> None:
        self.cmdb = cmdb or CMDBClient()
        self.tcum = tcum or TCUMClient()
        self.idcrm = idcrm or IDCRMClient()
        self.cache = cache or default_cache

    # ─────────────────── public ───────────────────

    async def get_host(self, asset_id: str) -> HostInfo | None:
        """按固资号查询单台机的全貌。

        数据源优先级：
        1. 内存缓存（热数据秒级返回）
        2. 本地数据库 host_cache 表（7天有效期）
        3. 云端拉取（TCUM + CMDB + IDCRM）→ 写回本地库
        """

        if not asset_id:
            return None

        key = CACHE_KEY_HOST.format(asset_id=asset_id.upper())
        cached = await self.cache.get(key)
        if cached:
            log.debug("host.cache_hit", asset_id=asset_id)
            return self._dict_to_host(cached, from_cache=True)

        # 查本地数据库
        db_result = await self._get_from_db(asset_id)
        if db_result:
            log.debug("host.db_hit", asset_id=asset_id)
            # 回写内存缓存
            await self.cache.set(key, db_result.model_dump(**CACHE_DUMP_KW))
            return db_result

        # 并发拉 CMDB + TCUM
        cmdb_task = self.cmdb.get_by_asset(asset_id)
        tcum_task = self.tcum.get_by_asset(asset_id)
        cmdb_data, tcum_data = await asyncio.gather(cmdb_task, tcum_task, return_exceptions=True)

        errors: dict[str, str] = {}
        cmdb_dict = self._unwrap("cmdb", cmdb_data, errors)
        tcum_dict = self._unwrap("tcum", tcum_data, errors)

        # 用 TCUM 的 idc/cabinet 再查 IDCRM
        idc_dict: dict[str, Any] | None = None
        if tcum_dict and tcum_dict.get("idc"):
            try:
                idc_dict = await self.idcrm.get_position(
                    tcum_dict["idc"], tcum_dict.get("cabinet"), asset_id
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("host.idcrm_failed", asset_id=asset_id, error=str(exc))
                errors["idcrm"] = str(exc)

        if not cmdb_dict and not tcum_dict:
            log.info("host.not_found", asset_id=asset_id, errors=errors)
            return None

        merged = self._merge(asset_id.upper(), cmdb_dict, tcum_dict, idc_dict, errors)
        await self.cache.set(key, merged.model_dump(**CACHE_DUMP_KW))

        # 写入本地数据库持久化
        await self._save_to_db(merged)

        return merged

    async def get_host_by_ip(self, ip: str) -> HostInfo | None:
        if not ip:
            return None
        key = CACHE_KEY_HOST_BY_IP.format(ip=ip)
        cached = await self.cache.get(key)
        if cached:
            log.debug("host.cache_hit_by_ip", ip=ip)
            return self._dict_to_host(cached, from_cache=True)

        cmdb_task = self.cmdb.get_by_ip(ip)
        tcum_task = self.tcum.search_by_ip(ip)
        cmdb_data, tcum_data = await asyncio.gather(cmdb_task, tcum_task, return_exceptions=True)
        errors: dict[str, str] = {}
        cmdb_dict = self._unwrap("cmdb", cmdb_data, errors)
        tcum_dict = self._unwrap("tcum", tcum_data, errors)

        if not cmdb_dict and not tcum_dict:
            return None

        asset_id = (cmdb_dict or {}).get("asset_id") or (tcum_dict or {}).get("asset_id") or ""

        idc_dict: dict[str, Any] | None = None
        if tcum_dict and tcum_dict.get("idc"):
            try:
                idc_dict = await self.idcrm.get_position(
                    tcum_dict["idc"], tcum_dict.get("cabinet"), asset_id
                )
            except Exception as exc:  # noqa: BLE001
                errors["idcrm"] = str(exc)

        merged = self._merge(asset_id, cmdb_dict, tcum_dict, idc_dict, errors)
        await self.cache.set(key, merged.model_dump(**CACHE_DUMP_KW))
        # 反向键也写一份，下次按 asset_id 查能命中
        if merged.asset_id:
            await self.cache.set(
                CACHE_KEY_HOST.format(asset_id=merged.asset_id),
                merged.model_dump(**CACHE_DUMP_KW),
            )
        return merged

    async def list_zone_hosts(self, zone: str) -> list[HostInfo]:
        if not zone:
            return []
        key = CACHE_KEY_ZONE.format(zone=zone)
        cached = await self.cache.get(key)
        if cached:
            log.debug("host.cache_hit_zone", zone=zone)
            return [self._dict_to_host(d, from_cache=True) for d in cached]

        try:
            rows = await self.cmdb.list_by_zone(zone)
        except Exception as exc:  # noqa: BLE001
            log.warning("host.list_zone_failed", zone=zone, error=str(exc))
            return []

        hosts: list[HostInfo] = []
        for row in rows:
            asset = row.get("asset_id") or ""
            host = self._merge(asset, row, None, None, errors={})
            hosts.append(host)

        await self.cache.set(
            key,
            [h.model_dump(**CACHE_DUMP_KW) for h in hosts],
            ttl=get_settings().cache_zone_ttl,
        )
        return hosts

    async def list_zones(self) -> list[str]:
        """返回当前可用的 zone 列表（从 zone_mapping 获取真实可用区）。"""

        cached = await self.cache.get(CACHE_KEY_ZONES_LIST)
        if cached:
            return list(cached)

        from app.data.zone_mapping import ZONE_IDC_MAPPING
        zones = sorted(ZONE_IDC_MAPPING.keys())

        await self.cache.set(
            CACHE_KEY_ZONES_LIST,
            zones,
            ttl=get_settings().cache_zone_ttl,
        )
        return zones

    async def get_zone_instance_stats(self, zones: list[str]) -> list[ZoneInstanceStat]:
        """查询一个或多个区域的线上实例资源统计。

        注意：此功能依赖 CMDB OpenAPI，当前如为 mock 模式则返回空统计。
        """

        normalized = [z.strip() for z in zones if z and z.strip()]
        if not normalized:
            return []

        results: list[ZoneInstanceStat] = []
        for zone in normalized:
            cache_key = CACHE_KEY_ZONE_INSTANCE_STATS.format(zone=zone)
            cached = await self.cache.get(cache_key)
            if cached:
                results.append(ZoneInstanceStat(**cached))
                continue

            try:
                raw = await self.cmdb.get_instance_stats_by_zone(zone)
                if not raw or not isinstance(raw, dict):
                    stat = self._fallback_instance_stat(zone)
                else:
                    stat = ZoneInstanceStat(**raw)
            except Exception as exc:  # noqa: BLE001
                log.warning("zone.instance_stats_failed", zone=zone, error=str(exc))
                stat = self._fallback_instance_stat(zone)

            await self.cache.set(
                cache_key,
                stat.model_dump(mode="json"),
                ttl=get_settings().cache_zone_ttl,
            )
            results.append(stat)
        return results

    def _fallback_instance_stat(self, zone: str) -> ZoneInstanceStat:
        """区域统计兜底：当上游统计失败时基于母机列表估算。"""

        return ZoneInstanceStat(
            zone=zone,
            host_count=0,
            total_instances=0,
            online_instances=0,
            offline_instances=0,
            maintenance_instances=0,
            by_machine_type={},
            by_customer={},
        )

    async def batch_get_hosts(
        self, asset_ids: list[str]
    ) -> list[tuple[str, HostInfo | None, str | None]]:
        """并发批量查询；返回 (query, host_or_none, error_or_none) 列表。

        W3 增强：
        - 用 ``asyncio.Semaphore(settings.batch_concurrency)`` 限流，
          防止 100 条同时打开 100 个 BrowserContext page
        - 单条失败不影响其他（gather + per-task try/except）
        """

        s = get_settings()
        sem = asyncio.Semaphore(s.batch_concurrency)

        async def _one(qid: str) -> tuple[str, HostInfo | None, str | None]:
            async with sem:
                try:
                    host = await self.get_host(qid)
                    return qid, host, None
                except Exception as exc:  # noqa: BLE001
                    return qid, None, str(exc)

        return await asyncio.gather(*(_one(q) for q in asset_ids))

    async def batch_get_hosts_mixed(
        self, queries: list[tuple[str, str]]
    ) -> list[tuple[str, str, HostInfo | None, str | None]]:
        """并发批量查询（混合 asset_id / ip），用于 batch_search 路由。

        Args:
            queries: 列表，每项为 ``(query, query_type)``，``query_type`` ∈ ``asset_id / ip / *``

        Returns:
            ``(query, query_type, host_or_none, error_or_none)`` 列表，顺序与输入一致。
        """

        s = get_settings()
        sem = asyncio.Semaphore(s.batch_concurrency)

        async def _one(qid: str, qtype: str) -> tuple[str, str, HostInfo | None, str | None]:
            async with sem:
                try:
                    if qtype == "asset_id":
                        host = await self.get_host(qid)
                    elif qtype == "ip":
                        host = await self.get_host_by_ip(qid)
                    else:
                        return (
                            qid,
                            qtype,
                            None,
                            f"不支持的批量类型：{qtype}（仅支持固资号 / IP）",
                        )
                    return qid, qtype, host, None
                except Exception as exc:  # noqa: BLE001
                    return qid, qtype, None, str(exc)

        return await asyncio.gather(*(_one(q, t) for q, t in queries))

    async def close(self) -> None:
        """W2 lifespan close 用：释放三个 client（reviewer 建议-5）。"""
        await self.cmdb.close()
        await self.tcum.close()
        await self.idcrm.close()

    # ─────────────────── 本地数据库持久化 ───────────────────

    DB_EXPIRE_DAYS = 7  # 本地库数据有效期

    async def _get_from_db(self, asset_id: str) -> HostInfo | None:
        """从本地 host_cache 数据库表查找设备信息（7天有效期）。"""
        from datetime import timedelta

        from sqlalchemy import select, text
        from app.deps import _get_session_factory
        from app.models.host import HostCache

        try:
            factory = _get_session_factory()
            async with factory() as session:
                stmt = select(HostCache).where(HostCache.asset_id == asset_id.upper())
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if not row:
                    return None

                # 检查过期
                if row.last_sync_at:
                    if (datetime.now() - row.last_sync_at) > timedelta(days=self.DB_EXPIRE_DAYS):
                        log.debug("host.db_expired", asset_id=asset_id)
                        return None

                # 构造 HostInfo
                return HostInfo(
                    asset_id=row.asset_id,
                    ip=row.ip,
                    zone=row.zone,
                    machine_type=row.machine_type,
                    status=normalize_status(row.status),
                    idc=row.idc,
                    cabinet=row.cabinet,
                    position=row.position,
                    module=row.module,
                    _meta=HostMeta(
                        from_cache=True,
                        data_sources=["local_db"],
                        last_sync_at=row.last_sync_at,
                    ),
                )
        except Exception as exc:
            log.debug("host.db_read_error", asset_id=asset_id, error=str(exc))
            return None

    async def _save_to_db(self, host: HostInfo) -> None:
        """把查询结果持久化到 host_cache 数据库表。"""
        from sqlalchemy import text
        from app.deps import _get_session_factory
        from app.models.host import HostCache

        if not host.asset_id:
            return

        try:
            factory = _get_session_factory()
            async with factory() as session:
                # Upsert
                existing = await session.get(HostCache, host.asset_id)
                now = datetime.now()

                if existing:
                    existing.ip = host.ip
                    existing.zone = host.zone
                    existing.machine_type = host.machine_type
                    existing.status = host.status
                    existing.idc = host.idc
                    existing.cabinet = host.cabinet
                    existing.position = host.position
                    existing.module = host.module
                    existing.last_sync_at = now
                else:
                    row = HostCache(
                        asset_id=host.asset_id,
                        ip=host.ip,
                        zone=host.zone,
                        machine_type=host.machine_type,
                        status=host.status,
                        idc=host.idc,
                        cabinet=host.cabinet,
                        position=host.position,
                        module=host.module,
                        last_sync_at=now,
                    )
                    session.add(row)

                await session.commit()
                log.debug("host.db_saved", asset_id=host.asset_id)
        except Exception as exc:
            log.debug("host.db_write_error", asset_id=host.asset_id, error=str(exc))

    # ─────────────────── 内部 ───────────────────

    @staticmethod
    def _unwrap(
        client: str,
        result: Any,
        errors: dict[str, str],
    ) -> dict[str, Any] | None:
        """统一处理 asyncio.gather 里的异常 / None。

        - 对 ``BrowserAuthExpired`` 单独处理：log + 异步告警；
        - 其他异常照旧记到 errors，后续 partial 降级。
        """

        if isinstance(result, BrowserAuthExpired):
            log.error("host.browser_auth_expired", client=client, error=str(result))
            errors[client] = "browser_auth_expired"
            alert_fire_and_forget(
                title=f"{client.upper()} 浏览器登录态失效",
                content=(
                    f"客户端 `{client}` 在抓取时被踢回 SSO 登录页，"
                    "请到工位机执行 `python -m app.scripts.relogin` 或重启服务并扫码。"
                ),
                level="error",
            )
            return None
        if isinstance(result, Exception):
            log.warning("host.client_failed", client=client, error=str(result))
            errors[client] = str(result)
            return None
        if not result:
            return None
        if not isinstance(result, dict):
            return None
        return result

    @staticmethod
    def _to_history(items: list[dict[str, Any]]) -> list[HostHistoryEvent]:
        events: list[HostHistoryEvent] = []
        for it in items or []:
            try:
                events.append(HostHistoryEvent(**it))
            except Exception:  # noqa: BLE001
                continue
        return events

    def _merge(
        self,
        asset_id: str,
        cmdb: dict[str, Any] | None,
        tcum: dict[str, Any] | None,
        idc: dict[str, Any] | None,
        errors: dict[str, str],
    ) -> HostInfo:
        """三方数据融合：CMDB > TCUM > IDC。"""

        cmdb = cmdb or {}
        tcum = tcum or {}
        idc = idc or {}
        sources: list[str] = []
        if cmdb:
            sources.append("cmdb")
        if tcum:
            sources.append("tcum")
        if idc:
            sources.append("idcrm")

        # 历史轨迹（目前只有 TCUM 提供）
        history = self._to_history(tcum.get("history", []))

        meta = HostMeta(
            from_cache=False,
            data_sources=sources,
            last_sync_at=datetime.now(timezone.utc),  # noqa: UP017
            partial=bool(errors),
            errors=errors,
        )

        return HostInfo(
            asset_id=cmdb.get("asset_id") or tcum.get("asset_id") or asset_id,
            ip=cmdb.get("ip") or tcum.get("ip"),
            zone=cmdb.get("zone") or tcum.get("zone"),
            machine_type=cmdb.get("machine_type") or tcum.get("machine_type"),
            status=normalize_status(cmdb.get("status") or tcum.get("status")),
            idc=tcum.get("idc") or cmdb.get("idc"),
            cabinet=idc.get("cabinet") or tcum.get("cabinet") or cmdb.get("cabinet"),
            position=idc.get("position"),
            module=cmdb.get("module") or tcum.get("module"),
            customer=cmdb.get("customer"),
            app_id=str(cmdb.get("app_id")) if cmdb.get("app_id") is not None else None,
            has_tpc=idc.get("has_tpc") if idc else cmdb.get("has_tpc"),
            billing_tags=cmdb.get("billing_tags") or {},
            owner=tcum.get("owner"),
            backup_owners=tcum.get("backup_owners") or [],
            city=tcum.get("city"),
            server_type=tcum.get("server_type"),
            use_years=tcum.get("use_years"),
            history=history,
            raw_json={"cmdb": cmdb, "tcum": tcum, "idcrm": idc},
            **{"_meta": meta},
        )

    @staticmethod
    def _dict_to_host(data: dict[str, Any], from_cache: bool = False) -> HostInfo:
        """缓存里的 dict → HostInfo（透传 from_cache）。"""

        host = HostInfo.model_validate(data)
        if from_cache:
            host.meta.from_cache = True
        return host
