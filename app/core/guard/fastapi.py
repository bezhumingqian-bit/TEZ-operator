"""FastAPI 集成：在路由层自动注入 Actor。"""

from __future__ import annotations

from fastapi import Header, Request

from app.core.guard.actor import Actor, ActorType


async def get_actor(
    request: Request,
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    x_actor_type: str | None = Header(default=None, alias="X-Actor-Type"),
    x_actor_session: str | None = Header(default=None, alias="X-Actor-Session"),
) -> Actor:
    """FastAPI 依赖：从 Header 提取 Actor。

    实际生产环境应该从 JWT/Session 中解析，这里先支持 Header 注入方便测试。

    用法:
        @router.post("/delete")
        async def delete_host(actor: Actor = Depends(get_actor)):
            ...
    """
    actor_id = x_actor_id or "anonymous"
    actor_type_str = x_actor_type or "human"
    try:
        actor_type = ActorType(actor_type_str)
    except ValueError:
        actor_type = ActorType.HUMAN

    return Actor(
        id=actor_id,
        type=actor_type,
        session_id=x_actor_session or f"sess-{actor_id}",
        permissions=["*"] if actor_type == ActorType.HUMAN else [],
        metadata={
            "ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
        },
    )
