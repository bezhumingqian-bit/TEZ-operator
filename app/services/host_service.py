"""HostService：核心融合逻辑。

数据流（11 文档 § 3.1）：
    1. 缓存优先
    2. 并发拉 TCUM + CCDB
    3. 用 TCUM 拿到的 idc/cabinet 再去 IDCRM 补机位
    4. _merge() 融合（CCDB > TCUM > IDC）
    5. 写回缓存
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.clients.ccdb import CCDBClient
from app.clients.idcrm import IDCRMClient
from app.clients.tcum import TCUMClient
from app.schemas.host import HostHistoryEvent, HostInfo, HostMeta
from app.services.cache_service import CacheService, cache as default_cache
from app.utils.logger import get_logger

log = get_logger(__name__)

CACHE_KEY_HOST = "host:{asset_id}"
CACHE_KEY_HOST_BY_IP = "host:ip:{ip}"
CACHE_KEY_ZONE = "zone:{zone}:hosts"
ZONE_CACHE_TTL = 600  # 10 分钟


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
        ccdb_data, tcum_data = await asyncio.gather(
            ccdb_task, tcum_task, return_exceptions=True
        )

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
        await self.cache.set(key, merged.model_dump(by_alias=True, mode="json"))
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
        ccdb_data, tcum_data = await asyncio.gather(
            ccdb_task, tcum_task, return_exceptions=True
        )
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
        await self.cache.set(key, merged.model_dump(by_alias=True, mode="json"))
        # 反向键也写一份，下次按 asset_id 查能命中
        if merged.asset_id:
            await self.cache.set(
                CACHE_KEY_HOST.format(asset_id=merged.asset_id),
                merged.model_dump(by_alias=True, mode="json"),
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
            [h.model_dump(by_alias=True, mode="json") for h in hosts],
            ttl=ZONE_CACHE_TTL,
        )
        return hosts

    async def batch_get_hosts(
        self, asset_ids: list[str]
    ) -> list[tuple[str, HostInfo | None, str | None]]:
        """并发批量查询；返回 (query, host_or_none, error_or_none) 列表。"""

        async def _one(qid: str) -> tuple[str, HostInfo | None, str | None]:
            try:
                host = await self.get_host(qid)
                return qid, host, None
            except Exception as exc:  # noqa: BLE001
                return qid, None, str(exc)

        return await asyncio.gather(*(_one(q) for q in asset_ids))

    # ─────────────────── 内部 ───────────────────

    @staticmethod
    def _unwrap(
        client: str,
        result: Any,
        errors: dict[str, str],
    ) -> dict[str, Any] | None:
        """统一处理 asyncio.gather 里的异常 / None。"""

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
            last_sync_at=datetime.now(),
            partial=bool(errors),
            errors=errors,
        )

        return HostInfo(
            asset_id=ccdb.get("asset_id") or tcum.get("asset_id") or asset_id,
            ip=ccdb.get("ip") or tcum.get("ip"),
            zone=ccdb.get("zone"),
            machine_type=ccdb.get("machine_type") or tcum.get("machine_type"),
            status=ccdb.get("status"),
            idc=tcum.get("idc") or ccdb.get("idc"),
            cabinet=idc.get("cabinet") or tcum.get("cabinet") or ccdb.get("cabinet"),
            position=idc.get("position"),
            module=ccdb.get("module"),
            customer=ccdb.get("customer"),
            app_id=str(ccdb.get("app_id")) if ccdb.get("app_id") is not None else None,
            has_tpc=idc.get("has_tpc") if idc else ccdb.get("has_tpc"),
            billing_tags=ccdb.get("billing_tags") or {},
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
