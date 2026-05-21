"""接口人路由器服务层。

核心能力：
1. route(query) — 输入场景描述，返回负责人+备份+升级路径
2. search(keyword) — 模糊搜索接口人（姓名/团队/职责）
3. CRUD — 管理接口人和分类数据
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contact import Category, Contact, EscalationPath, Responsibility
from app.schemas.contact import ContactCreate, ContactUpdate, RouteResult
from app.utils.logger import get_logger

log = get_logger(__name__)


class ContactService:
    """接口人路由器服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ─────────────── 路由（核心功能）───────────────

    async def route(self, query: str) -> list[RouteResult]:
        """根据场景描述，匹配分类并返回接口人链。

        匹配策略（简单有效）：
        1. 对 query 做分词/关键词提取
        2. 在 Category.name + Category.description 中做 LIKE 匹配
        3. 返回匹配到的分类对应的 primary/backup/escalation
        """
        if not query or not query.strip():
            return []

        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        # 搜索匹配的分类
        conditions = []
        for kw in keywords:
            like_pattern = f"%{kw}%"
            conditions.append(Category.name.ilike(like_pattern))
            conditions.append(Category.description.ilike(like_pattern))

        stmt = select(Category).where(or_(*conditions))
        result = await self.session.execute(stmt)
        categories = result.scalars().all()

        if not categories:
            return []

        # 对每个匹配的分类，查找接口人
        route_results: list[RouteResult] = []
        for cat in categories:
            resp_stmt = (
                select(Responsibility)
                .where(Responsibility.category_id == cat.id)
                .options(selectinload(Responsibility.contact))
                .order_by(Responsibility.priority)
            )
            resp_result = await self.session.execute(resp_stmt)
            responsibilities = resp_result.scalars().all()

            primary = []
            backup = []
            for r in responsibilities:
                if r.priority == 1:
                    primary.append(r.contact)
                elif r.priority == 2:
                    backup.append(r.contact)

            # 查升级路径
            esc_stmt = (
                select(EscalationPath)
                .where(EscalationPath.category_id == cat.id)
                .options(selectinload(EscalationPath.contact))  # type: ignore[attr-defined]
                .order_by(EscalationPath.level)
            )
            esc_result = await self.session.execute(esc_stmt)
            escalations = esc_result.scalars().all()
            escalation_contacts = [e.contact for e in escalations]

            route_results.append(
                RouteResult(
                    category=cat.name,
                    primary=primary,
                    backup=backup,
                    escalation=escalation_contacts,
                    note=cat.description,
                )
            )

        return route_results

    # ─────────────── 搜索 ───────────────

    async def search_contacts(self, keyword: str) -> list[Contact]:
        """模糊搜索接口人（姓名/团队/角色）。"""
        if not keyword or not keyword.strip():
            return []

        like = f"%{keyword.strip()}%"
        stmt = select(Contact).where(
            or_(
                Contact.name.ilike(like),
                Contact.display_name.ilike(like),
                Contact.team.ilike(like),
                Contact.role.ilike(like),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ─────────────── CRUD: Contact ───────────────

    async def create_contact(self, data: ContactCreate) -> Contact:
        contact = Contact(**data.model_dump())
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def get_contact(self, contact_id: int) -> Contact | None:
        return await self.session.get(Contact, contact_id)

    async def get_contact_by_name(self, name: str) -> Contact | None:
        stmt = select(Contact).where(Contact.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_contact(self, contact_id: int, data: ContactUpdate) -> Contact | None:
        contact = await self.session.get(Contact, contact_id)
        if not contact:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(contact, field, value)
        await self.session.flush()
        return contact

    async def list_contacts(self, status: str | None = None) -> list[Contact]:
        stmt = select(Contact).order_by(Contact.team, Contact.name)
        if status:
            stmt = stmt.where(Contact.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ─────────────── CRUD: Category ───────────────

    async def list_categories(self) -> list[Category]:
        """返回所有分类（扁平列表，前端自行构建树）。"""
        stmt = select(Category).order_by(Category.sort_order, Category.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_category(self, name: str, parent_id: int | None = None, description: str | None = None) -> Category:
        cat = Category(name=name, parent_id=parent_id, description=description)
        self.session.add(cat)
        await self.session.flush()
        return cat

    # ─────────────── CRUD: Responsibility ───────────────

    async def assign_responsibility(
        self, contact_id: int, category_id: int, priority: int = 1, note: str | None = None
    ) -> Responsibility:
        r = Responsibility(
            contact_id=contact_id,
            category_id=category_id,
            priority=priority,
            note=note,
        )
        self.session.add(r)
        await self.session.flush()
        return r

    # ─────────────── 内部 ───────────────

    @staticmethod
    def _extract_keywords(query: str) -> list[str]:
        """关键词提取：分词 + 中文子串展开。

        策略：
        1. 按标点/空格分词
        2. 去停用词
        3. 对长中文词做 2~4 字子串展开（简易中文分词替代）
        """
        import re

        tokens = re.split(r"[\s,，。、；;：:!！?？()（）\[\]【】/]+", query)
        stop_words = {"我", "要", "想", "做", "的", "了", "一下", "请问", "怎么", "如何", "找", "谁", "问题"}
        keywords: list[str] = []

        for t in tokens:
            t = t.strip()
            if not t or t in stop_words:
                continue
            keywords.append(t)
            # 对纯中文长词做子串展开
            if len(t) > 3 and re.match(r"^[\u4e00-\u9fff]+$", t):
                for size in (2, 3):
                    for i in range(len(t) - size + 1):
                        sub = t[i : i + size]
                        if sub not in stop_words:
                            keywords.append(sub)

        return list(dict.fromkeys(keywords))  # 去重保序
