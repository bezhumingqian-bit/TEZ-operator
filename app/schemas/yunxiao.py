"""云霄平台 — 请求/响应 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── 请求 ──

class YunxiaoHostQuery(BaseModel):
    """母机管理查询请求。"""
    zone: Optional[str] = Field(None, description="可用区，如'广州三区'")
    machine_type: Optional[str] = Field(None, description="机型筛选")
    instance_family: Optional[str] = Field(None, description="实例族，如'S1'")


class YunxiaoInventoryQuery(BaseModel):
    """新机型库存查询请求。"""
    zone: Optional[str] = Field(None, description="可用区")
    instance_family: Optional[str] = Field(None, description="实例族")
    instance_type: Optional[str] = Field(None, description="实例类型")


# ── 响应 ──

class HostMachineItem(BaseModel):
    """母机管理 - 单条记录。"""
    asset_id: str
    ip: Optional[str] = None
    instance_family: Optional[str] = None
    device_type: Optional[str] = None
    zone: Optional[str] = None
    logical_zone: Optional[str] = None
    pool: Optional[str] = None
    sale_pool: Optional[str] = None
    module_label: Optional[str] = None
    cpu_available: Optional[float] = None
    cpu_total: Optional[float] = None
    mem_available: Optional[float] = None
    mem_total: Optional[float] = None
    gpu_available: Optional[float] = None
    gpu_total: Optional[float] = None
    disk_available: Optional[float] = None
    disk_total: Optional[float] = None
    local_disk_available: Optional[float] = None
    local_disk_total: Optional[float] = None
    is_empty_host: Optional[str] = None
    is_cdh: Optional[str] = None
    exclusive_owner: Optional[str] = None
    tags: Optional[str] = None
    machine_model: Optional[str] = None
    health_score: Optional[int] = None
    online_status: Optional[str] = None
    kernel_version: Optional[str] = None
    kernel_version_id: Optional[str] = None
    manufacturer_module: Optional[str] = None
    sale_pool_type: Optional[str] = None
    box_type: Optional[str] = None
    host_updated_at: Optional[datetime] = None


class InventoryItem(BaseModel):
    """新机型库存 - 单条记录。"""
    zone: Optional[str] = None
    instance_family: Optional[str] = None
    instance_type: Optional[str] = None
    status: Optional[str] = None
    pool: Optional[str] = None
    billing_type: Optional[str] = None
    inventory: Optional[int] = None
    inventory_threshold: Optional[int] = None
    safety_quota: Optional[int] = None
    cpu: Optional[int] = None
    gpu: Optional[int] = None
    storage_block: Optional[int] = None
    mem: Optional[int] = None
    device_type: Optional[str] = None


class YunxiaoQueryResponse(BaseModel):
    """通用查询响应。"""
    items: list[HostMachineItem | InventoryItem]
    total: int
    mode: str
    snapshot_time: Optional[datetime] = None
