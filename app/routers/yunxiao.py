"""云霄平台 — 母机管理 / 新机型库存查询 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db_session
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.yunxiao import YunxiaoHostQuery, YunxiaoInventoryQuery, YunxiaoQueryResponse
from app.services.yunxiao_service import YunxiaoService
from app.utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/yunxiao", tags=["yunxiao"])

# 全局单例（复用登录态）
_service = YunxiaoService()


@router.post("/host-machines", response_model=YunxiaoQueryResponse, summary="查询母机管理")
async def query_host_machines(
    payload: YunxiaoHostQuery | None = None,
    zone: str | None = Query(None, description="可用区"),
    machine_type: str | None = Query(None, description="机型"),
    instance_family: str | None = Query(None, description="实例族"),
    is_empty_host: bool = Query(False, description="只看空母机"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    """查询云霄母机管理页面的母机数据（支持筛选）。"""
    try:
        items = await _service.query_host_machines(
            session,
            zone=zone or (payload.zone if payload else None),
            machine_type=machine_type or (payload.machine_type if payload else None),
            instance_family=instance_family or (payload.instance_family if payload else None),
            is_empty_host=is_empty_host or (payload.is_empty_host if payload else False),
        )
        return YunxiaoQueryResponse(
            items=items,
            total=len(items),
            mode=_service.mode,
            snapshot_time=datetime.now(),
        )
    except Exception as exc:
        log.error("yunxiao_host_query_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"云霄查询失败: {exc}")


@router.get("/host-machines/search", response_model=YunxiaoQueryResponse, summary="按固资号/IP精确查母机")
async def search_host_machine(
    keyword: str = Query(..., min_length=2, description="固资号或内网IP"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    """按固资号 / IP 精确查单台母机。"""
    try:
        items = await _service.query_host_by_keyword(session, keyword=keyword)
        return YunxiaoQueryResponse(
            items=items,
            total=len(items),
            mode=_service.mode,
            snapshot_time=datetime.now(),
        )
    except Exception as exc:
        log.error("yunxiao_host_search_failed", keyword=keyword, error=str(exc))
        raise HTTPException(status_code=502, detail=f"云霄查询失败: {exc}")


@router.post("/inventory", response_model=YunxiaoQueryResponse, summary="查询新机型库存")
async def query_inventory(
    payload: YunxiaoInventoryQuery | None = None,
    zone: str | None = Query(None, description="可用区"),
    instance_family: str | None = Query(None, description="实例族"),
    instance_type: str | None = Query(None, description="实例类型"),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    """查询云霄新机型库存页面数据（支持筛选）。"""
    try:
        items = await _service.query_inventory(
            session,
            zone=zone or (payload.zone if payload else None),
            instance_family=instance_family or (payload.instance_family if payload else None),
            instance_type=instance_type or (payload.instance_type if payload else None),
        )
        return YunxiaoQueryResponse(
            items=items,
            total=len(items),
            mode=_service.mode,
            snapshot_time=datetime.now(),
        )
    except Exception as exc:
        log.error("yunxiao_inventory_query_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"云霄查询失败: {exc}")


@router.get("/host-machines/history", summary="查询母机管理历史快照")
async def get_host_history(
    zone: str | None = Query(None, description="可用区"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    _: User = Depends(get_current_user),
):
    """查询已入库的母机快照历史。"""
    items = await _service.get_host_history(session, zone=zone, limit=limit)
    return {"items": items, "total": len(items)}


@router.post("/sync", summary="手动触发云霄全量同步")
async def trigger_sync(
    _: User = Depends(get_current_user),
):
    """手动触发一次云霄母机 + 库存全量同步入库（与每日定时任务同一逻辑）。"""
    from app.scheduler import sync_yunxiao_job
    result = await sync_yunxiao_job()
    return result
