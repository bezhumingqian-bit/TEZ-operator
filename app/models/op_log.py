"""运维操作日志模型。

记录每次腾讯文档写入等关键操作的详细信息。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OperationLog(Base):
    """运维操作日志。"""

    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64), comment="push_doc / add_rows / switch_sheet")
    target: Mapped[str] = mapped_column(String(128), comment="操作目标：sheet_name:row")
    status: Mapped[str] = mapped_column(String(16), default="ok", comment="ok / warn / fail")
    message: Mapped[Optional[str]] = mapped_column(Text, comment="结果消息")
    detail: Mapped[Optional[dict]] = mapped_column(JSON, comment="详细信息（mismatches等）")
    workorder_no: Mapped[Optional[str]] = mapped_column(String(32), comment="关联工单号")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
