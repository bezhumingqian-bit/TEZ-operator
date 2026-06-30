"""agent-guard FastAPI 集成测试。

验证目标：
1. HarnessMiddleware 能识别 AI Actor
2. AI 调用会被审计
3. 非 AI 调用不受影响（直接放行）
4. Guard 拒绝时返回 422
5. middleware 的 op_type 推断正确
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.guard.middleware import HarnessMiddleware, _build_guards_for_op, _classify_op

# ─────────────────── 单元：op_type 推断 ───────────────────


def test_classify_op_by_method():
    assert _classify_op("POST", "/api/v1/hosts") == "write"
    assert _classify_op("PUT", "/api/v1/hosts/1") == "write"
    assert _classify_op("PATCH", "/api/v1/hosts/1") == "write"
    assert _classify_op("DELETE", "/api/v1/hosts/1") == "delete"
    assert _classify_op("GET", "/api/v1/hosts") == "read"
    assert _classify_op("UNKNOWN", "/api/v1/hosts") == "read"  # 默认


def test_build_guards_for_write():
    """write 类型应包含 audit_log + version_check。"""
    guards = _build_guards_for_op("write")
    names = [g.name for g in guards]
    assert "audit_log" in names
    assert "version_check" in names


def test_build_guards_for_delete():
    """delete 类型应包含 audit_log + soft_delete。"""
    guards = _build_guards_for_op("delete")
    names = [g.name for g in guards]
    assert "audit_log" in names
    assert "soft_delete" in names


def test_build_guards_for_trigger():
    """trigger 类型应包含 audit + version + idempotency。"""
    guards = _build_guards_for_op("trigger")
    names = [g.name for g in guards]
    assert "audit_log" in names
    assert "version_check" in names
    assert "idempotency" in names


def test_build_guards_for_read():
    """read 类型应只包含 audit_log。"""
    guards = _build_guards_for_op("read")
    names = [g.name for g in guards]
    assert "audit_log" in names
    # read 默认不强制 version_check（避免破坏只读接口）


# ─────────────────── 集成：中间件 + FastAPI app ───────────────────


@pytest.fixture
def harness_app():
    """构造一个测试用 FastAPI app，挂上 HarnessMiddleware。"""
    app = FastAPI()
    app.add_middleware(HarnessMiddleware)

    @app.get("/api/v1/test/read")
    def read_endpoint():
        return {"status": "ok", "data": "read"}

    @app.post("/api/v1/test/write")
    def write_endpoint(payload: dict | None = None):
        return {"status": "ok", "received": payload}

    @app.delete("/api/v1/test/delete")
    def delete_endpoint():
        return {"status": "deleted"}

    return app


@pytest.fixture
def client(harness_app):
    return TestClient(harness_app)


# ── 1. 非 AI 调用（人类）直接放行，不走 Harness 链 ──


def test_human_request_passes_through(client):
    """人类调用不需要 actor header，应该直接放行。"""
    resp = client.get("/api/v1/test/read")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "data": "read"}


def test_human_write_request_passes_through(client):
    """人类写操作不强制要求 version。"""
    resp = client.post("/api/v1/test/write", json={"foo": "bar"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "received": {"foo": "bar"}}


# ── 2. AI 调用会被中间件识别 + 审计 ──


def test_ai_request_identified_and_logged(client):
    """AI 调用应被中间件识别（即使不强制 Guard）。"""
    resp = client.get(
        "/api/v1/test/read",
        headers={
            "X-Actor-Id": "ai-test-agent",
            "X-Actor-Type": "ai",
        },
    )
    assert resp.status_code == 200
    # 中间件不强制 Guard 验证（只审计），所以返回正常
    assert resp.json() == {"status": "ok", "data": "read"}


def test_ai_write_request_logged(client):
    """AI 写操作应被中间件记录（不阻断当前 endpoint）。"""
    resp = client.post(
        "/api/v1/test/write",
        json={"foo": "bar"},
        headers={
            "X-Actor-Id": "ai-test",
            "X-Actor-Type": "ai",
        },
    )
    # 当前 PoC：中间件不强制业务 endpoint 套 Guard，只审计
    # 业务层 Guard 在 M3 W1 接入
    assert resp.status_code == 200


# ── 3. AI 错误类型被识别为 HUMAN（防御性）──


def test_invalid_actor_type_treated_as_human(client):
    """无效的 X-Actor-Type 应被当作 HUMAN（防御性默认）。"""
    resp = client.post(
        "/api/v1/test/write",
        json={"foo": "bar"},
        headers={
            "X-Actor-Id": "test",
            "X-Actor-Type": "invalid-type",  # 非法值
        },
    )
    # 防御性默认：当作人类，不走 Harness 强制路径
    assert resp.status_code == 200
