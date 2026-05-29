"""主机查询路由。

GET  /api/v1/hosts/search?q=...
GET  /api/v1/hosts/{asset_id}
POST /api/v1/hosts/batch_search
GET  /api/v1/hosts/export?asset_ids=A,B,C&format=xlsx
GET  /api/v1/zones                 ← W3 新增（前端远程加载）
GET  /api/v1/zones/{zone}/hosts
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db_session, get_host_service
from app.schemas.host import (
    BatchSearchItem,
    BatchSearchRequest,
    BatchSearchResponse,
    SearchResponse,
    ZoneHostsResponse,
    ZoneInstanceStatsResponse,
)
from app.services.host_service import HostService
from app.utils.logger import get_logger
from app.utils.parser import detect_query_type, normalize_query

router = APIRouter(prefix="/hosts", tags=["hosts"])


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="按固资号 / IP / Zone 查询主机",
)
async def search(
    q: str = Query(..., description="固资号 / IP / Zone", min_length=1),
    service: HostService = Depends(get_host_service),
) -> SearchResponse:
    qtype = detect_query_type(q)
    norm = normalize_query(q)

    if qtype == "asset_id":
        host = await service.get_host(norm)
        if host is None:
            raise HTTPException(status_code=404, detail=f"未找到固资号 {norm}")
        return SearchResponse(query_type=qtype, data=host)

    if qtype == "ip":
        host = await service.get_host_by_ip(norm)
        if host is None:
            raise HTTPException(status_code=404, detail=f"未找到 IP {norm}")
        return SearchResponse(query_type=qtype, data=host)

    if qtype == "zone":
        items = await service.list_zone_hosts(norm)
        return SearchResponse(query_type=qtype, data=items)

    raise HTTPException(
        status_code=400,
        detail=f"无法识别的查询：{q}（仅支持固资号 TYSV*** / IPv4 / Zone ap-xx-yy-N）",
    )


@router.post(
    "/batch_search",
    response_model=BatchSearchResponse,
    summary="批量查询（并发限流；最多 100 条）",
)
async def batch_search(
    payload: BatchSearchRequest,
    service: HostService = Depends(get_host_service),
) -> BatchSearchResponse:
    """W3 改造：用 ``HostService.batch_get_hosts_mixed`` 并发限流。"""

    # 先识别每个 query 的类型
    typed: list[tuple[str, str, str]] = []  # (raw, qtype, normalized)
    for raw in payload.queries:
        qtype = detect_query_type(raw)
        norm = normalize_query(raw)
        typed.append((raw, qtype, norm))

    # 把可查的（asset_id / ip）丢进 service 并发；unknown 直接标错
    results: dict[int, tuple[str, str, object]] = {}
    queryable: list[tuple[int, str, str]] = []
    for idx, (raw, qtype, norm) in enumerate(typed):
        if qtype in ("asset_id", "ip"):
            queryable.append((idx, norm, qtype))
        else:
            results[idx] = (raw, qtype, f"不支持的批量类型：{qtype}（仅支持固资号 / IP）")

    if queryable:
        batched = await service.batch_get_hosts_mixed(
            [(norm, qtype) for _, norm, qtype in queryable]
        )
        for (idx, _, _), (_, _, host, err) in zip(queryable, batched):  # noqa: B905
            results[idx] = (typed[idx][0], typed[idx][1], host or err or "未找到")

    items: list[BatchSearchItem] = []
    success = 0
    for _idx, (raw, qtype, payload_or_err) in sorted(results.items()):
        host = payload_or_err if hasattr(payload_or_err, "asset_id") else None
        err = payload_or_err if isinstance(payload_or_err, str) else None
        if host is not None:
            success += 1
        items.append(
            BatchSearchItem(
                query=raw,
                query_type=qtype,  # type: ignore[arg-type]
                success=host is not None,
                data=host,  # type: ignore[arg-type]
                error=err if host is None else None,
            )
        )

    return BatchSearchResponse(
        total=len(items),
        success_count=success,
        items=items,
    )


# ── Excel 导出（W3 Day 4，前端 axios 已封装）────────────────────


@router.get(
    "/export",
    summary="导出 xlsx（前端调用：?asset_ids=A,B,C）",
    response_class=None,  # 显式声明返回 StreamingResponse
)
async def export_xlsx(
    asset_ids: str = Query(
        ...,
        description="逗号分隔的固资号列表，如 TYSV00000001,TYSV00000002",
        min_length=1,
    ),
    service: HostService = Depends(get_host_service),
):
    """导出指定固资号的全字段 xlsx。

    设计：
    - 前端约定参数名 ``asset_ids``（逗号分隔）
    - 返回 ``application/vnd.openxmlformats-officedocument.spreadsheetml.sheet``
    - 表头中文化，列序与 HostInfo 主体字段一致
    """

    from app.config import get_settings
    from app.services.export_service import build_hosts_xlsx

    s = get_settings()
    # 解析 + 校验
    ids = [x.strip() for x in asset_ids.split(",") if x.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="asset_ids 不能为空")
    if len(ids) > s.batch_max_size:
        raise HTTPException(
            status_code=400,
            detail=f"asset_ids 超过上限 {s.batch_max_size}（当前 {len(ids)}）",
        )
    for a in ids:
        if detect_query_type(a) != "asset_id":
            raise HTTPException(status_code=400, detail=f"非法固资号：{a}")

    # 并发拉
    triples = await service.batch_get_hosts([a.upper() for a in ids])
    hosts = [h for _, h, _ in triples if h is not None]

    return build_hosts_xlsx(hosts)


# ── 单个固资号详情（注意：path 必须放在 /export, /batch_search 等具体路径之后）──


@router.get(
    "/{asset_id}",
    response_model=SearchResponse,
    summary="按固资号查询单机详情（含历史）",
)
async def detail(
    asset_id: str,
    service: HostService = Depends(get_host_service),
) -> SearchResponse:
    qtype = detect_query_type(asset_id)
    if qtype != "asset_id":
        raise HTTPException(status_code=400, detail=f"非法固资号 {asset_id}")
    host = await service.get_host(normalize_query(asset_id))
    if host is None:
        raise HTTPException(status_code=404, detail=f"未找到 {asset_id}")
    return SearchResponse(query_type="asset_id", data=host)


# ── zone 路由（同模块内合并，便于 W1 单一入口）────────────────────


zone_router = APIRouter(prefix="/zones", tags=["zones"])


@zone_router.get(
    "",
    summary="列出所有可用 zone（前端远程加载用）",
)
async def list_zones(
    service: HostService = Depends(get_host_service),
) -> dict[str, Any]:
    """返回 zone 列表 + zone→机房映射。"""
    from app.data.zone_mapping import ZONE_IDC_MAPPING

    zones = sorted(ZONE_IDC_MAPPING.keys())
    return {"zones": zones, "mapping": ZONE_IDC_MAPPING}


@zone_router.get(
    "/info",
    summary="查询可用区详细信息（支持多选）",
)
async def get_zone_info(
    zones: str = Query("", description="逗号分隔的可用区名，为空时返回全部"),
) -> dict[str, Any]:
    """返回可用区的详细信息（region、机房、架构、状态、机型等）。

    支持多选，方便用户批量查看信息后去星云操作。
    """
    from app.data.zone_mapping import ZONE_DETAIL_MAP, ZONE_INFO

    if not zones.strip():
        # 返回全部
        return {"total": len(ZONE_INFO), "items": ZONE_INFO}

    selected = [z.strip() for z in zones.split(",") if z.strip()]
    items = [ZONE_DETAIL_MAP[z] for z in selected if z in ZONE_DETAIL_MAP]
    not_found = [z for z in selected if z not in ZONE_DETAIL_MAP]

    return {
        "total": len(items),
        "items": items,
        "not_found": not_found if not_found else None,
    }


@zone_router.get(
    "/{zone}/free_positions",
    summary="查询目标机房空闲虚拟化机位数",
)
async def get_free_positions(
    zone: str,
) -> dict[str, Any]:
    """查目标机房是否有空闲虚拟化机位。

    数据来源：数全通（IDCRM）机位列表
    筛选条件：机位逻辑区域=虚拟化bonding + 机位状态=空闲
    """
    from app.data.zone_mapping import ZONE_IDC_MAPPING
    from app.config import get_settings

    idc = ZONE_IDC_MAPPING.get(zone)
    if not idc:
        return {"zone": zone, "idc": None, "free_count": None, "message": "未知可用区"}

    settings = get_settings()
    if settings.idcrm_mode != "browser":
        return {
            "zone": zone,
            "idc": idc,
            "free_count": None,
            "status": "mock",
            "message": f"IDCRM 当前为 mock 模式，请切 browser 模式后查询真实数据（{idc}）",
        }

    # 真实查询：通过 IDCRM Skill 查空闲虚拟化机位
    try:
        from app.skills.idcrm_position_skill import IDCRMPositionSkill

        skill = IDCRMPositionSkill()
        result = await skill.query_free_positions(idc)
        result["zone"] = zone
        result["idc"] = idc
        return result
    except Exception as exc:
        return {
            "zone": zone,
            "idc": idc,
            "free_count": None,
            "status": "error",
            "message": f"查询失败: {str(exc)[:100]}",
        }


@zone_router.get(
    "/{zone}/offline_devices",
    summary="查询节点未上线设备清单",
)
async def get_offline_devices(
    zone: str,
) -> dict[str, Any]:
    """查询某节点下未上线的设备。

    SOP：
    1. 数全通查虚拟化机位 → 取出机位上的固资号
    2. 拿固资号去 TCUM 查模块状态
    3. 模块不含"现网运营"的就是未上线设备
    4. 根据模块路径判断未上线原因
    """
    from app.data.zone_mapping import ZONE_IDC_MAPPING
    from app.config import get_settings

    idc = ZONE_IDC_MAPPING.get(zone)
    if not idc:
        return {"zone": zone, "devices": [], "message": "未知可用区"}

    settings = get_settings()
    if settings.idcrm_mode != "browser" or settings.tcum_mode != "browser":
        return {
            "zone": zone,
            "idc": idc,
            "devices": [],
            "message": "需要 IDCRM+TCUM 均为 browser 模式才能查询未上线设备",
        }

    try:
        # Step 1: 用 IDCRM Skill 查全量虚拟化机位 + 获取所有设备固资号
        from app.skills.idcrm_position_skill import IDCRMPositionSkill

        skill = IDCRMPositionSkill()
        pos_result = await skill.query_free_positions(idc)

        # 新版返回 all_assets（全量固资号）
        asset_ids_from_positions = pos_result.get("all_assets", []) or pos_result.get("occupied_assets", [])

        if not asset_ids_from_positions:
            return {
                "zone": zone,
                "idc": idc,
                "free_count": pos_result.get("free_count", 0),
                "total_positions": pos_result.get("total_positions", 0),
                "devices": [],
                "message": f"机位上未发现设备（{idc} 虚拟化机位: {pos_result.get('total_positions', 0)}, 空闲: {pos_result.get('free_count', 0)}）",
            }

        # Step 2: 批量查 TCUM（用;拼接一次查完）
        from app.clients.tcum_browser import TCUMBrowserImpl

        tcum_impl = TCUMBrowserImpl()
        all_devices = await tcum_impl.batch_search(asset_ids_from_positions[:100])

        # Step 3: 按模块过滤 TEZ 设备 + 分类
        # TEZ 模块特征：[N][腾讯云边缘可用区]
        # ECM 模块特征：[腾讯云][边缘计算]
        TEZ_MODULE_KEYWORDS = ["腾讯云边缘可用区", "TEZ"]

        online_devices = []  # 已上线（运营中）
        offline_devices = []  # 未上线
        non_tez_devices = []  # 非 TEZ 设备

        for dev in all_devices:
            module = dev.get("module", "") or ""
            status_raw = dev.get("status", "") or ""

            # 判断是否 TEZ 模块
            is_tez = any(kw in module for kw in TEZ_MODULE_KEYWORDS)
            if not is_tez:
                non_tez_devices.append({
                    "asset_id": dev.get("asset_id", ""),
                    "ip": dev.get("ip", ""),
                    "machine_type": dev.get("machine_type", ""),
                    "module": module[:50],
                    "status": status_raw,
                })
                continue

            # TEZ 设备：按运营状态分类
            if status_raw == "online":
                online_devices.append({
                    "asset_id": dev.get("asset_id", ""),
                    "ip": dev.get("ip", ""),
                    "machine_type": dev.get("machine_type", ""),
                    "module": module[:50],
                })
            else:
                # 判断未上线原因
                reason = "未知"
                if "待上线" in module:
                    reason = "模块状态：待上线"
                elif "上线中" in module:
                    reason = "模块状态：上线中（等待投放）"
                elif "搬迁中" in module:
                    reason = "模块状态：搬迁中"
                elif "待搬迁" in module:
                    reason = "模块状态：待搬迁"
                elif "compute_未上线" in module:
                    reason = "ECM 计算母机未上线"
                elif status_raw == "maintenance":
                    reason = "设备状态：维护中"
                elif status_raw == "offline":
                    reason = "设备状态：离线/故障"

                offline_devices.append({
                    "asset_id": dev.get("asset_id", ""),
                    "ip": dev.get("ip", ""),
                    "machine_type": dev.get("machine_type", ""),
                    "module": module[:50],
                    "reason": reason,
                })

        return {
            "zone": zone,
            "idc": idc,
            "total_positions": pos_result.get("total_positions", 0),
            "free_count": pos_result.get("free_count", 0),
            "used_count": pos_result.get("used_count", 0),
            "total_assets": len(asset_ids_from_positions),
            "online_devices": online_devices,
            "online_count": len(online_devices),
            "offline_devices": offline_devices,
            "offline_count": len(offline_devices),
            "non_tez_count": len(non_tez_devices),
            "message": (
                f"虚拟化机位: {pos_result.get('total_positions', 0)}"
                f"（空闲{pos_result.get('free_count', 0)}/已用{pos_result.get('used_count', 0)}），"
                f"TEZ设备: 已上线{len(online_devices)}台, 未上线{len(offline_devices)}台, "
                f"非TEZ设备{len(non_tez_devices)}台"
            ),
        }
    except Exception as exc:
        return {
            "zone": zone,
            "idc": idc,
            "devices": [],
            "message": f"查询失败: {str(exc)[:100]}",
        }


@zone_router.get(
    "/snapshots",
    summary="列出所有已同步的节点快照摘要（驾驶舱用）",
)
async def list_zone_snapshots(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """返回所有已同步过的可用区概况（用于驾驶舱看板）。"""
    from app.services.zone_resource_service import ZoneResourceService

    svc = ZoneResourceService(session)
    items = await svc.list_all_snapshots()
    return {"items": items}


@zone_router.post(
    "/sync-all",
    summary="一次性刷新所有可用区（IDCRM机位 + TCUM设备详情）",
)
async def sync_all_zones(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """全量同步：IDCRM 拉机位 → TCUM 批量查设备 → 按区域写入本地缓存。

    耗时约 2-5 分钟（取决于设备数量），前端可用 AbortController 取消。
    HTTP 模式下 IDCRM 查询仅需数秒。
    """
    from app.services.zone_resource_service import ZoneResourceService
    from app.clients.tcum_browser import TCUMBrowserImpl
    from app.models.zone_snapshot import ZoneSnapshot
    from app.config import get_settings
    from datetime import datetime
    import re

    settings = get_settings()
    log = get_logger(__name__)

    # Step 1: IDCRM 全量机位（优先用 HTTP）
    if settings.idcrm_mode == "http":
        from app.clients.idcrm_http import IDCRMHttpClient
        client = IDCRMHttpClient()
        result = await client.query_all_positions()
    else:
        from app.skills.idcrm_position_skill import IDCRMPositionSkill
        skill = IDCRMPositionSkill()
        result = await skill.query_all_positions()

    if not result.get("success"):
        return {"success": False, "message": result.get("message", "IDCRM查询失败")}

    log.info("sync_all.idcrm_done", zones=result.get("zones_found"), rows=result.get("total_rows"))

    # Step 2: 收集所有固资号 → TCUM 批量查
    all_assets_flat = []
    zone_assets_map: dict[str, list[str]] = {}  # zone → [asset_ids]

    for idc, data in result.get("results", {}).items():
        zone = data.get("zone", "")
        if not zone:
            continue
        assets = data.get("all_assets", [])
        zone_assets_map[zone] = assets
        all_assets_flat.extend(assets)

    all_assets_flat = list(set(all_assets_flat))
    tcum_device_map: dict[str, dict] = {}  # asset_id → device info

    if all_assets_flat and settings.tcum_mode == "browser":
        try:
            tcum = TCUMBrowserImpl()
            # 分批查询（每批 50 个，TCUM 限制）
            batch_size = 50
            for i in range(0, len(all_assets_flat), batch_size):
                batch = all_assets_flat[i:i + batch_size]
                devices = await tcum.batch_search(batch)
                for dev in devices:
                    aid = dev.get("asset_id", "")
                    if aid:
                        tcum_device_map[aid] = dev
                log.info("sync_all.tcum_batch", batch_num=i // batch_size + 1, found=len(devices))
        except Exception as exc:
            log.warning("sync_all.tcum_failed", error=str(exc))

    log.info("sync_all.tcum_done", total_devices=len(tcum_device_map))

    # Step 3: 按区域分类设备 + 写入
    svc = ZoneResourceService(session)
    updated_zones = []

    TEZ_CORE_KEYWORDS = ["腾讯云边缘可用区", "TEZ"]
    TRANSITIONAL_KEYWORDS = ["待上线", "上线中", "搬迁", "待搬迁", "buffer", "未上线"]

    for idc, data in result.get("results", {}).items():
        zone = data.get("zone", "")
        if not zone:
            continue

        assets = data.get("all_assets", [])
        online_devices = []
        offline_devices = []
        non_tez_devices = []

        for asset_id in assets:
            dev = tcum_device_map.get(asset_id)
            if not dev:
                continue

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
                reason = "搬迁/待上线"
                if "待上线" in module or "未上线" in module:
                    reason = "模块状态：待上线"
                elif "搬迁" in module:
                    reason = "模块状态：搬迁中"
                elif "buffer" in module_lower:
                    reason = "模块状态：buffer"
                dev["reason"] = reason
                offline_devices.append(dev)
            elif status == "online":
                online_devices.append(dev)
            else:
                dev["reason"] = f"设备状态：{status or '未知'}"
                offline_devices.append(dev)

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
            len(assets),
        )
        updated_zones.append(zone)

    return {
        "success": True,
        "total_positions": result.get("total_rows", 0),
        "total_devices": len(tcum_device_map),
        "zones_updated": len(updated_zones),
        "zones": updated_zones,
        "message": f"已刷新 {len(updated_zones)} 个可用区（{result.get('total_rows', 0)} 机位，{len(tcum_device_map)} 台设备）",
    }


@zone_router.get(
    "/{zone}/overview",
    summary="节点资源概况（本地数据库优先，7天过期自动刷新）",
)
async def get_zone_overview(
    zone: str,
    force_refresh: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """获取可用区资源概况（本地数据库模式）。

    - 默认读本地数据库（毫秒级响应）
    - 数据超过7天自动触发后台同步
    - force_refresh=true 手动强制刷新
    """
    from app.services.zone_resource_service import ZoneResourceService

    svc = ZoneResourceService(session)
    return await svc.get_zone_overview(zone, force_refresh=force_refresh)


@router.get("/browser/status", summary="浏览器登录态检查")
async def get_browser_status() -> dict:
    """检查 Playwright 浏览器的登录态是否有效。

    前端可用此接口判断是否需要等待用户扫码登录。
    """
    from app.clients.browser_session import BrowserSession

    return {
        "login_valid": BrowserSession.is_login_valid(),
        "profile_exists": BrowserSession.profile_exists(),
    }


@router.post(
    "/lookup",
    summary="批量查固资号基本信息（轻量，用于表单回填）",
)
async def lookup_assets(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """输入固资号列表，返回每个固资号的设备型号和可用区。

    数据来源：本地全量母机缓存（从 OnePage 导入）。
    """
    from app.data.asset_cache import ASSET_CACHE

    asset_ids = payload.get("asset_ids", [])
    if isinstance(asset_ids, str):
        asset_ids = [a.strip() for a in asset_ids.replace("\n", ",").split(",") if a.strip()]

    results = {}
    for aid in asset_ids[:100]:
        aid_upper = aid.strip().upper()
        if aid_upper in ASSET_CACHE:
            results[aid_upper] = ASSET_CACHE[aid_upper]
        else:
            results[aid_upper] = None

    found = sum(1 for v in results.values() if v)
    return {"results": results, "found": found, "total": len(results)}


@zone_router.get(
    "/instances/stats",
    response_model=ZoneInstanceStatsResponse,
    summary="按区域统计线上实例资源",
)
async def zone_instance_stats(
    zones: str = Query(..., description="逗号分隔的 Zone 列表，如 zone_a,zone_b", min_length=1),
    service: HostService = Depends(get_host_service),
) -> ZoneInstanceStatsResponse:
    parsed = [z.strip() for z in zones.split(",") if z.strip()]
    if not parsed:
        raise HTTPException(status_code=400, detail="zones 不能为空")
    invalid = [z for z in parsed if detect_query_type(z) != "zone"]
    if invalid:
        raise HTTPException(status_code=400, detail=f"非法 zone：{','.join(invalid)}")

    stats = await service.get_zone_instance_stats([normalize_query(z) for z in parsed])
    return ZoneInstanceStatsResponse(
        total_zones=len(stats),
        total_hosts=sum(s.host_count for s in stats),
        total_instances=sum(s.total_instances for s in stats),
        online_instances=sum(s.online_instances for s in stats),
        items=stats,
    )


@zone_router.get(
    "/{zone}/hosts",
    response_model=ZoneHostsResponse,
    summary="按 Zone 列出母机",
)
async def zone_hosts(
    zone: str,
    service: HostService = Depends(get_host_service),
) -> ZoneHostsResponse:
    if detect_query_type(zone) != "zone":
        raise HTTPException(status_code=400, detail=f"非法 zone：{zone}")
    items = await service.list_zone_hosts(normalize_query(zone))
    return ZoneHostsResponse(zone=zone, total=len(items), items=items)


# 注：zone_router 由 app.main 直接 include 到 /api/v1，
# 这里不再嵌套，否则路径会变成 /hosts/zones/...
