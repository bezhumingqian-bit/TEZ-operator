"""主机相关 ORM 模型：host_cache / host_history / audit_logs。

对应 11 文档 § 3.3。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HostCache(Base, TimestampMixin):
    """主缓存表：固资号为主键。"""

    __tablename__ = "host_cache"

    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    machine_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    idc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cabinet: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    module: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_tpc: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_host_cache_ip", "ip"),
        Index("ix_host_cache_zone", "zone"),
        Index("ix_host_cache_module", "module"),
    )


class HostHistory(Base):
    """历史轨迹表：投放/搬迁/迁入/迁出/维修等事件流。"""

    __tablename__ = "host_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    from_module: Mapped[str | None] = mapped_column(String(128), nullable=True)
    to_module: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="ccdb/tcum/manual"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (Index("ix_host_history_asset_id", "asset_id"),)


class AuditLog(Base):
    """操作日志表：每次查询/导出都记录。"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, comment="search/export/...")
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_audit_logs_user_id", "user_id"),)
