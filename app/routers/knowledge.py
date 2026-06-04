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

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
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


# 上传目录
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / "knowledge"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".docx", ".pdf"}


@router.post("/articles/upload", response_model=ArticleInfo, status_code=201, summary="上传文档解析为文章")
async def upload_article(
    file: UploadFile = File(...),
    category: str = Form(default="competitive"),
    tags: str = Form(default=""),
    service: KnowledgeService = Depends(_get_service),
) -> ArticleInfo:
    """上传 Word/PDF 文档，自动解析为 Markdown 存入知识库。"""
    from app.services.document_parser import parse_document

    # 校验文件扩展名
    filename = file.filename or "unnamed"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式（仅支持 {', '.join(ALLOWED_EXTENSIONS)}）")

    # 读取并校验大小
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    # 解析文档
    try:
        result = parse_document(file_bytes, filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"文档解析失败: {str(exc)[:200]}")

    # 自动分类
    if category == "auto":
        from app.services.document_parser import auto_categorize
        category = auto_categorize(result["title"], result["content"])

    # 保存原始文件到 data/uploads/knowledge/
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    import time
    safe_name = f"{int(time.time())}_{filename}"
    save_path = UPLOAD_DIR / safe_name
    save_path.write_bytes(file_bytes)

    # 写入数据库
    art = await service.create_article(
        title=result["title"],
        category=category,
        content=result["content"],
        summary=result["summary"],
        tags=tags or None,
        source_file=f"uploads/knowledge/{safe_name}",
        importance=2,
    )
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



@router.get("/sop-flows", summary="获取运维SOP流程数据")
async def get_sop_flows():
    """返回所有场景的 SOP 分步操作流程。"""
    from app.data.sop_flows import SOP_FLOWS
    return {"items": SOP_FLOWS}


@router.get("/sop-flows/{flow_id}", summary="获取单个SOP流程详情")
async def get_sop_flow(flow_id: str):
    """返回指定场景的 SOP 流程。"""
    from app.data.sop_flows import SOP_FLOWS
    for flow in SOP_FLOWS:
        if flow["id"] == flow_id:
            return flow
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="SOP流程不存在")
