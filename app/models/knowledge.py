"""知识中枢数据模型。

模块 5：知识中枢（Knowledge Hub）
- 知识手册管理
- 外部链接管理
- FAQ 管理
- 全文搜索
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KnowledgeArticle(Base):
    """知识手册/文章。"""

    __tablename__ = "knowledge_articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), comment="标题")
    category: Mapped[str] = mapped_column(String(64), comment="分类：manual/sop/faq/link")
    content: Mapped[Optional[str]] = mapped_column(Text, comment="正文内容（Markdown）")
    summary: Mapped[Optional[str]] = mapped_column(String(512), comment="摘要")
    tags: Mapped[Optional[str]] = mapped_column(String(512), comment="标签，逗号分隔")
    source_file: Mapped[Optional[str]] = mapped_column(String(256), comment="来源文件路径")
    url: Mapped[Optional[str]] = mapped_column(String(512), comment="外部链接URL")
    importance: Mapped[int] = mapped_column(Integer, default=1, comment="重要度 1-5")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="active/archived")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class FAQ(Base):
    """常见问题。"""

    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(String(512), comment="问题")
    answer: Mapped[str] = mapped_column(Text, comment="回答（支持HTML）")
    category: Mapped[Optional[str]] = mapped_column(String(64), comment="FAQ分类")
    tags: Mapped[Optional[str]] = mapped_column(String(256), comment="标签")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PlatformLink(Base):
    """平台链接。"""

    __tablename__ = "platform_links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), comment="平台名称")
    purpose: Mapped[Optional[str]] = mapped_column(String(512), comment="用途描述")
    url: Mapped[str] = mapped_column(String(512), comment="链接地址")
    importance: Mapped[int] = mapped_column(Integer, default=1, comment="重要度 1-5")
    category: Mapped[Optional[str]] = mapped_column(String(64), comment="分类")
    status: Mapped[str] = mapped_column(String(16), default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
