"""定时任务调度器：每日自动刷新资源数据（时间打散，避免集中）。

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

    # 1. 每天 10:13 — 登录态预热（到工位开机后先刷一遍 SSO）
    _scheduler.add_job(
        refresh_login_job,
        trigger=CronTrigger(hour=10, minute=13),
        id="refresh_login_daily",
        name="每日登录态预热",
        replace_existing=True,
    )

    # 2. 每天 13:37 — 全量刷新节点机位 + TCUM 设备状态
    _scheduler.add_job(
        sync_all_zones_job,
        trigger=CronTrigger(hour=13, minute=37),
        id="sync_all_zones_daily",
        name="每日全量刷新节点机位+设备数据",
        replace_existing=True,
    )

    # 3. 每天 16:52 — 云霄母机 + 库存同步
    _scheduler.add_job(
        sync_yunxiao_job,
        trigger=CronTrigger(hour=16, minute=52),
        id="sync_yunxiao_daily",
        name="每日云霄母机+库存同步",
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


async def refresh_login_job() -> None:
    """每日登录态预热：访问各平台首页，让 iOA SSO cookie 续期。

    headless=true 下 SSO 自动点击可完成，无需人工。
    腾讯文档走企微登录，这里不刷（过期时由 TencentDocSkill 弹窗处理）。
    """
    log.info("scheduler.refresh_login_start")
    try:
        from app.clients.browser_session import BrowserSession, is_login_url
        from app.clients.base_browser import BaseBrowserImpl

        sso_helper = BaseBrowserImpl()
        targets = [
            ("CMDB", "https://cmdb.woa.com"),
            ("TCUM", "https://tcum.woa.com"),
            ("IDCRM", "https://idcrm.woa.com"),
        ]

        for name, url in targets:
            try:
                async with BrowserSession.page() as page:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(2)
                    # 自动点 SSO 按钮
                    if is_login_url(page.url):
                        await sso_helper._try_finish_sso_flow(page)
                        await asyncio.sleep(3)
                    ok = not is_login_url(page.url)
                    log.info("scheduler.refresh_login_done", target=name, ok=ok)
            except Exception as exc:
                log.warning("scheduler.refresh_login_failed", target=name, error=str(exc))

        log.info("scheduler.refresh_login_complete")
    except Exception as exc:
        log.error("scheduler.refresh_login_error", error=str(exc))


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


async def sync_yunxiao_job() -> dict:
    """定时/手动任务：通过 API 直调查询全部 TEZ 边缘可用区母机+库存。

    使用 data360/zone 获取 53 个边缘区 zoneId→region 映射，
    然后逐区调 honeycomb/host 全量抓取。
    资源池全取（cdc 客户可买 + supp 支撑机），pool_type 字段区分。
    """
    log.info("scheduler.sync_yunxiao_start")

    from app.config import get_settings
    settings = get_settings()
    if settings.yunxiao_mode not in ("api", "browser"):
        log.warning("scheduler.sync_yunxiao_skip", mode=settings.yunxiao_mode)
        return {"skipped": True, "mode": settings.yunxiao_mode}

    from app.data.zone_mapping import ZONE_IDC_MAPPING
    from app.deps import _get_session_factory
    from app.services.yunxiao_service import YunxiaoService

    svc = YunxiaoService()
    total_hosts = 0
    total_inv = 0
    stats: dict[str, int] = {"zones_done": 0, "zones_failed": 0, "zones_skipped": 0}

    try:
        factory = _get_session_factory()

        # 收集目标可用区：ZONE_IDC_MAPPING 中已开区/开区中的 TEZ 节点
        target_zones: list[str] = []
        for z, idc in ZONE_IDC_MAPPING.items():
            from app.data.zone_mapping import ZONE_DETAIL_MAP
            info = ZONE_DETAIL_MAP.get(z)
            if info and info.get("status") in ("已开区", "开区中"):
                target_zones.append(z)

        log.info("scheduler.sync_yunxiao_targets", count=len(target_zones))

        if not target_zones:
            log.warning("scheduler.sync_yunxiao_no_targets")
            return {"skipped": True, "reason": "no_target_zones"}

        # 逐区查询母机（API 客户端自动按 zone_name 查 zoneId→region 映射）
        for zone_name in sorted(target_zones):
            log.info("scheduler.sync_yunxiao_zone", zone=zone_name)

            h_count = 0
            try:
                async with factory() as session:
                    hosts = await svc.query_host_machines(session, zones=[zone_name])
                    h_count = len(hosts)
                    total_hosts += h_count
                    # 统计 pool_type 分布
                    cdc = sum(1 for h in hosts if h.get("pool_type") == "cdc")
                    supp = sum(1 for h in hosts if h.get("pool_type") == "supp")
                    log.info("scheduler.sync_yunxiao_host_done", zone=zone_name,
                             rows=h_count, cdc=cdc, supp=supp)
            except Exception as exc:
                log.warning("scheduler.sync_yunxiao_host_failed", zone=zone_name, error=str(exc))
                stats["zones_failed"] += 1
                continue

            # 库存同步：当前仅 browser 模式支持库存页面抓取，api 模式暂未实现
            try:
                async with factory() as session:
                    inv = await svc.query_inventory(session, region="", zones=[zone_name])
                    i_count = len(inv)
                    total_inv += i_count
                    log.info("scheduler.sync_yunxiao_inv_done", zone=zone_name, rows=i_count)
            except NotImplementedError:
                log.info("scheduler.sync_yunxiao_inv_skip", zone=zone_name,
                         mode=settings.yunxiao_mode, reason="inventory_not_implemented_for_mode")
            except Exception as exc:
                log.warning("scheduler.sync_yunxiao_inv_failed", zone=zone_name, error=str(exc))

            stats["zones_done"] += 1
            await asyncio.sleep(0.5)  # 区间短暂间隔，避免请求过密

        log.info("scheduler.sync_yunxiao_complete", total_hosts=total_hosts, total_inv=total_inv,
                 stats=stats)
        return {"skipped": False, "hosts": total_hosts, "inventory": total_inv, **stats}
    except Exception as exc:
        log.error("scheduler.sync_yunxiao_error", error=str(exc))
        return {"skipped": False, "error": str(exc)}
    finally:
        await svc.close()
