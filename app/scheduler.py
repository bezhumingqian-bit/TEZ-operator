"""定时任务调度器：每周自动刷新全量节点资源数据。

使用 APScheduler，在 FastAPI lifespan 启动时激活。
"""

from __future__ import annotations

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.utils.logger import get_logger

log = get_logger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    """启动定时任务调度器。"""
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    # 每周一早上 9:00 自动全量刷新节点资源
    _scheduler.add_job(
        sync_all_zones_job,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="sync_all_zones_weekly",
        name="每周一全量刷新节点机位+设备数据",
        replace_existing=True,
    )

    _scheduler.start()
    log.info("scheduler.started", jobs=len(_scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    """关闭调度器。"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        log.info("scheduler.shutdown")
        _scheduler = None


async def sync_all_zones_job() -> None:
    """定时任务：全量刷新所有可用区机位 + TCUM 设备状态。"""
    log.info("scheduler.sync_all_start")

    try:
        from app.skills.idcrm_position_skill import IDCRMPositionSkill
        from app.deps import _get_session_factory
        from app.services.zone_resource_service import ZoneResourceService
        from app.models.zone_snapshot import ZoneSnapshot
        from app.clients.tcum_browser import TCUMBrowserImpl
        from app.config import get_settings
        from datetime import datetime

        settings = get_settings()

        # Step 1: IDCRM 全量机位查询
        skill = IDCRMPositionSkill()
        result = await skill.query_all_positions()

        if not result.get("success"):
            log.error("scheduler.idcrm_failed", message=result.get("message"))
            return

        log.info("scheduler.idcrm_done", zones=result.get("zones_found"), rows=result.get("total_rows"))

        # Step 2: 逐区域更新 + TCUM 查设备
        factory = _get_session_factory()
        async with factory() as session:
            svc = ZoneResourceService(session)

            for idc, data in result.get("results", {}).items():
                zone = data.get("zone", "")
                if not zone:
                    continue

                all_assets = data.get("all_assets", [])

                # TCUM 查设备详情（如果有固资号且开启了 browser 模式）
                online_devices = []
                offline_devices = []
                non_tez_devices = []

                if all_assets and settings.tcum_mode == "browser":
                    try:
                        tcum = TCUMBrowserImpl()
                        devices = await tcum.batch_search(all_assets[:100])

                        TEZ_CORE_KEYWORDS = ["腾讯云边缘可用区", "TEZ"]
                        TRANSITIONAL_KEYWORDS = ["待上线", "上线中", "搬迁", "待搬迁", "buffer", "未上线"]

                        for dev in devices:
                            module = dev.get("module", "") or ""
                            status = dev.get("status", "") or ""
                            module_lower = module.lower()

                            is_core_tez = any(kw in module for kw in TEZ_CORE_KEYWORDS)
                            has_edge_compute = "边缘计算" in module
                            is_transitional = any(kw in module for kw in TRANSITIONAL_KEYWORDS) or "buffer" in module_lower

                            if is_core_tez:
                                is_tez = True
                            elif has_edge_compute and is_transitional:
                                is_tez = True
                            else:
                                is_tez = False

                            if not is_tez:
                                non_tez_devices.append(dev)
                            elif is_transitional:
                                dev["reason"] = "搬迁/待上线"
                                offline_devices.append(dev)
                            elif status == "online":
                                online_devices.append(dev)
                            else:
                                dev["reason"] = f"状态: {status}"
                                offline_devices.append(dev)

                    except Exception as exc:
                        log.warning("scheduler.tcum_failed", zone=zone, error=str(exc))

                # 保存快照
                pos_result = {
                    "total_positions": data["total_positions"],
                    "free_count": data["free_count"],
                    "used_count": data["used_count"],
                    "other_count": 0,
                }
                await svc._save_snapshot(
                    zone, idc, pos_result,
                    online_devices, offline_devices, non_tez_devices,
                    len(all_assets),
                )
                log.info("scheduler.zone_synced", zone=zone, online=len(online_devices), offline=len(offline_devices))

        log.info("scheduler.sync_all_complete", zones=result.get("zones_found"))

    except Exception as exc:
        log.error("scheduler.sync_all_error", error=str(exc))
