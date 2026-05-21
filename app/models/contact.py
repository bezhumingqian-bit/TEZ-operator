"""接口人路由器数据模型。

模块 3：接口人路由器（People Router）
- 输入"我要做 X"→ 返回接口人 + 备份 + 升级路径
- 模糊搜索（场景/系统/姓名/英文名）
- 标注在岗状态
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Contact(Base):
    """接口人主表。"""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), comment="英文名（OA账号名）")
    display_name: Mapped[Optional[str]] = mapped_column(String(64), comment="中文名/昵称")
    team: Mapped[Optional[str]] = mapped_column(String(128), comment="所属团队")
    role: Mapped[Optional[str]] = mapped_column(String(128), comment="角色/职责简述")
    status: Mapped[str] = mapped_column(
        String(16), default="active", comment="active/vacation/left"
    )
    wecom_id: Mapped[Optional[str]] = mapped_column(String(64), comment="企微ID")
    phone: Mapped[Optional[str]] = mapped_column(String(32), comment="手机号")
    note: Mapped[Optional[str]] = mapped_column(Text, comment="备注")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # 关系
    responsibilities: Mapped[list["Responsibility"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )


class Category(Base):
    """事项分类表（树形结构）。

    例：
    - 母机相关 / 母机故障排查
    - 网络相关 / EIP/VPC/IPv6
    - 资源相关 / 从CVM要机器
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), comment="分类名称")
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id"), comment="父分类ID"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, comment="描述/关键词")
    sort_order: Mapped[int] = mapped_column(default=0, comment="排序")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # 自引用
    parent: Mapped[Optional["Category"]] = relationship(
        remote_side=[id], backref="children"
    )
    responsibilities: Mapped[list["Responsibility"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )


class Responsibility(Base):
    """接口人-事项关联表（谁负责什么）。"""

    __tablename__ = "responsibilities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    priority: Mapped[int] = mapped_column(
        default=1, comment="1=主负责人, 2=备份, 3=上升"
    )
    note: Mapped[Optional[str]] = mapped_column(Text, comment="备注")

    contact: Mapped["Contact"] = relationship(back_populates="responsibilities")
    category: Mapped["Category"] = relationship(back_populates="responsibilities")


class EscalationPath(Base):
    """升级路径表。"""

    __tablename__ = "escalation_paths"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    level: Mapped[int] = mapped_column(comment="升级层级 1/2/3")
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"))
    description: Mapped[Optional[str]] = mapped_column(Text, comment="该层级说明")

    contact: Mapped["Contact"] = relationship()
    category: Mapped["Category"] = relationship()
