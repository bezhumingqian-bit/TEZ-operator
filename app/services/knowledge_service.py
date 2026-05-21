"""知识中枢服务层。"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import FAQ, KnowledgeArticle, PlatformLink
from app.utils.logger import get_logger

log = get_logger(__name__)


class KnowledgeService:
    """知识中枢服务。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ─── 全文搜索 ───

    async def search(self, query: str) -> dict:
        """跨表全文搜索：文章+链接+FAQ。"""
        if not query or not query.strip():
            return {"articles": [], "links": [], "faqs": [], "total": 0}

        like = f"%{query.strip()}%"

        # 搜文章
        art_stmt = select(KnowledgeArticle).where(
            or_(
                KnowledgeArticle.title.ilike(like),
                KnowledgeArticle.content.ilike(like),
                KnowledgeArticle.summary.ilike(like),
                KnowledgeArticle.tags.ilike(like),
            )
        ).limit(20)
        arts = (await self.session.execute(art_stmt)).scalars().all()

        # 搜链接
        link_stmt = select(PlatformLink).where(
            or_(
                PlatformLink.name.ilike(like),
                PlatformLink.purpose.ilike(like),
            )
        ).limit(20)
        links = (await self.session.execute(link_stmt)).scalars().all()

        # 搜FAQ
        faq_stmt = select(FAQ).where(
            or_(
                FAQ.question.ilike(like),
                FAQ.answer.ilike(like),
                FAQ.tags.ilike(like),
            )
        ).limit(20)
        faqs = (await self.session.execute(faq_stmt)).scalars().all()

        return {
            "articles": list(arts),
            "links": list(links),
            "faqs": list(faqs),
            "total": len(arts) + len(links) + len(faqs),
        }

    # ─── 文章 CRUD ───

    async def list_articles(self, category: str | None = None) -> list[KnowledgeArticle]:
        stmt = select(KnowledgeArticle).where(KnowledgeArticle.status == "active")
        if category:
            stmt = stmt.where(KnowledgeArticle.category == category)
        stmt = stmt.order_by(KnowledgeArticle.importance.desc(), KnowledgeArticle.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_article(self, **kwargs) -> KnowledgeArticle:
        art = KnowledgeArticle(**kwargs)
        self.session.add(art)
        await self.session.flush()
        return art

    # ─── 链接 CRUD ───

    async def list_links(self) -> list[PlatformLink]:
        stmt = select(PlatformLink).where(
            PlatformLink.status == "active"
        ).order_by(PlatformLink.importance.desc(), PlatformLink.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_link(self, **kwargs) -> PlatformLink:
        link = PlatformLink(**kwargs)
        self.session.add(link)
        await self.session.flush()
        return link

    # ─── FAQ CRUD ───

    async def list_faqs(self, category: str | None = None) -> list[FAQ]:
        stmt = select(FAQ).where(FAQ.status == "active")
        if category:
            stmt = stmt.where(FAQ.category == category)
        stmt = stmt.order_by(FAQ.sort_order, FAQ.id)
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_faq(self, **kwargs) -> FAQ:
        faq = FAQ(**kwargs)
        self.session.add(faq)
        await self.session.flush()
        return faq
