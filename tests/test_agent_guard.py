"""agent-guard PoC 测试。

验证目标：
1. 装饰器能正常串起 Guard 链
2. Guard 的 before/after 能被正确调用
3. AI Actor 触发的动作会被审计日志记录
4. soft_delete 能拦截 hard_delete 请求
5. version_check 能拦截缺少 version 的请求
6. result_limit 能截断超大结果集
7. idempotency 能保证重复调用返回一致结果
"""

from __future__ import annotations

import pytest

from app.core.guard import (
    Actor,
    ActorType,
    GuardRejected,
    audit_log,
    guard_chain,
)
from app.core.guard.guards import (
    idempotency,
    result_limit,
    soft_delete,
    version_check,
)

# ─────────────────── 1. 基础：Guard 链能正常执行 ───────────────────


@pytest.mark.asyncio
async def test_guard_chain_passes_through():
    """基础场景：单个 Guard 链不影响原函数执行。"""
    calls = []

    @guard_chain(audit_log())
    async def simple(x: int, actor: Actor) -> int:
        calls.append(("called", x))
        return x * 2

    actor = Actor(id="ai-test", type=ActorType.AI)
    result = await simple(5, actor=actor)
    assert result == 10
    assert calls == [("called", 5)]


@pytest.mark.asyncio
async def test_guard_chain_preserves_signature():
    """Guard 链函数应保留原函数签名和元信息。"""
    @guard_chain(audit_log())
    async def my_func(x: int, actor: Actor) -> int:
        """My docstring."""
        return x

    assert my_func.__name__ == "my_func"
    assert "My docstring" in (my_func.__doc__ or "")
    assert "audit_log" in my_func.__harness_guards__


# ─────────────────── 2. AI Actor 强制要求 ───────────────────


@pytest.mark.asyncio
async def test_guard_chain_requires_actor():
    """不传 actor 时应该报错（不能在没有身份的情况下走 Guard 链）。"""
    @guard_chain(audit_log())
    async def my_func(x: int, actor: Actor) -> int:
        return x

    with pytest.raises(GuardRejected, match="actor"):
        await my_func(5)  # 没传 actor


# ─────────────────── 3. soft_delete 拦截 hard_delete ───────────────────


@pytest.mark.asyncio
async def test_soft_delete_blocks_hard_delete():
    """AI 试图 hard_delete 时必须被 Guard 拦截。"""
    actor = Actor(id="ai-test", type=ActorType.AI)

    @guard_chain(soft_delete())
    async def delete_func(
        asset_id: str,
        actor: Actor,
        hard_delete: bool = False,
        deleted_at: str | None = None,
        deleted_by: str | None = None,
    ) -> dict:
        return {
            "asset_id": asset_id,
            "hard_delete": hard_delete,
            "deleted_at": deleted_at,
            "deleted_by": deleted_by,
        }

    # AI 试图 hard_delete → 拒绝
    with pytest.raises(GuardRejected, match="禁止 hard_delete"):
        await delete_func("TZA-001", actor=actor, hard_delete=True)


@pytest.mark.asyncio
async def test_soft_delete_injects_metadata():
    """正常软删除应自动注入 deleted_at / deleted_by。"""
    actor = Actor(id="ai-test", type=ActorType.AI)

    @guard_chain(soft_delete())
    async def delete_func(
        asset_id: str,
        actor: Actor,
        deleted_at: str | None = None,
        deleted_by: str | None = None,
    ) -> dict:
        return {
            "asset_id": asset_id,
            "deleted_at": deleted_at,
            "deleted_by": deleted_by,
        }

    result = await delete_func("TZA-001", actor=actor)
    assert result["asset_id"] == "TZA-001"
    assert result["deleted_at"] is not None
    assert result["deleted_by"] == "ai-test"


# ─────────────────── 4. version_check 拦截缺 version ───────────────────


@pytest.mark.asyncio
async def test_version_check_requires_version():
    """AI 写入不带 version 应被拦截（防止并发覆盖）。"""
    actor = Actor(id="ai-test", type=ActorType.AI)

    @guard_chain(version_check())
    async def update_func(payload: dict, actor: Actor, version: int | None = None) -> dict:
        return {"version": version, "payload": payload}

    with pytest.raises(GuardRejected, match="version"):
        await update_func({"name": "new"}, actor=actor)


@pytest.mark.asyncio
async def test_version_check_passes_with_version():
    """带 version 的写入应正常通过。"""
    actor = Actor(id="ai-test", type=ActorType.AI)

    @guard_chain(version_check())
    async def update_func(payload: dict, actor: Actor, version: int | None = None) -> dict:
        return {"version": version, "payload": payload}

    result = await update_func({"name": "new"}, actor=actor, version=3)
    assert result["version"] == 3
    assert result["payload"] == {"name": "new"}


# ─────────────────── 5. result_limit 截断超大结果 ───────────────────


@pytest.mark.asyncio
async def test_result_limit_truncates_list():
    """返回 list 超过限制应被截断 + 标记。"""
    actor = Actor(id="ai-test", type=ActorType.AI)

    @guard_chain(result_limit(max_items=3))
    async def list_func(actor: Actor) -> list:
        return [{"id": i} for i in range(10)]

    result = await list_func(actor=actor)
    # 截断后会被包装成 dict（含 _truncated 标记）
    assert isinstance(result, dict)
    assert result["_truncated"] is True
    assert result["_original_size"] == 10
    assert result["_limit"] == 3
    assert len(result["items"]) == 3


