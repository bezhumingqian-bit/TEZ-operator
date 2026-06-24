"""云霄平台 — 业务逻辑层（查询 + 入库）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.yunxiao import YunxiaoClient
from app.models.yunxiao import YunxiaoHostSnapshot, YunxiaoInventorySnapshot
from app.utils.logger import get_logger

log = get_logger(__name__)


class YunxiaoService:
    """云霄平台数据服务。

    职责：
    1. 委托 YunxiaoClient 抓取页面数据
    2. 将查询结果入库（快照）
    3. 返回结构化数据给前端
    """

    def __init__(self) -> None:
        self._client = YunxiaoClient()

    @property
    def mode(self) -> str:
        return self._client.mode

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
        """查询母机管理并入库快照。"""
        raw = await self._client.query_host_machines(
            zone, machine_type, instance_family, is_empty_host,
            zones=zones, region=region,
        )
        await self._persist_host_snapshots(session, raw)
        return raw

    async def query_host_by_keyword(
        self, session: AsyncSession, keyword: str,
    ) -> list[dict]:
        """按固资号 / IP 精确查单台母机并入库快照。"""
        raw = await self._client.query_host_by_keyword(keyword)
        await self._persist_host_snapshots(session, raw)
        return raw

    # 母机模型已知字段集合（用于过滤 API 客户端返回的额外派生字段如 pool_type）
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

    async def _persist_host_snapshots(
        self, session: AsyncSession, raw: list[dict],
    ) -> None:
        """将母机查询结果入库为快照（host 查询与精确查共用）。

        自动过滤 API 客户端返回的派生字段（如 pool_type），
        只保留数据库模型已定义的列。
        """
        snapshot_time = datetime.now()

        saved_count = 0
        for item in raw:
            kwargs = {
                "snapshot_time": snapshot_time,
                "asset_id": item.get("asset_id", ""),
                "ip": item.get("ip"),
                "instance_family": item.get("instance_family"),
                "device_type": item.get("device_type"),
                "zone": item.get("zone"),
                "logical_zone": item.get("logical_zone"),
                "pool": item.get("pool"),
                "sale_pool": item.get("sale_pool"),
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
                "tags": item.get("tags"),
                "machine_model": item.get("machine_model"),
                "health_score": item.get("health_score"),
                "online_status": item.get("online_status"),
                "kernel_version": item.get("kernel_version"),
                "kernel_version_id": item.get("kernel_version_id"),
                "manufacturer_module": item.get("manufacturer_module"),
                "sale_pool_type": item.get("sale_pool_type"),
                "box_type": item.get("box_type"),
                "host_updated_at": item.get("host_updated_at"),
            }
            # 安全过滤：只保留模型已知字段
            kwargs = {k: v for k, v in kwargs.items() if k in self._HOST_MODEL_FIELDS}
            snapshot = YunxiaoHostSnapshot(**kwargs)
            session.add(snapshot)
            saved_count += 1

        await session.commit()
        log.info("yunxiao_host_saved", count=saved_count, snapshot_time=str(snapshot_time))

    async def query_inventory(
        self,
        session: AsyncSession,
        zone: str | None = None,
        instance_family: str | None = None,
        instance_type: str | None = None,
        zones: list[str] | None = None,
        region: str | None = None,
    ) -> list[dict]:
        """查询新机型库存并入库快照。"""
        raw = await self._client.query_inventory(zone, instance_family, instance_type, zones=zones, region=region)
        snapshot_time = datetime.now()

        saved_count = 0
        for item in raw:
            snapshot = YunxiaoInventorySnapshot(**{
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
                "cpu": item.get("cpu"),
                "gpu": item.get("gpu"),
                "storage_block": item.get("storage_block"),
                "mem": item.get("mem"),
                "device_type": item.get("device_type"),
            })
            session.add(snapshot)
            saved_count += 1

        await session.commit()
        log.info("yunxiao_inventory_saved", count=saved_count, snapshot_time=str(snapshot_time))
        return raw

    async def get_host_history(
        self, session: AsyncSession, zone: str | None = None, limit: int = 100,
    ) -> list[dict]:
        """查询历史母机快照。"""
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
