"""企微智能机器人 — 意图路由服务。

策略（用户确认）：默认走 AI Agent；命中固定关键词时走快捷命令（稳定、低延迟）。

固定关键词命令：
- ``帮助`` / ``help`` / ``菜单``     → 返回命令说明
- ``库存 <可用区> [实例族]``         → 查云霄可售卖库存（本地快照）
- ``能否上线 <可用区>`` / ``上线 ..`` → 判断该区能否上线新设备

其余消息一律交给 :class:`AgentService` 做自然语言理解 + 工具调用。
快捷命令复用 ``agent_tools`` 的执行器，避免逻辑分叉。
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agent_tools import exec_check_online_capacity, exec_query_inventory
from app.utils.logger import get_logger

log = get_logger(__name__)

# @机器人 提及前缀，例如 "@运营助手 库存 广州六区"
_MENTION_RE = re.compile(r"^\s*@[^\s]+\s+")

_HELP_TEXT = (
    "我是 TEZ 运营助手，可以这样问我：\n"
    "1. 直接用自然语言提问，例如『示例可用区A还能上线设备吗』『示例可用区B S5 还有多少库存』\n"
    "2. 快捷命令：\n"
    "   • `库存 <可用区> [实例族]` —— 查可售卖库存\n"
    "   • `能否上线 <可用区>` —— 判断该区能否上线新设备\n"
    "   • `帮助` —— 查看本说明"
)

_HELP_KEYWORDS = ("帮助", "help", "菜单", "你好", "hi", "hello")
_INVENTORY_PREFIXES = ("库存", "查库存")
_ONLINE_PREFIXES = ("能否上线", "能上线", "可否上线", "可以上线", "是否能上线", "上线")


def _strip_mention(text: str) -> str:
    """去掉开头的 @机器人 提及。"""
    return _MENTION_RE.sub("", text or "", count=1).strip()


def _format_inventory(result: dict) -> str:
    if not result.get("ok"):
        return result.get("error", "查询失败")
    items = result.get("items", [])
    if not items:
        return f"未查到 {result.get('zone') or ''} 的库存记录。"
    lines = [
        f"【{result.get('zone') or '全部可用区'}】库存共 {result.get('count')} 条，"
        f"合计可售 {result.get('total_inventory')} 台",
        f"> 数据来源：本地快照（7天内有效）",
        ""
    ]
    for i in items[:15]:
        lines.append(
            f"• {i.get('instance_type') or i.get('instance_family') or '?'}："
            f"库存 {i.get('inventory')} / 安全水位 {i.get('inventory_threshold')}"
            f"（{i.get('billing_type') or '-'}）"
        )
    if result.get("truncated") or len(items) > 15:
        lines.append("\n…（仅显示前 15 条，请用更精确的实例族/类型缩小范围）")
    return "\n".join(lines)


def _format_online_capacity(result: dict) -> str:
    if not result.get("ok"):
        return result.get("error", "查询失败")
    lines = [
        result.get("conclusion", ""),
        f"机位：空闲 {result.get('free_count')} / 已用 {result.get('used_count')}"
        f" / 总计 {result.get('total_positions')}",
        f"设备：在线 {result.get('online_count')} / 离线 {result.get('offline_count')}",
    ]
    inv = result.get("sellable_inventory_total")
    if inv is not None:
        lines.append(f"可售卖库存合计：{inv} 台")
    if result.get("last_sync_at"):
        lines.append(f"（数据快照：{result['last_sync_at']}）")
    return "\n".join(lines)


class WecomBotService:
    """机器人消息处理：意图路由 + 回复文本生成。"""

    async def handle_text(self, raw_text: str, session: AsyncSession) -> str:
        """处理一条文本消息，返回回复文本。"""
        text = _strip_mention(raw_text)
        if not text:
            return _HELP_TEXT

        lower = text.lower()

        # 1. 帮助
        if any(lower == kw or lower.startswith(kw) and len(text) <= len(kw) + 1
               for kw in _HELP_KEYWORDS):
            return _HELP_TEXT

        # 2. 库存查询快捷命令
        for prefix in _INVENTORY_PREFIXES:
            if text.startswith(prefix):
                return await self._cmd_inventory(text[len(prefix):].strip(), session)

        # 3. 能否上线快捷命令
        for prefix in _ONLINE_PREFIXES:
            if text.startswith(prefix):
                rest = text[len(prefix):].strip()
                if rest:  # 必须带可用区，否则交给 AI
                    return await self._cmd_online(rest, session)

        # 4. 兜底：AI Agent
        return await self._fallback_agent(text, session)

    async def _cmd_inventory(self, rest: str, session: AsyncSession) -> str:
        parts = rest.split()
        zone = parts[0] if parts else ""
        family = parts[1] if len(parts) > 1 else ""
        if not zone:
            return "请指定可用区，例如：`库存 广州六区 S5`"
        result = await exec_query_inventory(
            {"zone": zone, "instance_family": family}, session
        )
        return _format_inventory(result)

    async def _cmd_online(self, rest: str, session: AsyncSession) -> str:
        zone = rest.split()[0] if rest.split() else ""
        if not zone:
            return "请指定可用区，例如：`能否上线 示例可用区A`"
        result = await exec_check_online_capacity({"zone": zone}, session)
        return _format_online_capacity(result)

    async def _fallback_agent(self, text: str, session: AsyncSession) -> str:
        try:
            from app.services.agent import AgentService

            svc = AgentService()
            if not svc.is_configured:
                return (
                    "暂未配置 AI 能力，可使用快捷命令：\n"
                    "`库存 <可用区> [实例族]` / `能否上线 <可用区>` / `帮助`"
                )
            result = await svc.run(text, session=session)
            reply = result.get("reply") or "（未生成回复）"
            log.info("wecom_bot.agent_done", iterations=result.get("iterations"),
                     tool_calls=len(result.get("tool_calls", [])),
                     reply_len=len(reply))
            return reply
        except Exception as exc:  # noqa: BLE001
            log.warning("wecom_bot.agent_failed", error=str(exc))
            return f"处理失败：{str(exc)[:150]}"


__all__ = ["WecomBotService"]
