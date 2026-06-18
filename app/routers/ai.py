"""AI 助手 API 路由。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] | None = Field(None, description="多轮对话历史,格式 [{role, content}, ...]")


class AgentToolCall(BaseModel):
    name: str
    args: dict
    ok: bool
    result_preview: str = ""
    truncated: bool = False


class AgentChatResponse(BaseModel):
    reply: str
    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    iterations: int = 0
    model: str = ""
    usage: dict = Field(default_factory=dict)
    source: str = "agent"


@router.post("/agent", response_model=AgentChatResponse, summary="AI Agent 智能问答（带工具调用）")
async def ai_agent(
    payload: AgentChatRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Agent 模式：AI 可自主调用工具查询真实数据。"""
    from app.services.agent import AgentService

    svc = AgentService()
    result = await svc.run(payload.message, session=session, history=payload.history)
    return AgentChatResponse(**result)


@router.post("/agent/stream", summary="AI Agent 流式问答（SSE）")
async def ai_agent_stream(
    payload: AgentChatRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Agent 流式模式：SSE 事件流，逐字输出 + 工具调用进度。"""
    from app.services.agent import AgentService, StreamingAgent

    svc = AgentService()

    async def event_generator():
        async for event in StreamingAgent(
            svc, payload.message, session=session, history=payload.history
        ).run():
            event_type = event["event"]
            data = event.get("data", {})
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


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
