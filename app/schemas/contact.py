"""接口人路由器 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─────────────── Contact ───────────────

class ContactBase(BaseModel):
    name: str = Field(..., description="英文名（OA账号名）")
    display_name: str | None = Field(None, description="中文名/昵称")
    team: str | None = Field(None, description="所属团队")
    role: str | None = Field(None, description="角色/职责简述")
    status: Literal["active", "vacation", "left"] = "active"
    wecom_id: str | None = None
    phone: str | None = None
    note: str | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    display_name: str | None = None
    team: str | None = None
    role: str | None = None
    status: Literal["active", "vacation", "left"] | None = None
    wecom_id: str | None = None
    phone: str | None = None
    note: str | None = None


class ContactInfo(ContactBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─────────────── Category ───────────────

class CategoryBase(BaseModel):
    name: str = Field(..., description="分类名称")
    parent_id: int | None = None
    description: str | None = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryInfo(CategoryBase):
    id: int

    model_config = {"from_attributes": True}


# ─────────────── Responsibility ───────────────

class ResponsibilityInfo(BaseModel):
    id: int
    contact: ContactInfo
    category_id: int
    priority: int = Field(..., description="1=主负责人, 2=备份, 3=上升")
    note: str | None = None

    model_config = {"from_attributes": True}


# ─────────────── 路由查询结果 ───────────────

class RouteResult(BaseModel):
    """接口人路由结果 — 回答"这事找谁"。"""

    category: str = Field(..., description="匹配到的事项分类")
    primary: list[ContactInfo] = Field(default_factory=list, description="主负责人")
    backup: list[ContactInfo] = Field(default_factory=list, description="备份接口人")
    escalation: list[ContactInfo] = Field(default_factory=list, description="升级路径")
    note: str | None = None


class RouteResponse(BaseModel):
    """路由查询响应。"""

    query: str
    results: list[RouteResult]
    total: int


class ContactSearchResponse(BaseModel):
    """搜索响应。"""

    query: str
    contacts: list[ContactInfo]
    total: int
