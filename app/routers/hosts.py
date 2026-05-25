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

from app.deps import get_host_service
from app.schemas.host import (
    BatchSearchItem,
    BatchSearchRequest,
    BatchSearchResponse,
    SearchResponse,
    ZoneHostsResponse,
    ZoneInstanceStatsResponse,
)
from app.services.host_service import HostService
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

    # 真实查询：通过 IDCRM 浏览器查空闲虚拟化机位
    try:
        from app.clients.idcrm_browser import IDCRMBrowserImpl
        import asyncio

        impl = IDCRMBrowserImpl()
        # 构造查询 URL：按机房管理单元筛选
        base = settings.idcrm_base_url.rstrip("/")
        from urllib.parse import urlencode
        url = f"{base}/db/positions?{urlencode({'idc': idc})}"

        rows = await impl._fetch_rows(url, target_keyword="虚拟化")

        # 从结果中筛选空闲机位
        free_count = 0
        total_count = len(rows)
        for row in rows:
            # 根据真实页面列序：COL_STATUS=7
            status_cell = row[7] if len(row) > 7 else ""
            if "空闲" in status_cell or "free" in status_cell.lower():
                free_count += 1

        return {
            "zone": zone,
            "idc": idc,
            "free_count": free_count,
            "total_positions": total_count,
            "status": "ok",
            "message": f"空闲虚拟化机位: {free_count} / 总机位: {total_count}",
        }
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
        # Step 1: 从数全通查该机房的虚拟化机位，提取固资号
        from app.clients.idcrm_browser import IDCRMBrowserImpl
        from urllib.parse import urlencode

        idcrm_impl = IDCRMBrowserImpl()
        base = settings.idcrm_base_url.rstrip("/")
        url = f"{base}/db/positions?{urlencode({'idc': idc})}"
        rows = await idcrm_impl._fetch_rows(url, target_keyword="虚拟化")

        # 从机位行里提取固资号（通常在某一列，先尝试全行文本匹配 TYSV）
        import re
        asset_ids_from_positions: list[str] = []
        for row in rows:
            row_text = " ".join(row)
            found = re.findall(r"TYSV[0-9A-Z]{6,}", row_text, re.IGNORECASE)
            asset_ids_from_positions.extend(found)

        asset_ids_from_positions = list(set(asset_ids_from_positions))[:50]  # 去重，限50

        if not asset_ids_from_positions:
            return {
                "zone": zone,
                "idc": idc,
                "devices": [],
                "message": f"在数全通机位中未发现固资号（{idc}），可能页面结构有变",
            }

        # Step 2: 拿固资号去 TCUM 查模块状态
        from app.clients.tcum_browser import TCUMBrowserImpl

        tcum_impl = TCUMBrowserImpl()
        devices = []

        for aid in asset_ids_from_positions[:20]:  # 限20台避免太慢
            try:
                info = await tcum_impl.get_by_asset(aid)
                if not info:
                    devices.append({
                        "asset_id": aid, "ip": "", "machine_type": "",
                        "module_status": "未找到", "reason": "TCUM 未查到该固资号",
                    })
                    continue

                module = info.get("module", "") or ""
                status = info.get("status") or ""

                # 判断是否未上线
                if "现网运营" in module and status == "online":
                    continue  # 已上线，跳过

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
                elif status == "maintenance":
                    reason = "设备状态：维护中"
                elif status == "offline":
                    reason = "设备状态：离线/故障"

                devices.append({
                    "asset_id": aid,
                    "ip": info.get("ip", ""),
                    "machine_type": info.get("machine_type", ""),
                    "module_status": module.split("]")[-1].strip("[]") if "]" in module else module[:20],
                    "reason": reason,
                })
            except Exception:
                devices.append({
                    "asset_id": aid, "ip": "", "machine_type": "",
                    "module_status": "查询失败", "reason": "TCUM 查询异常",
                })

        return {
            "zone": zone,
            "idc": idc,
            "devices": devices,
            "total_positions_assets": len(asset_ids_from_positions),
            "message": f"从机位中提取 {len(asset_ids_from_positions)} 个固资号，{len(devices)} 台未上线",
        }
    except Exception as exc:
        return {
            "zone": zone,
            "idc": idc,
            "devices": [],
            "message": f"查询失败: {str(exc)[:100]}",
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
