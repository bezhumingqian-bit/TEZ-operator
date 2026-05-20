"""主机相关 Pydantic Schemas。

字段命名遵循 11 文档 § 3.3 / § 4.2，存储统一用 snake_case。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ─────────────────────────── 基础元素 ───────────────────────────


class HostHistoryEvent(BaseModel):
    """单条历史轨迹事件。"""

    model_config = ConfigDict(from_attributes=True)

    event_type: str = Field(..., description="投放/搬迁/迁入/迁出/维修等")
    event_at: datetime
    from_module: str | None = None
    to_module: str | None = None
    description: str | None = None
    source: str | None = Field(default=None, description="ccdb/tcum/manual")


class HostMeta(BaseModel):
    """响应元信息：是否走缓存、用了哪些数据源等。"""

    from_cache: bool = False
    data_sources: list[str] = Field(default_factory=list)
    last_sync_at: datetime | None = None
    partial: bool = Field(default=False, description="是否部分数据源失败的降级响应")
    errors: dict[str, str] = Field(default_factory=dict)


# ─────────────────────────── 主体 ───────────────────────────


class HostInfo(BaseModel):
    """单台机的完整信息（融合三方后的统一视图）。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    asset_id: str = Field(..., description="固资号 TYSVxxxx")
    ip: str | None = None
    zone: str | None = None
    machine_type: str | None = Field(default=None, description="如 CG3-10G")
    status: str | None = Field(default=None, description="online/offline/maintenance")
    idc: str | None = Field(default=None, description="机房代号 / 中文名")
    cabinet: str | None = None
    position: str | None = None
    module: str | None = Field(default=None, description="ten1.customer_a-PRD")
    customer: str | None = None
    app_id: str | None = None
    has_tpc: bool | None = None
    billing_tags: dict[str, str] = Field(default_factory=dict)

    # ─── 来自 TCUM Browser 的扩展字段（W2 新增） ───
    owner: str | None = Field(default=None, description="主负责人 OA")
    backup_owners: list[str] = Field(
        default_factory=list, description="备负责人列表（分号分隔后已 split）"
    )
    city: str | None = None
    server_type: str | None = None
    use_years: float | None = Field(default=None, description="使用年限（如 5.9）")

    history: list[HostHistoryEvent] = Field(default_factory=list)

    raw_json: dict[str, Any] | None = Field(default=None, exclude=True)

    meta: HostMeta = Field(default_factory=HostMeta, alias="_meta")


# ─────────────────────────── 请求 / 响应 ───────────────────────────


class SearchResponse(BaseModel):
    """单条 search 接口响应。"""

    code: int = 0
    message: str = "ok"
    query_type: Literal["asset_id", "ip", "zone", "unknown"] = "unknown"
    data: HostInfo | list[HostInfo] | None = None


class BatchSearchRequest(BaseModel):
    """批量查询请求。"""

    queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="最多 100 条，可混合固资号/IP",
    )

    @field_validator("queries")
    @classmethod
    def _strip_each(cls, v: list[str]) -> list[str]:
        out = [x.strip() for x in v if x and x.strip()]
        if not out:
            raise ValueError("queries 不能全部为空")
        return out


class BatchSearchItem(BaseModel):
    """批量结果中的单项。"""

    query: str
    query_type: Literal["asset_id", "ip", "zone", "unknown"]
    success: bool
    data: HostInfo | None = None
    error: str | None = None


class BatchSearchResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    total: int
    success_count: int
    items: list[BatchSearchItem]


class ZoneHostsResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    zone: str
    total: int
    items: list[HostInfo]
