"""节点资源同步 Service：本地数据库优先 + 过期自动刷新。

策略：
- 读取：永远读本地数据库（快、稳定）
- 刷新：7天内有效期，过期后触发后台同步（IDCRM + TCUM）
- 支持手动强制刷新
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zone_snapshot import ZoneDevice, ZoneSnapshot
from app.utils.logger import get_logger

log = get_logger(__name__)

# 默认过期时间：7天
SYNC_EXPIRE_DAYS = 7


class ZoneResourceService:
    """节点资源服务：本地优先 + 定期同步。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_zone_overview(self, zone: str, force_refresh: bool = False) -> dict[str, Any]:
        """获取可用区资源概况。

        Args:
            zone: 可用区名称
            force_refresh: 是否强制刷新（忽略缓存有效期）

        Returns:
            概况数据 dict
        """
        # 1. 读本地数据库
        snapshot = await self._get_snapshot(zone)

        if snapshot and not force_refresh:
            # 检查是否过期
            if snapshot.last_sync_at and (datetime.now() - snapshot.last_sync_at) < timedelta(days=SYNC_EXPIRE_DAYS):
                # 未过期，直接返回本地数据
                devices = await self._get_devices(zone)
                return self._build_response(snapshot, devices, from_cache=True)

        # 2. 过期或无数据 → 从云端同步
        log.info("zone_resource.sync_needed", zone=zone, force=force_refresh)
        result = await self._sync_from_cloud(zone)

        if result:
            return result

        # 3. 同步失败但有旧数据，仍然返回旧数据
        if snapshot:
            devices = await self._get_devices(zone)
            resp = self._build_response(snapshot, devices, from_cache=True)
            resp["sync_warning"] = "同步失败，显示的是上次缓存数据"
            return resp

        return {"zone": zone, "message": "暂无数据，且同步失败"}

    async def force_sync(self, zone: str) -> dict[str, Any]:
        """手动强制同步。"""
        return await self.get_zone_overview(zone, force_refresh=True)

    async def list_all_snapshots(self) -> list[dict[str, Any]]:
        """列出所有已同步的可用区快照摘要。"""
        stmt = select(ZoneSnapshot).order_by(ZoneSnapshot.zone)
        result = await self._session.execute(stmt)
        snapshots = result.scalars().all()
        return [
            {
                "zone": s.zone,
                "idc": s.idc,
                "total_positions": s.total_positions,
                "free_count": s.free_count,
                "online_count": s.online_count,
                "offline_count": s.offline_count,
                "last_sync_at": s.last_sync_at.isoformat() if s.last_sync_at else None,
            }
            for s in snapshots
        ]

    # ─── 内部方法 ───

    async def _get_snapshot(self, zone: str) -> ZoneSnapshot | None:
        stmt = select(ZoneSnapshot).where(ZoneSnapshot.zone == zone)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_devices(self, zone: str) -> list[ZoneDevice]:
        stmt = select(ZoneDevice).where(ZoneDevice.zone == zone)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _sync_from_cloud(self, zone: str) -> dict[str, Any] | None:
        """从 IDCRM + TCUM 拉取最新数据并写入本地库。"""
        from app.config import get_settings
        from app.data.zone_mapping import ZONE_IDC_MAPPING

        idc = ZONE_IDC_MAPPING.get(zone)
        if not idc:
            return {"zone": zone, "message": "未知可用区"}

        settings = get_settings()
        if settings.idcrm_mode != "browser":
            return {"zone": zone, "message": "需要 browser 模式才能同步"}

        try:
            # Step 1: IDCRM 查全量机位（支持 HTTP 和 Browser 两种模式）
            if settings.idcrm_mode == "http":
                from app.clients.idcrm_http import IDCRMHttpClient
                client = IDCRMHttpClient()
                pos_result = await client.query_positions_by_idc(idc)
                if not pos_result.get("success"):
                    pos_result = {"free_count": None, "message": pos_result.get("message", "HTTP查询失败")}
            else:
                from app.skills.idcrm_position_skill import IDCRMPositionSkill
                skill = IDCRMPositionSkill()
                pos_result = await skill.query_free_positions(idc)

            if pos_result.get("idc_not_found"):
                # 存一条标记为未开区的快照
                await self._save_snapshot(zone, idc, pos_result, [], [], [], 0)
                return {
                    "zone": zone,
                    "idc": idc,
                    "idc_not_found": True,
                    "message": pos_result.get("message", "该可用区尚未开区"),
                }

            all_assets = pos_result.get("all_assets", [])

            # Step 2: TCUM 批量查
            online_devices: list[dict] = []
            offline_devices: list[dict] = []
            non_tez_devices: list[dict] = []

            if all_assets and settings.tcum_mode in ("browser", "http"):
                if settings.tcum_mode == "http":
                    from app.clients.tcum_http import TCUMHttpClient
                    tcum = TCUMHttpClient()
                else:
                    from app.clients.tcum_browser import TCUMBrowserImpl
                    tcum = TCUMBrowserImpl()
                devices = await tcum.batch_search(all_assets[:100])

                # TEZ 设备识别规则：
                # 1. 模块含 "腾讯云边缘可用区" 或 "TEZ" → 一定是 TEZ
                # 2. 模块含 "边缘计算" + 过渡关键词(搬迁/buffer/待上线) → TEZ（过渡中）
                # 3. 模块含 "边缘计算" 但无过渡词 → 非 TEZ（ECM 设备）
                TEZ_CORE_KEYWORDS = ["腾讯云边缘可用区", "TEZ"]
                TRANSITIONAL_KEYWORDS = ["待上线", "上线中", "搬迁", "待搬迁", "buffer", "未上线"]

                for dev in devices:
                    module = dev.get("module", "") or ""
                    status = dev.get("status", "") or ""
                    module_lower = module.lower()

                    # 判断是否 TEZ
                    is_core_tez = any(kw in module for kw in TEZ_CORE_KEYWORDS)
                    has_edge_compute = "边缘计算" in module
                    is_transitional = any(kw in module for kw in TRANSITIONAL_KEYWORDS) or "buffer" in module_lower

                    if is_core_tez:
                        # 明确的 TEZ 设备
                        is_tez = True
                    elif has_edge_compute and is_transitional:
                        # 边缘计算 + 过渡状态 = TEZ 搬迁中
                        is_tez = True
                    else:
                        is_tez = False

                    if not is_tez:
                        non_tez_devices.append(dev)
                        continue

                    # TEZ 设备：按模块状态分类
                    if is_transitional:
                        reason = "未知"
                        if "待上线" in module or "未上线" in module:
                            reason = "模块状态：待上线"
                        elif "上线中" in module:
                            reason = "模块状态：上线中"
                        elif "搬迁" in module:
                            reason = "模块状态：搬迁中"
                        elif "待搬迁" in module:
                            reason = "模块状态：待搬迁"
                        elif "buffer" in module_lower:
                            reason = "模块状态：buffer（待分配）"
                        dev["reason"] = reason
                        offline_devices.append(dev)
                    elif status == "online":
                        online_devices.append(dev)
                    else:
                        reason = "未知"
                        if status == "maintenance":
                            reason = "设备状态：维护中"
                        elif status == "offline":
                            reason = "设备状态：离线/故障"
                        else:
                            reason = f"设备状态：{status or '未知'}"
                        dev["reason"] = reason
                        offline_devices.append(dev)

            # Step 3: 写入本地数据库
            await self._save_snapshot(
                zone, idc, pos_result,
                online_devices, offline_devices, non_tez_devices,
                len(all_assets),
            )

            # 返回结果
            snapshot = await self._get_snapshot(zone)
            all_devs = await self._get_devices(zone)
            return self._build_response(snapshot, all_devs, from_cache=False)

        except Exception as exc:
            log.error("zone_resource.sync_error", zone=zone, error=str(exc))
            return None

    async def _save_snapshot(
        self,
        zone: str,
        idc: str,
        pos_result: dict,
        online_devices: list[dict],
        offline_devices: list[dict],
        non_tez_devices: list[dict],
        total_assets: int,
    ) -> None:
        """保存快照和设备到本地库（upsert 逻辑）。"""
        now = datetime.now()

        # Upsert ZoneSnapshot
        existing = await self._get_snapshot(zone)
        if existing:
            existing.idc = idc
            existing.total_positions = pos_result.get("total_positions", 0)
            existing.free_count = pos_result.get("free_count", 0)
            existing.used_count = pos_result.get("used_count", 0)
            existing.other_count = pos_result.get("other_count", 0)
            existing.total_assets = total_assets
            existing.online_count = len(online_devices)
            existing.offline_count = len(offline_devices)
            existing.non_tez_count = len(non_tez_devices)
            existing.last_sync_at = now
            existing.raw_data = pos_result
        else:
            snapshot = ZoneSnapshot(
                zone=zone,
                idc=idc,
                total_positions=pos_result.get("total_positions", 0),
                free_count=pos_result.get("free_count", 0),
                used_count=pos_result.get("used_count", 0),
                other_count=pos_result.get("other_count", 0),
                total_assets=total_assets,
                online_count=len(online_devices),
                offline_count=len(offline_devices),
                non_tez_count=len(non_tez_devices),
                last_sync_at=now,
                raw_data=pos_result,
            )
            self._session.add(snapshot)

        # 清除旧设备记录，写入新的
        await self._session.execute(delete(ZoneDevice).where(ZoneDevice.zone == zone))

        for dev in online_devices:
            self._session.add(ZoneDevice(
                zone=zone,
                asset_id=dev.get("asset_id", ""),
                ip=dev.get("ip"),
                machine_type=dev.get("machine_type"),
                module=dev.get("module"),
                status="online",
                is_tez=True,
                category="online",
            ))

        for dev in offline_devices:
            self._session.add(ZoneDevice(
                zone=zone,
                asset_id=dev.get("asset_id", ""),
                ip=dev.get("ip"),
                machine_type=dev.get("machine_type"),
                module=dev.get("module"),
                status=dev.get("status"),
                is_tez=True,
                category="offline",
                reason=dev.get("reason"),
            ))

        for dev in non_tez_devices:
            self._session.add(ZoneDevice(
                zone=zone,
                asset_id=dev.get("asset_id", ""),
                ip=dev.get("ip"),
                machine_type=dev.get("machine_type"),
                module=dev.get("module"),
                status=dev.get("status"),
                is_tez=False,
                category="non_tez",
            ))

        await self._session.commit()
        log.info(
            "zone_resource.saved",
            zone=zone,
            online=len(online_devices),
            offline=len(offline_devices),
            non_tez=len(non_tez_devices),
        )

    def _build_response(
        self,
        snapshot: ZoneSnapshot | None,
        devices: list[ZoneDevice],
        from_cache: bool,
    ) -> dict[str, Any]:
        """从本地数据构建 API 响应。"""
        if not snapshot:
            return {"zone": "", "message": "暂无数据"}

        online = [d for d in devices if d.category == "online"]
        offline = [d for d in devices if d.category == "offline"]
        non_tez = [d for d in devices if d.category == "non_tez"]

        return {
            "zone": snapshot.zone,
            "idc": snapshot.idc,
            "total_positions": snapshot.total_positions,
            "free_count": snapshot.free_count,
            "used_count": snapshot.used_count,
            "total_assets": snapshot.total_assets,
            "online_devices": [
                {"asset_id": d.asset_id, "ip": d.ip, "machine_type": d.machine_type, "module": d.module}
                for d in online
            ],
            "online_count": len(online),
            "offline_devices": [
                {"asset_id": d.asset_id, "ip": d.ip, "machine_type": d.machine_type, "module": d.module, "reason": d.reason}
                for d in offline
            ],
            "offline_count": len(offline),
            "non_tez_devices": [
                {"asset_id": d.asset_id, "ip": d.ip, "machine_type": d.machine_type, "module": d.module}
                for d in non_tez
            ],
            "non_tez_count": len(non_tez),
            "last_sync_at": snapshot.last_sync_at.isoformat() if snapshot.last_sync_at else None,
            "from_cache": from_cache,
            "message": (
                f"虚拟化机位: {snapshot.total_positions}"
                f"（空闲{snapshot.free_count}/已用{snapshot.used_count}），"
                f"TEZ已上线{len(online)}台, 未上线{len(offline)}台"
                + (f", 非TEZ设备{snapshot.non_tez_count}台" if snapshot.non_tez_count else "")
            ),
        }
