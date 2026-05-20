"""主机查询路由。

GET  /api/v1/hosts/search?q=...
GET  /api/v1/hosts/{asset_id}
POST /api/v1/hosts/batch_search
GET  /api/v1/zones/{zone}/hosts
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_host_service
from app.schemas.host import (
    BatchSearchItem,
    BatchSearchRequest,
    BatchSearchResponse,
    SearchResponse,
    ZoneHostsResponse,
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


@router.post(
    "/batch_search",
    response_model=BatchSearchResponse,
    summary="批量查询（最多 100 条）",
)
async def batch_search(
    payload: BatchSearchRequest,
    service: HostService = Depends(get_host_service),
) -> BatchSearchResponse:
    items: list[BatchSearchItem] = []
    success = 0

    # 把所有 query 先识别类型
    for raw in payload.queries:
        qtype = detect_query_type(raw)
        norm = normalize_query(raw)
        host = None
        err: str | None = None
        try:
            if qtype == "asset_id":
                host = await service.get_host(norm)
            elif qtype == "ip":
                host = await service.get_host_by_ip(norm)
            else:
                err = f"不支持的批量类型：{qtype}（仅支持固资号 / IP）"
        except Exception as exc:  # noqa: BLE001
            err = str(exc)

        if host is not None:
            success += 1
        elif err is None:
            err = "未找到"

        items.append(
            BatchSearchItem(
                query=raw,
                query_type=qtype,
                success=host is not None,
                data=host,
                error=err if host is None else None,
            )
        )

    return BatchSearchResponse(
        total=len(items),
        success_count=success,
        items=items,
    )


# ── zone 路由（同模块内合并，便于 W1 单一入口）────────────────────


zone_router = APIRouter(prefix="/zones", tags=["zones"])


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
