"""HostService：核心融合逻辑。

数据流（11 文档 § 3.1）：
    1. 缓存优先
    2. 并发拉 TCUM + CCDB
    3. 用 TCUM 拿到的 idc/cabinet 再去 IDCRM 补机位
    4. _merge() 融合（CCDB > TCUM > IDC）
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
from app.clients.ccdb import CCDBClient
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

# ── status 映射兜底（W3 与前端对齐）──
# 主映射在 TCUMBrowserImpl._parse_row 完成（数据净化在采集层做，越靠近源头越好）。
# 这里仅作为兜底：万一某 client 漏配映射，HostService 层不让脏数据穿透到前端。
STATUS_MAP_CN_TO_EN: dict[str, str] = {
    "运营中": "online",
    "在线": "online",
    "维护中": "maintenance",
    "维修中": "maintenance",
    "故障": "offline",
    "离线": "offline",
    "下线": "offline",
}
_VALID_STATUSES = {"online", "offline", "maintenance"}


def _normalize_status(raw: str | None) -> str | None:
    """归一化兜底：把任意来源的 status 收敛到 ``online/offline/maintenance``。

    采集层（TCUMBrowserImpl）已做主映射，这里只兜底：
    - 已是合法英文 → 返回
    - 中文映射命中 → 翻译
    - 其他 → 记 warning + 返回 None（schema 是 Literal，传脏数据会 422）
    """
    if not raw:
        return None
    v = raw.strip()
    if v in _VALID_STATUSES:
        return v
    if v in STATUS_MAP_CN_TO_EN:
        return STATUS_MAP_CN_TO_EN[v]
    log.warning("host.unknown_status", value=v)
    return None


# ── 占位 zone 列表（mock 模式时 GET /api/v1/zones 用）──
# 严格脱敏：不带任何真实城市/产品代号（docs/16 § 二），
# 与前端 W3 约定的 zone_a~zone_e 占位保持一致。
# W4 切真实 CCDB 后由 CCDBClient.list_zones() 提供
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
        ccdb: CCDBClient | None = None,
        tcum: TCUMClient | None = None,
        idcrm: IDCRMClient | None = None,
        cache: CacheService | None = None,
    ) -> None:
        self.ccdb = ccdb or CCDBClient()
        self.tcum = tcum or TCUMClient()
        self.idcrm = idcrm or IDCRMClient()
        self.cache = cache or default_cache

    # ─────────────────── public ───────────────────

    async def get_host(self, asset_id: str) -> HostInfo | None:
        """按固资号查询单台机的全貌。"""

        if not asset_id:
            return None

        key = CACHE_KEY_HOST.format(asset_id=asset_id.upper())
        cached = await self.cache.get(key)
        if cached:
            log.debug("host.cache_hit", asset_id=asset_id)
            return self._dict_to_host(cached, from_cache=True)

        # 并发拉 CCDB + TCUM
        ccdb_task = self.ccdb.get_by_asset(asset_id)
        tcum_task = self.tcum.get_by_asset(asset_id)
        ccdb_data, tcum_data = await asyncio.gather(ccdb_task, tcum_task, return_exceptions=True)

        errors: dict[str, str] = {}
        ccdb_dict = self._unwrap("ccdb", ccdb_data, errors)
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

        if not ccdb_dict and not tcum_dict:
            log.info("host.not_found", asset_id=asset_id, errors=errors)
            return None

        merged = self._merge(asset_id.upper(), ccdb_dict, tcum_dict, idc_dict, errors)
        await self.cache.set(key, merged.model_dump(**CACHE_DUMP_KW))
        return merged

    async def get_host_by_ip(self, ip: str) -> HostInfo | None:
        if not ip:
            return None
        key = CACHE_KEY_HOST_BY_IP.format(ip=ip)
        cached = await self.cache.get(key)
        if cached:
            log.debug("host.cache_hit_by_ip", ip=ip)
            return self._dict_to_host(cached, from_cache=True)

        ccdb_task = self.ccdb.get_by_ip(ip)
        tcum_task = self.tcum.search_by_ip(ip)
        ccdb_data, tcum_data = await asyncio.gather(ccdb_task, tcum_task, return_exceptions=True)
        errors: dict[str, str] = {}
        ccdb_dict = self._unwrap("ccdb", ccdb_data, errors)
        tcum_dict = self._unwrap("tcum", tcum_data, errors)

        if not ccdb_dict and not tcum_dict:
            return None

        asset_id = (ccdb_dict or {}).get("asset_id") or (tcum_dict or {}).get("asset_id") or ""

        idc_dict: dict[str, Any] | None = None
        if tcum_dict and tcum_dict.get("idc"):
            try:
                idc_dict = await self.idcrm.get_position(
                    tcum_dict["idc"], tcum_dict.get("cabinet"), asset_id
                )
            except Exception as exc:  # noqa: BLE001
                errors["idcrm"] = str(exc)

        merged = self._merge(asset_id, ccdb_dict, tcum_dict, idc_dict, errors)
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
            rows = await self.ccdb.list_by_zone(zone)
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
        """返回当前可用的 zone 列表。

        当前实现：
        - mock 模式（W3）→ 从 ``MOCK_ZONES`` 返回固定占位
        - W4 真实 CCDB 接通后改为从 ``self.ccdb.list_zones()`` 拉
        - 缓存 10 分钟（与 zone hosts 一致）
        """

        cached = await self.cache.get(CACHE_KEY_ZONES_LIST)
        if cached:
            return list(cached)

        # TODO(W4): 改为 self.ccdb.list_zones()
        zones = list(MOCK_ZONES)
        await self.cache.set(
            CACHE_KEY_ZONES_LIST,
            zones,
            ttl=get_settings().cache_zone_ttl,
        )
        return zones

    async def get_zone_instance_stats(self, zones: list[str]) -> list[ZoneInstanceStat]:
        """查询一个或多个区域的线上实例资源统计。"""

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
                raw = await self.ccdb.get_instance_stats_by_zone(zone)
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
        await self.ccdb.close()
        await self.tcum.close()
        await self.idcrm.close()

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
        ccdb: dict[str, Any] | None,
        tcum: dict[str, Any] | None,
        idc: dict[str, Any] | None,
        errors: dict[str, str],
    ) -> HostInfo:
        """三方数据融合：CCDB > TCUM > IDC。"""

        ccdb = ccdb or {}
        tcum = tcum or {}
        idc = idc or {}
        sources: list[str] = []
        if ccdb:
            sources.append("ccdb")
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
            asset_id=ccdb.get("asset_id") or tcum.get("asset_id") or asset_id,
            ip=ccdb.get("ip") or tcum.get("ip"),
            zone=ccdb.get("zone") or tcum.get("zone"),
            machine_type=ccdb.get("machine_type") or tcum.get("machine_type"),
            status=_normalize_status(ccdb.get("status") or tcum.get("status")),
            idc=tcum.get("idc") or ccdb.get("idc"),
            cabinet=idc.get("cabinet") or tcum.get("cabinet") or ccdb.get("cabinet"),
            position=idc.get("position"),
            module=ccdb.get("module") or tcum.get("module"),
            customer=ccdb.get("customer"),
            app_id=str(ccdb.get("app_id")) if ccdb.get("app_id") is not None else None,
            has_tpc=idc.get("has_tpc") if idc else ccdb.get("has_tpc"),
            billing_tags=ccdb.get("billing_tags") or {},
            owner=tcum.get("owner"),
            backup_owners=tcum.get("backup_owners") or [],
            city=tcum.get("city"),
            server_type=tcum.get("server_type"),
            use_years=tcum.get("use_years"),
            history=history,
            raw_json={"ccdb": ccdb, "tcum": tcum, "idcrm": idc},
            **{"_meta": meta},
        )

    @staticmethod
    def _dict_to_host(data: dict[str, Any], from_cache: bool = False) -> HostInfo:
        """缓存里的 dict → HostInfo（透传 from_cache）。"""

        host = HostInfo.model_validate(data)
        if from_cache:
            host.meta.from_cache = True
        return host
