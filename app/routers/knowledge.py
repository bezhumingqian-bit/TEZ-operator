"""知识中枢 API。

GET  /api/v1/knowledge/search?q=...     全文搜索
GET  /api/v1/knowledge/articles          文章列表
POST /api/v1/knowledge/articles          新增文章
GET  /api/v1/knowledge/articles/{id}/content  读取文章正文（从 docs/ 文件）
GET  /api/v1/knowledge/links             平台链接列表
POST /api/v1/knowledge/links             新增链接
GET  /api/v1/knowledge/faqs              FAQ列表
POST /api/v1/knowledge/faqs              新增FAQ
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.deps import get_db_session
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# docs 目录路径
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / ".codebuddy" / "teams" / "tez-ops" / "docs"


async def _get_service(session=Depends(get_db_session)):
    return KnowledgeService(session)


# ─── Schemas ───

class ArticleInfo(BaseModel):
    id: int
    title: str
    category: str
    summary: str | None = None
    tags: str | None = None
    url: str | None = None
    importance: int = 1
    model_config = {"from_attributes": True}


class ArticleCreate(BaseModel):
    title: str
    category: str = "manual"
    content: str | None = None
    summary: str | None = None
    tags: str | None = None
    url: str | None = None
    importance: int = 1


class LinkInfo(BaseModel):
    id: int
    name: str
    purpose: str | None = None
    url: str
    importance: int = 1
    category: str | None = None
    model_config = {"from_attributes": True}


class LinkCreate(BaseModel):
    name: str
    purpose: str | None = None
    url: str
    importance: int = 1
    category: str | None = None


class FAQInfo(BaseModel):
    id: int
    question: str
    answer: str
    category: str | None = None
    tags: str | None = None
    model_config = {"from_attributes": True}


class FAQCreate(BaseModel):
    question: str
    answer: str
    category: str | None = None
    tags: str | None = None


class SearchResponse(BaseModel):
    query: str
    articles: list[ArticleInfo] = []
    links: list[LinkInfo] = []
    faqs: list[FAQInfo] = []
    total: int = 0


# ─── Endpoints ───

@router.get("/search", response_model=SearchResponse, summary="全文搜索")
async def search_knowledge(
    q: str = Query(..., min_length=1),
    service: KnowledgeService = Depends(_get_service),
) -> SearchResponse:
    result = await service.search(q)
    return SearchResponse(
        query=q,
        articles=result["articles"],
        links=result["links"],
        faqs=result["faqs"],
        total=result["total"],
    )


@router.get("/articles", response_model=list[ArticleInfo], summary="文章列表")
async def list_articles(
    category: str | None = Query(None),
    service: KnowledgeService = Depends(_get_service),
) -> list[ArticleInfo]:
    return await service.list_articles(category=category)


@router.post("/articles", response_model=ArticleInfo, status_code=201, summary="新增文章")
async def create_article(
    payload: ArticleCreate,
    service: KnowledgeService = Depends(_get_service),
) -> ArticleInfo:
    art = await service.create_article(**payload.model_dump())
    await service.session.commit()
    return art


class ArticleContentResponse(BaseModel):
    id: int
    title: str
    content: str
    source_file: str | None = None


@router.get("/articles/{article_id}/content", response_model=ArticleContentResponse, summary="读取文章正文")
async def get_article_content(
    article_id: int,
    service: KnowledgeService = Depends(_get_service),
) -> ArticleContentResponse:
    """从 docs/ 目录读取 Markdown 文件内容。"""
    from sqlalchemy import select
    from app.models.knowledge import KnowledgeArticle

    stmt = select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
    result = await service.session.execute(stmt)
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    content = ""
    if article.source_file:
        # source_file 格式如 "docs/01-tez-product-background.md"
        file_path = Path(__file__).resolve().parent.parent.parent / article.source_file.replace("docs/", ".codebuddy/teams/tez-ops/docs/")
        if not file_path.exists():
            # 尝试直接在 DOCS_DIR 下找
            fname = Path(article.source_file).name
            file_path = DOCS_DIR / fname
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
        else:
            content = f"*文件未找到: {article.source_file}*"
    elif article.content:
        content = article.content
    else:
        content = "*暂无内容*"

    return ArticleContentResponse(
        id=article.id,
        title=article.title,
        content=content,
        source_file=article.source_file,
    )


@router.get("/links", response_model=list[LinkInfo], summary="平台链接列表")
async def list_links(
    service: KnowledgeService = Depends(_get_service),
) -> list[LinkInfo]:
    return await service.list_links()


@router.post("/links", response_model=LinkInfo, status_code=201, summary="新增链接")
async def create_link(
    payload: LinkCreate,
    service: KnowledgeService = Depends(_get_service),
) -> LinkInfo:
    link = await service.create_link(**payload.model_dump())
    await service.session.commit()
    return link


@router.get("/faqs", response_model=list[FAQInfo], summary="FAQ列表")
async def list_faqs(
    category: str | None = Query(None),
    service: KnowledgeService = Depends(_get_service),
) -> list[FAQInfo]:
    return await service.list_faqs(category=category)


@router.post("/faqs", response_model=FAQInfo, status_code=201, summary="新增FAQ")
async def create_faq(
    payload: FAQCreate,
    service: KnowledgeService = Depends(_get_service),
) -> FAQInfo:
    faq = await service.create_faq(**payload.model_dump())
    await service.session.commit()
    return faq
