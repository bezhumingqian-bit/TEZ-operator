"""企微机器人意图路由服务单元测试。"""

from __future__ import annotations

from app.services import wecom_bot_service as mod
from app.services.wecom_bot_service import WecomBotService

_SESSION = object()  # 哨兵：被 mock 的执行器不会真正使用


async def test_help_keyword():
    svc = WecomBotService()
    reply = await svc.handle_text("帮助", _SESSION)
    assert "快捷命令" in reply


async def test_empty_after_mention_returns_help():
    svc = WecomBotService()
    reply = await svc.handle_text("@运营助手   ", _SESSION)
    assert "快捷命令" in reply


async def test_inventory_command(monkeypatch):
    async def fake_inv(args, session):
        assert args["zone"] == "广州六区"
        assert args["instance_family"] == "S5"
        return {
            "ok": True, "zone": "广州六区", "count": 1, "total_inventory": 500,
            "items": [{
                "instance_type": "S5.MEDIUM4", "inventory": 500,
                "inventory_threshold": 50, "billing_type": "按量计费",
            }],
            "truncated": False,
        }

    monkeypatch.setattr(mod, "exec_query_inventory", fake_inv)
    svc = WecomBotService()
    reply = await svc.handle_text("库存 广州六区 S5", _SESSION)
    assert "广州六区" in reply
    assert "500" in reply
    assert "S5.MEDIUM4" in reply


async def test_inventory_command_with_mention(monkeypatch):
    async def fake_inv(args, session):
        return {"ok": True, "zone": args["zone"], "count": 0, "total_inventory": 0,
                "items": [], "truncated": False}

    monkeypatch.setattr(mod, "exec_query_inventory", fake_inv)
    svc = WecomBotService()
    reply = await svc.handle_text("@bot 库存 上海边缘三区", _SESSION)
    assert "上海边缘三区" in reply


async def test_inventory_command_missing_zone(monkeypatch):
    called = False

    async def fake_inv(args, session):
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(mod, "exec_query_inventory", fake_inv)
    svc = WecomBotService()
    reply = await svc.handle_text("库存", _SESSION)
    assert "请指定可用区" in reply
    assert called is False


async def test_online_command(monkeypatch):
    async def fake_online(args, session):
        assert args["zone"] == "示例可用区A"
        return {
            "ok": True, "zone": "示例可用区A", "can_online": True,
            "conclusion": "可以上线：示例可用区A 当前有 12 个空闲机位",
            "free_count": 12, "used_count": 8, "total_positions": 20,
            "online_count": 6, "offline_count": 2,
            "sellable_inventory_total": 100, "last_sync_at": None,
        }

    monkeypatch.setattr(mod, "exec_check_online_capacity", fake_online)
    svc = WecomBotService()
    reply = await svc.handle_text("能否上线 示例可用区A", _SESSION)
    assert "可以上线" in reply
    assert "12" in reply


async def test_fallback_to_agent(monkeypatch):
    class FakeAgent:
        @property
        def is_configured(self):
            return True

        async def run(self, message, session=None, history=None):
            return {"reply": f"AI 回答：{message}"}

    import app.services.agent as agent_mod
    monkeypatch.setattr(agent_mod, "AgentService", FakeAgent)

    svc = WecomBotService()
    reply = await svc.handle_text("沈阳还能扩容吗", _SESSION)
    assert reply.startswith("AI 回答：")


async def test_fallback_agent_not_configured(monkeypatch):
    class FakeAgent:
        @property
        def is_configured(self):
            return False

        async def run(self, *a, **k):  # pragma: no cover - 不应被调用
            raise AssertionError("不应调用 run")

    import app.services.agent as agent_mod
    monkeypatch.setattr(agent_mod, "AgentService", FakeAgent)

    svc = WecomBotService()
    reply = await svc.handle_text("随便问问", _SESSION)
    assert "快捷命令" in reply
