"""云霄平台 — 母机库存 & 机型库存快照模型。

数据来源：https://yunxiao.vstation.woa.com/synergy/honeycomb-host
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class YunxiaoHostSnapshot(Base):
    """母机管理快照表 — 每次查询保存一份快照，用于趋势分析。

    数据来自 云霄/宿主机管理/母机管理 页面。
    """

    __tablename__ = "yunxiao_host_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True,
                                                     comment="快照时间")

    # ── 母机核心字段 ──
    asset_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True,
                                           comment="固资号")
    ip: Mapped[str] = mapped_column(String(50), nullable=True, comment="内网IP")
    instance_family: Mapped[str] = mapped_column(String(100), nullable=True, comment="实例族")
    device_type: Mapped[str] = mapped_column(String(50), nullable=True, comment="设备类型")
    zone: Mapped[str] = mapped_column(String(100), nullable=True, index=True, comment="可用区")
    logical_zone: Mapped[str] = mapped_column(String(50), nullable=True, comment="逻辑区")
    pool: Mapped[str] = mapped_column(String(50), nullable=True, comment="资源池")
    sale_pool: Mapped[str] = mapped_column(String(50), nullable=True, comment="售卖池")
    module_label: Mapped[str] = mapped_column(String(200), nullable=True, comment="Module")

    # ── CPU / GPU / 内存 / 磁盘 ──
    cpu_available: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="可用CPU(核)")
    cpu_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="总CPU(核)")
    mem_available: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="可用内存(G)")
    mem_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="总内存(G)")
    gpu_available: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="可用GPU(卡)")
    gpu_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="总GPU(卡)")
    disk_available: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="可用磁盘(GB)")
    disk_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="总磁盘(GB)")
    local_disk_available: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="可用本地盘(GB)")
    local_disk_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="总本地盘(GB)")

    # ── 状态 / 标记 ──
    is_empty_host: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, comment="空母机")
    is_cdh: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, comment="CDH母机")
    exclusive_owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="独享母机owner")
    tags: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="标签")
    machine_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="机型")
    health_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="健康度")
    online_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True, comment="在线状态")
    kernel_version: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="内核版本")
    kernel_version_id: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, comment="内核版本识别")
    manufacturer_module: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="制作商模块")
    sale_pool_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="售卖池类型")
    box_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="装箱类型")

    # ── 更新时间（母机页面的更新时间）──
    host_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="母机更新时间")


class YunxiaoInventorySnapshot(Base):
    """新机型库存快照表。

    数据来自 云霄/资源规划/新机型库存查询 页面。
    """

    __tablename__ = "yunxiao_inventory_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True,
                                                     comment="快照时间")

    zone: Mapped[str] = mapped_column(String(100), nullable=True, index=True, comment="可用区")
    instance_family: Mapped[str] = mapped_column(String(100), nullable=True, index=True, comment="实例族")
    instance_type: Mapped[str] = mapped_column(String(100), nullable=True, comment="实例类型")
    status: Mapped[str] = mapped_column(String(50), nullable=True, comment="状态")
    pool: Mapped[str] = mapped_column(String(50), nullable=True, comment="资源池")
    billing_type: Mapped[str] = mapped_column(String(50), nullable=True, comment="计费类型")
    inventory: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="库存")
    inventory_threshold: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="库存售罄阈值")
    safety_quota: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="安全库存配额")
    cpu: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="CPU")
    gpu: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="GPU")
    storage_block: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="storageBlock")
    mem: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="内存")
    device_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="设备类型")
