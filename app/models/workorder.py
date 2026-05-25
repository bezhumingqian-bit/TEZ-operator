"""工单流数据模型。

4 类工单：ecm_export / host_deploy / migration / repair
状态机：submitted → pending → processing → verifying → completed / rejected
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkOrder(Base):
    """工单主表。"""

    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, comment="工单编号 WO-YYYYMMDD-XXXX")
    order_type: Mapped[str] = mapped_column(
        String(32), comment="ecm_export / host_deploy / migration / repair"
    )
    title: Mapped[str] = mapped_column(String(256), comment="工单标题")
    status: Mapped[str] = mapped_column(
        String(16), default="submitted",
        comment="submitted/pending/processing/verifying/completed/rejected"
    )

    # 提交人
    creator: Mapped[str] = mapped_column(String(64), comment="提交人（OA英文名）")

    # 指派人（接口人路由自动填入）
    assignee: Mapped[Optional[str]] = mapped_column(String(64), comment="当前处理人")

    # 工单详情（JSON，不同类型字段不同）
    detail: Mapped[Optional[dict]] = mapped_column(JSON, comment="工单详情（结构化字段）")

    # 前置校验结果
    pre_checks: Mapped[Optional[dict]] = mapped_column(JSON, comment="前置校验结果")

    # 备注
    note: Mapped[Optional[str]] = mapped_column(Text, comment="备注")

    # 优先级
    priority: Mapped[int] = mapped_column(Integer, default=2, comment="1=紧急 2=普通 3=低")

    # 时间
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="完成时间")

    # 关联
    logs: Mapped[list["WorkOrderLog"]] = relationship(
        back_populates="work_order", cascade="all, delete-orphan", order_by="WorkOrderLog.created_at"
    )


class WorkOrderLog(Base):
    """工单操作日志。"""

    __tablename__ = "work_order_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("work_orders.id"))
    action: Mapped[str] = mapped_column(String(32), comment="create/assign/process/verify/complete/reject/comment")
    operator: Mapped[str] = mapped_column(String(64), comment="操作人")
    content: Mapped[Optional[str]] = mapped_column(Text, comment="操作内容/备注")
    from_status: Mapped[Optional[str]] = mapped_column(String(16))
    to_status: Mapped[Optional[str]] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    work_order: Mapped["WorkOrder"] = relationship(back_populates="logs")
