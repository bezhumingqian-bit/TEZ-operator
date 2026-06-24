"""云霄平台 — 业务逻辑层（查询 + 入库 + 本地缓存优先）。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.yunxiao import YunxiaoClient
from app.models.yunxiao import YunxiaoHostSnapshot, YunxiaoInventorySnapshot
from app.utils.logger import get_logger

log = get_logger(__name__)

_CACHE_EXPIRE_DAYS = 7


def _host_snapshot_to_dict(h: YunxiaoHostSnapshot) -> dict:
    return {
        "asset_id": h.asset_id, "ip": h.ip, "instance_family": h.instance_family,
        "device_type": h.device_type, "zone": h.zone, "logical_zone": h.logical_zone,
        "pool": h.pool, "sale_pool": h.sale_pool, "module_label": h.module_label,
        "cpu_available": h.cpu_available, "cpu_total": h.cpu_total,
        "mem_available": h.mem_available, "mem_total": h.mem_total,
        "gpu_available": h.gpu_available, "gpu_total": h.gpu_total,
        "disk_available": h.disk_available, "disk_total": h.disk_total,
        "local_disk_available": h.local_disk_available, "local_disk_total": h.local_disk_total,
        "is_empty_host": h.is_empty_host, "is_cdh": h.is_cdh,
        "exclusive_owner": h.exclusive_owner, "tags": h.tags,
        "machine_model": h.machine_model, "health_score": h.health_score,
        "online_status": h.online_status, "kernel_version": h.kernel_version,
        "kernel_version_id": h.kernel_version_id, "manufacturer_module": h.manufacturer_module,
        "sale_pool_type": h.sale_pool_type, "box_type": h.box_type,
        "host_updated_at": h.host_updated_at.isoformat() if h.host_updated_at else None,
    }


def _inv_snapshot_to_dict(i: YunxiaoInventorySnapshot) -> dict:
    return {
        "zone": i.zone, "instance_family": i.instance_family,
        "instance_type": i.instance_type, "status": i.status,
        "pool": i.pool, "billing_type": i.billing_type,
        "inventory": i.inventory, "inventory_threshold": i.inventory_threshold,
        "safety_quota": i.safety_quota, "cpu": i.cpu, "gpu": i.gpu,
        "storage_block": i.storage_block, "mem": i.mem, "device_type": i.device_type,
    }


class YunxiaoService:
    """云霄平台数据服务。

    职责：
    1. 委托 YunxiaoClient 抓取页面数据
    2. 将查询结果入库（快照）
    3. 返回结构化数据给前端
    4. 本地快照优先：7 天内数据直接读库，不调云霄 API
    """

    def __init__(self) -> None:
        self._client = YunxiaoClient()

    @property
    def mode(self) -> str:
        return self._client.mode

    # ─── 缓存读取 ───

    @staticmethod
    async def _get_cached_hosts(
        session: AsyncSession,
        zone: str | None = None,
        machine_type: str | None = None,
        instance_family: str | None = None,
    ) -> list[dict] | None:
        sub = select(func.max(YunxiaoHostSnapshot.snapshot_time))
        if zone:
            sub = sub.where(YunxiaoHostSnapshot.zone == zone)
        r = await session.execute(sub)
        latest = r.scalar()
        if not latest:
            return None
        if (datetime.now() - latest) > timedelta(days=_CACHE_EXPIRE_DAYS):
            log.info("yunxiao_host_cache_expired", zone=zone, latest=latest.isoformat())
            return None

        q = select(YunxiaoHostSnapshot).where(YunxiaoHostSnapshot.snapshot_time == latest)
        if zone:
            q = q.where(YunxiaoHostSnapshot.zone == zone)
        if machine_type:
            q = q.where(YunxiaoHostSnapshot.machine_model == machine_type)
        if instance_family:
            q = q.where(YunxiaoHostSnapshot.instance_family == instance_family)
        result = await session.execute(q)
        items = list(result.scalars().all())
        if not items:
            return None
        log.info("yunxiao_host_cache_hit", zone=zone, count=len(items))
        return [_host_snapshot_to_dict(h) for h in items]

    @staticmethod
    async def _get_cached_inventory(
        session: AsyncSession,
        zone: str | None = None,
        instance_family: str | None = None,
        instance_type: str | None = None,
    ) -> list[dict] | None:
        sub = select(func.max(YunxiaoInventorySnapshot.snapshot_time))
        if zone:
            sub = sub.where(YunxiaoInventorySnapshot.zone == zone)
        r = await session.execute(sub)
        latest = r.scalar()
        if not latest:
            return None
        if (datetime.now() - latest) > timedelta(days=_CACHE_EXPIRE_DAYS):
            log.info("yunxiao_inv_cache_expired", zone=zone, latest=latest.isoformat())
            return None

        q = select(YunxiaoInventorySnapshot).where(
            YunxiaoInventorySnapshot.snapshot_time == latest
        )
        if zone:
            q = q.where(YunxiaoInventorySnapshot.zone == zone)
        if instance_family:
            q = q.where(YunxiaoInventorySnapshot.instance_family == instance_family)
        if instance_type:
            q = q.where(YunxiaoInventorySnapshot.instance_type == instance_type)
        result = await session.execute(q)
        items = list(result.scalars().all())
        if not items:
            return None
        log.info("yunxiao_inv_cache_hit", zone=zone, count=len(items))
        return [_inv_snapshot_to_dict(i) for i in items]

    # ─── 公开查询 ───

    async def query_host_machines(
        self,
        session: AsyncSession,
        zone: str | None = None,
        machine_type: str | None = None,
        instance_family: str | None = None,
        is_empty_host: bool = False,
        zones: list[str] | None = None,
        region: str | None = None,
    ) -> list[dict]:
        """查询母机管理，优先读本地缓存。

        定时同步任务传 zones/region → 跳过缓存，走云端全量抓取。
        前端查询传 zone → 优先读 7 天内本地快照。
        """
        if not zones and not region and not is_empty_host:
            cached = await self._get_cached_hosts(
                session, zone=zone, machine_type=machine_type,
                instance_family=instance_family,
            )
            if cached is not None:
                return cached

        raw = await self._client.query_host_machines(
            zone, machine_type, instance_family, is_empty_host,
            zones=zones, region=region,
        )
        await self._persist_host_snapshots(session, raw)
        return raw

    async def query_host_by_keyword(
        self, session: AsyncSession, keyword: str,
    ) -> list[dict]:
        """按固资号 / IP 精确查母机（不走缓存，始终云端查）。"""
        raw = await self._client.query_host_by_keyword(keyword)
        await self._persist_host_snapshots(session, raw)
        return raw

    async def query_inventory(
        self,
        session: AsyncSession,
        zone: str | None = None,
        instance_family: str | None = None,
        instance_type: str | None = None,
        zones: list[str] | None = None,
        region: str | None = None,
    ) -> list[dict]:
        """查询新机型库存，优先读本地缓存。"""
        if not zones and not region:
            cached = await self._get_cached_inventory(
                session, zone=zone, instance_family=instance_family,
                instance_type=instance_type,
            )
            if cached is not None:
                return cached

        raw = await self._client.query_inventory(
            zone, instance_family, instance_type, zones=zones, region=region,
        )
        await self._persist_inventory_snapshots(session, raw)
        return raw

    # 母机模型已知字段集合
    _HOST_MODEL_FIELDS = frozenset({
        "snapshot_time", "asset_id", "ip", "instance_family", "device_type",
        "zone", "logical_zone", "pool", "sale_pool", "module_label",
        "cpu_available", "cpu_total", "mem_available", "mem_total",
        "gpu_available", "gpu_total", "disk_available", "disk_total",
        "local_disk_available", "local_disk_total",
        "is_empty_host", "is_cdh", "exclusive_owner", "tags", "machine_model",
        "health_score", "online_status", "kernel_version", "kernel_version_id",
        "manufacturer_module", "sale_pool_type", "box_type", "host_updated_at",
    })

    # ─── 持久化 ───

    async def _persist_host_snapshots(
        self, session: AsyncSession, raw: list[dict],
    ) -> None:
        snapshot_time = datetime.now()
        saved_count = 0
        for item in raw:
            kwargs = {
                "snapshot_time": snapshot_time,
                "asset_id": item.get("asset_id", ""),
                "ip": item.get("ip"), "instance_family": item.get("instance_family"),
                "device_type": item.get("device_type"),
                "zone": item.get("zone"), "logical_zone": item.get("logical_zone"),
                "pool": item.get("pool"), "sale_pool": item.get("sale_pool"),
                "module_label": item.get("module_label"),
                "cpu_available": item.get("cpu_available"),
                "cpu_total": item.get("cpu_total"),
                "mem_available": item.get("mem_available"),
                "mem_total": item.get("mem_total"),
                "gpu_available": item.get("gpu_available"),
                "gpu_total": item.get("gpu_total"),
                "disk_available": item.get("disk_available"),
                "disk_total": item.get("disk_total"),
                "local_disk_available": item.get("local_disk_available"),
                "local_disk_total": item.get("local_disk_total"),
                "is_empty_host": item.get("is_empty_host"),
                "is_cdh": item.get("is_cdh"),
                "exclusive_owner": item.get("exclusive_owner"),
                "tags": item.get("tags"), "machine_model": item.get("machine_model"),
                "health_score": item.get("health_score"),
                "online_status": item.get("online_status"),
                "kernel_version": item.get("kernel_version"),
                "kernel_version_id": item.get("kernel_version_id"),
                "manufacturer_module": item.get("manufacturer_module"),
                "sale_pool_type": item.get("sale_pool_type"),
                "box_type": item.get("box_type"),
                "host_updated_at": item.get("host_updated_at"),
            }
            kwargs = {k: v for k, v in kwargs.items() if k in self._HOST_MODEL_FIELDS}
            session.add(YunxiaoHostSnapshot(**kwargs))
            saved_count += 1
        await session.commit()
        log.info("yunxiao_host_saved", count=saved_count, snapshot_time=str(snapshot_time))

    async def _persist_inventory_snapshots(
        self, session: AsyncSession, raw: list[dict],
    ) -> None:
        snapshot_time = datetime.now()
        saved_count = 0
        for item in raw:
            session.add(YunxiaoInventorySnapshot(**{
                "snapshot_time": snapshot_time,
                "zone": item.get("zone"),
                "instance_family": item.get("instance_family"),
                "instance_type": item.get("instance_type"),
                "status": item.get("status"),
                "pool": item.get("pool"),
                "billing_type": item.get("billing_type"),
                "inventory": item.get("inventory"),
                "inventory_threshold": item.get("inventory_threshold"),
                "safety_quota": item.get("safety_quota"),
                "cpu": item.get("cpu"), "gpu": item.get("gpu"),
                "storage_block": item.get("storage_block"),
                "mem": item.get("mem"), "device_type": item.get("device_type"),
            }))
            saved_count += 1
        await session.commit()
        log.info("yunxiao_inventory_saved", count=saved_count, snapshot_time=str(snapshot_time))

    # ─── 历史 ───

    async def get_host_history(
        self, session: AsyncSession, zone: str | None = None, limit: int = 100,
    ) -> list[dict]:
        q = select(YunxiaoHostSnapshot).order_by(
            YunxiaoHostSnapshot.snapshot_time.desc()
        ).limit(limit)
        if zone:
            q = q.where(YunxiaoHostSnapshot.zone == zone)
        result = await session.execute(q)
        items = result.scalars().all()
        return [{
            "id": h.id, "asset_id": h.asset_id, "ip": h.ip,
            "zone": h.zone, "machine_model": h.machine_model,
            "online_status": h.online_status, "cpu_total": h.cpu_total,
            "mem_total": h.mem_total, "snapshot_time": h.snapshot_time,
        } for h in items]

    async def close(self) -> None:
        await self._client.close()
