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

    idc = ZONE_IDC_MAPPING.get(zone)
    if not idc:
        return {"zone": zone, "idc": None, "free_count": None, "message": "未知可用区"}

    return {
        "zone": zone,
        "idc": idc,
        "free_count": None,
        "status": "pending",
        "message": f"机位查询待接入数全通（{idc}），请手动到 IDCRM 确认",
    }


@zone_router.get(
    "/{zone}/offline_devices",
    summary="查询节点未上线设备清单",
)
async def get_offline_devices(
    zone: str,
) -> dict[str, Any]:
    """查询某节点下未上线的设备。

    数据来源：CMDB 模块路径包含 [待上线]/[上线中]/[搬迁中] 的设备。
    """
    from app.data.zone_mapping import ZONE_IDC_MAPPING

    idc = ZONE_IDC_MAPPING.get(zone)
    if not idc:
        return {"zone": zone, "devices": [], "message": "未知可用区"}

    # TODO: 接入真实 CMDB 查询未上线设备
    # 当前返回框架占位
    return {
        "zone": zone,
        "idc": idc,
        "devices": [],
        "message": f"未上线设备查询待接入 CMDB（模块含[待上线]/[上线中]/[搬迁中]），当前无数据",
    }


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
