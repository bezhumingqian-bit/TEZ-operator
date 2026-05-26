"""工单流 API。

POST /api/v1/workorders                  创建工单
GET  /api/v1/workorders                  工单列表
GET  /api/v1/workorders/stats            工单统计
GET  /api/v1/workorders/{id}             工单详情
POST /api/v1/workorders/{id}/transition  状态流转
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import get_db_session
from app.services.workorder_service import WorkOrderService

router = APIRouter(prefix="/workorders", tags=["workorders"])


async def _get_service(session=Depends(get_db_session)):
    return WorkOrderService(session)


# ─── Schemas ───

class OrderCreate(BaseModel):
    order_type: str = Field(..., description="ecm_export/host_deploy/migration/repair")
    title: str = Field(..., description="工单标题")
    creator: str = Field(..., description="提交人OA英文名")
    detail: dict | None = Field(None, description="工单详情字段")
    note: str | None = None
    priority: int = Field(2, description="1=紧急 2=普通 3=低")


class TransitionRequest(BaseModel):
    to_status: str = Field(..., description="目标状态")
    operator: str = Field(..., description="操作人")
    comment: str | None = None


class OrderLogInfo(BaseModel):
    id: int
    action: str
    operator: str
    content: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrderInfo(BaseModel):
    id: int
    order_no: str
    order_type: str
    title: str
    status: str
    creator: str
    assignee: str | None = None
    detail: dict | None = None
    pre_checks: dict | None = None
    note: str | None = None
    priority: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    logs: list[OrderLogInfo] = []

    model_config = {"from_attributes": True}


class OrderBrief(BaseModel):
    """列表用简版（不含 logs）。"""
    id: int
    order_no: str
    order_type: str
    title: str
    status: str
    creator: str
    assignee: str | None = None
    priority: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list[OrderBrief]
    total: int


class StatsResponse(BaseModel):
    submitted: int = 0
    pending: int = 0
    processing: int = 0
    verifying: int = 0
    completed: int = 0
    rejected: int = 0
    total: int = 0


# ─── Endpoints ───

@router.post("", response_model=OrderInfo, status_code=201, summary="创建工单")
async def create_order(
    payload: OrderCreate,
    service: WorkOrderService = Depends(_get_service),
) -> OrderInfo:
    order = await service.create_order(
        order_type=payload.order_type,
        title=payload.title,
        creator=payload.creator,
        detail=payload.detail,
        note=payload.note,
        priority=payload.priority,
    )
    await service.session.commit()
    # 重新查询带 logs
    order = await service.get_order(order.id)
    return order


@router.get("", response_model=OrderListResponse, summary="工单列表")
async def list_orders(
    status: str | None = Query(None),
    order_type: str | None = Query(None),
    creator: str | None = Query(None),
    assignee: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    service: WorkOrderService = Depends(_get_service),
) -> OrderListResponse:
    orders, total = await service.list_orders(
        status=status, order_type=order_type,
        creator=creator, assignee=assignee,
        limit=limit, offset=offset,
    )
    return OrderListResponse(items=orders, total=total)


@router.get("/stats", response_model=StatsResponse, summary="工单统计")
async def get_stats(
    service: WorkOrderService = Depends(_get_service),
) -> StatsResponse:
    stats = await service.get_stats()
    return StatsResponse(**stats)


@router.get("/{order_id}", response_model=OrderInfo, summary="工单详情")
async def get_order(
    order_id: int,
    service: WorkOrderService = Depends(_get_service),
) -> OrderInfo:
    order = await service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    return order


@router.post("/{order_id}/transition", response_model=OrderInfo, summary="状态流转")
async def transition_order(
    order_id: int,
    payload: TransitionRequest,
    service: WorkOrderService = Depends(_get_service),
) -> OrderInfo:
    try:
        order = await service.transition(
            order_id=order_id,
            to_status=payload.to_status,
            operator=payload.operator,
            comment=payload.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await service.session.commit()
    order = await service.get_order(order_id)
    return order


@router.patch("/{order_id}/detail", response_model=OrderInfo, summary="更新工单详情")
async def update_order_detail(
    order_id: int,
    payload: dict,
    service: WorkOrderService = Depends(_get_service),
) -> OrderInfo:
    order = await service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    order.detail = payload.get("detail", order.detail)
    await service.session.flush()
    await service.session.commit()
    order = await service.get_order(order_id)
    return order


@router.delete("/{order_id}", status_code=204, summary="删除工单")
async def delete_order(
    order_id: int,
    service: WorkOrderService = Depends(_get_service),
) -> None:
    order = await service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    await service.session.delete(order)
    await service.session.commit()