@pytest.mark.asyncio
async def test_result_limit_passes_under_limit():
    """未超限的 list 应原样返回。"""
    actor = Actor(id="ai-test", type=ActorType.AI)

    @guard_chain(result_limit(max_items=100))
    async def list_func(actor: Actor) -> list:
        return [{"id": i} for i in range(5)]

    result = await list_func(actor=actor)
    assert isinstance(result, list)  # 不包装
    assert len(result) == 5


# ─────────────────── 6. idempotency 重复调用返回一致 ───────────────────


@pytest.mark.asyncio
async def test_idempotency_caches_result():
    """同一 key 重复调用应返回首次结果，不重复执行。"""
    actor = Actor(id="ai-test", type=ActorType.AI)
    call_count = 0

    @guard_chain(idempotency())
    async def trigger(actor: Actor, idempotency_key: str = "key-001") -> dict:
        nonlocal call_count
        call_count += 1
        return {"call": call_count, "key": idempotency_key}

    r1 = await trigger(actor=actor, idempotency_key="same-key")
    r2 = await trigger(actor=actor, idempotency_key="same-key")

    # 只执行一次
    assert call_count == 1
    # 两次返回相同结果
    assert r1 == r2
    assert r1["call"] == 1


@pytest.mark.asyncio
async def test_idempotency_different_keys():
    """不同 key 应分别执行。"""
    actor = Actor(id="ai-test", type=ActorType.AI)
    call_count = 0

    @guard_chain(idempotency())
    async def trigger(actor: Actor, idempotency_key: str = "key") -> dict:
        nonlocal call_count
        call_count += 1
        return {"call": call_count}

    r1 = await trigger(actor=actor, idempotency_key="key-A")
    r2 = await trigger(actor=actor, idempotency_key="key-B")

    assert call_count == 2
    assert r1["call"] == 1
    assert r2["call"] == 2


# ─────────────────── 7. 完整链：audit + soft_delete ───────────────────


@pytest.mark.asyncio
async def test_full_chain_audit_plus_soft_delete():
    """完整 Guard 链：audit + soft_delete 组合工作。"""
    actor = Actor(id="ai-agent-v1", type=ActorType.AI)

    @guard_chain(audit_log(), soft_delete())
    async def delete_host(
        asset_id: str,
        actor: Actor,
        deleted_at: str | None = None,
        deleted_by: str | None = None,
    ) -> dict:
        return {
            "status": "soft_deleted",
            "asset_id": asset_id,
            "deleted_at": deleted_at,
            "deleted_by": deleted_by,
        }

    result = await delete_host("TZA-999", actor=actor)
    assert result["status"] == "soft_deleted"
    assert result["asset_id"] == "TZA-999"
    assert result["deleted_at"] is not None
    assert result["deleted_by"] == "ai-agent-v1"


@pytest.mark.asyncio
async def test_chain_stops_on_first_rejection():
    """前面的 Guard 拒绝后，后面的不会执行。"""
    actor = Actor(id="ai-test", type=ActorType.AI)
    after_called = []

    @guard_chain(soft_delete(), version_check())
    async def my_func(actor: Actor, **kwargs) -> dict:
        after_called.append("called")
        return {}

    # soft_delete 会先拒绝 hard_delete
    with pytest.raises(GuardRejected, match="hard_delete"):
        await my_func(actor=actor, hard_delete=True)

    # 原函数不应该被调用
    assert after_called == []


# ─────────────────── 8. Actor 权限检查 ───────────────────


def test_actor_has_permission_wildcard():
    """* 通配符应匹配所有权限。"""
    actor = Actor(id="admin", type=ActorType.HUMAN, permissions=["*"])
    assert actor.has_permission("anything:at:all")
    assert actor.has_permission("resource:delete")


def test_actor_has_permission_prefix():
    """前缀通配符应匹配对应前缀。"""
    actor = Actor(id="dev", type=ActorType.HUMAN, permissions=["resource:*"])
    assert actor.has_permission("resource:read")
    assert actor.has_permission("resource:write")
    assert not actor.has_permission("user:delete")


def test_actor_has_permission_exact():
    """精确匹配。"""
    actor = Actor(id="limited", type=ActorType.AI, permissions=["resource:read"])
    assert actor.has_permission("resource:read")
    assert not actor.has_permission("resource:write")


# ─────────────────── 9. HostService guarded 入口（PoC 真实集成）───────────────────


async def _async(value):
    """辅助：把值包装成 awaitable。"""
    return value


@pytest.mark.asyncio
async def test_host_service_guarded_accepts_ai_actor():
    """PoC 验证：get_host_guarded 能接受 AI actor 并正常走 Guard 链。"""
    from app.core.guard.actor import Actor as GuardActor
    from app.core.guard.actor import ActorType
    from app.services.host_service import HostService

    # 跳过 __init__（避免初始化三个客户端），把 get_host mock 掉
    real_svc = HostService.__new__(HostService)
    real_svc.get_host = lambda aid: _async({"asset_id": aid, "status": "mock"})  # type: ignore[assignment]

    ai_actor = GuardActor(id="ai-test", type=ActorType.AI)
    result = await real_svc.get_host_guarded("TZA-001", actor=ai_actor)
    assert result["asset_id"] == "TZA-001"
    assert result["status"] == "mock"
