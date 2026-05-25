"""节点资源快照 ORM 模型：存储每个可用区的机位/设备概况。

设计思路：
- zone_snapshots: 每个可用区一条记录，存机位概况汇总 + 上次同步时间
- zone_devices: 每台设备一条记录，关联到所属可用区快照
- 界面只读本地库；同步逻辑（IDCRM+TCUM）定期或手动触发更新
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ZoneSnapshot(Base, TimestampMixin):
    """可用区资源快照：每个 zone 一条，记录机位概况 + 同步时间。"""

    __tablename__ = "zone_snapshots"

    zone: Mapped[str] = mapped_column(String(64), primary_key=True)
    idc: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # 机位概况
    total_positions: Mapped[int] = mapped_column(Integer, default=0)
    free_count: Mapped[int] = mapped_column(Integer, default=0)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    other_count: Mapped[int] = mapped_column(Integer, default=0)

    # 设备统计
    total_assets: Mapped[int] = mapped_column(Integer, default=0)
    online_count: Mapped[int] = mapped_column(Integer, default=0)
    offline_count: Mapped[int] = mapped_column(Integer, default=0)
    non_tez_count: Mapped[int] = mapped_column(Integer, default=0)

    # 同步时间
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 原始结果 JSON（完整数据备份）
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class ZoneDevice(Base, TimestampMixin):
    """可用区设备清单：每台设备一条记录。"""

    __tablename__ = "zone_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    machine_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    module: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_tez: Mapped[bool] = mapped_column(default=False)
    category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
