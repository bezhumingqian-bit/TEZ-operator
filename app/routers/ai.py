"""AI 助手 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db_session
from app.services.ai_service import AIService

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context_type: str | None = Field(None, description="上下文类型: competitive/knowledge/none")
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    reply: str
    model: str = ""
    usage: dict = {}


@router.get("/status", summary="AI 助手配置状态")
async def ai_status():
    svc = AIService()
    return {"configured": svc.is_configured}


@router.post("/chat", response_model=ChatResponse, summary="AI 对话")
async def ai_chat(
    payload: ChatRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """通用 AI 对话，可选附加知识库上下文。"""
    svc = AIService()

    context = ""
    if payload.context_type == "competitive":
        # 加载竞分文档作为上下文
        from sqlalchemy import select
        from app.models.knowledge import KnowledgeArticle
        stmt = select(KnowledgeArticle.content).where(KnowledgeArticle.category == "competitive").limit(5)
        result = await session.execute(stmt)
        docs = result.scalars().all()
        context = "\n\n---\n\n".join(d[:2000] for d in docs if d)

    elif payload.context_type == "knowledge":
        # 加载全部知识库文章作为上下文
        from sqlalchemy import select
        from app.models.knowledge import KnowledgeArticle
        stmt = select(KnowledgeArticle.content).where(KnowledgeArticle.status == "active").limit(8)
        result = await session.execute(stmt)
        docs = result.scalars().all()
        context = "\n\n---\n\n".join(d[:1500] for d in docs if d)

    result = await svc.chat(payload.message, context=context, history=payload.history)
    return ChatResponse(**result)


@router.post("/analyze", summary="竞争分析（AI生成）")
async def ai_analyze(
    question: str = "请生成竞争分析摘要",
    session: AsyncSession = Depends(get_db_session),
):
    """基于知识库竞分文档生成 AI 分析。"""
    svc = AIService()
    if not svc.is_configured:
        raise HTTPException(status_code=503, detail="AI 未配置，请在 .env 设置 TEZ_AI_API_BASE 和 TEZ_AI_API_KEY")

    # 加载竞分资料
    from sqlalchemy import select
    from app.models.knowledge import KnowledgeArticle
    stmt = select(KnowledgeArticle.content).where(KnowledgeArticle.category == "competitive").limit(5)
    result = await session.execute(stmt)
    docs = result.scalars().all()
    content = "\n\n---\n\n".join(d[:3000] for d in docs if d)

    if not content:
        raise HTTPException(status_code=404, detail="知识库中暂无竞分资料")

    result = await svc.analyze_competitive(content, question)
    return result
