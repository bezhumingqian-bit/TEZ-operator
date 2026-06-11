"""运维操作日志 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func

from app.deps import get_db_session
from app.models.op_log import OperationLog

router = APIRouter(prefix="/op-logs", tags=["op-logs"])


class OpLogItem(BaseModel):
    id: int
    action: str
    target: str
    status: str
    message: str | None = None
    detail: dict | None = None
    workorder_no: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class OpLogListResponse(BaseModel):
    items: list[OpLogItem]
    total: int
    ok_count: int = 0
    fail_count: int = 0
    warn_count: int = 0


@router.get("", response_model=OpLogListResponse, summary="运维日志列表")
async def list_logs(
    status: str | None = Query(None, description="ok / fail / warn"),
    action: str | None = Query(None, description="push_doc / add_rows / switch_sheet"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    session=Depends(get_db_session),
) -> OpLogListResponse:
    stmt = select(OperationLog).order_by(desc(OperationLog.created_at))
    count_stmt = select(func.count(OperationLog.id))

    if status:
        stmt = stmt.where(OperationLog.status == status)
        count_stmt = count_stmt.where(OperationLog.status == status)
    if action:
        stmt = stmt.where(OperationLog.action == action)
        count_stmt = count_stmt.where(OperationLog.action == action)

    total = (await session.execute(count_stmt)).scalar() or 0
    result = await session.execute(stmt.limit(limit).offset(offset))
    items = list(result.scalars().all())

    # 统计
    stats = {}
    for s in ("ok", "warn", "fail"):
        stats[f"{s}_count"] = (
            await session.execute(
                select(func.count(OperationLog.id)).where(OperationLog.status == s)
            )
        ).scalar() or 0

    return OpLogListResponse(
        items=items,
        total=total,
        ok_count=stats["ok_count"],
        warn_count=stats["warn_count"],
        fail_count=stats["fail_count"],
    )
