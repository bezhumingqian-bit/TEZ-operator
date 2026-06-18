"""用户模型 + 认证工具。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """用户表。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")  # admin / ops / viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ─── 角色权限映射 ───

ROLE_PERMISSIONS = {
    "admin": ["dashboard", "hosts", "workorder", "assistant", "knowledge", "cost", "yunxiao", "users"],
    "ops": ["dashboard", "hosts", "workorder", "yunxiao"],
    "operator": ["dashboard", "hosts", "workorder", "assistant", "knowledge", "yunxiao", "users"],
    "viewer": ["dashboard", "hosts", "yunxiao"],
}


def has_permission(role: str, module: str) -> bool:
    """检查角色是否有权访问某模块。"""
    perms = ROLE_PERMISSIONS.get(role, [])
    return module in perms
