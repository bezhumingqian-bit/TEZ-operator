"""企业微信群机器人简单告警封装。

设计要点
========
- 仅依赖 ``httpx``，配置失败时静默降级（只 log）。
- 不阻塞主流程：调用方应当 ``asyncio.create_task(send_alert(...))``
  或 ``await`` 后忽略异常（已内部 try/except 包好）。
- 不在日志里打 webhook URL（防泄露）。
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import get_settings
from app.utils.logger import get_logger

log = get_logger(__name__)


async def send_alert(title: str, content: str, level: str = "warning") -> None:
    """发送企微告警。

    - 当 ``settings.wecom_webhook`` 为空时只 log，不发请求。
    - 任何异常都被吞掉（保证主流程不被告警影响）。
    """
    s = get_settings()
    log_method = log.warning if level != "info" else log.info
    log_method("alert", title=title, content=content[:200])
    webhook = s.wecom_webhook
    if not webhook:
        return

    try:
        # 延迟 import 避免依赖耦合
        import httpx

        msg = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"**[TEZ Operator] {title}**\n\n{content}\n\n> level: {level}",
            },
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(webhook, json=msg)
    except Exception as exc:  # noqa: BLE001
        log.warning("alert.send_failed", error=str(exc))


def alert_fire_and_forget(title: str, content: str, level: str = "warning") -> None:
    """非 await 版本：任意位置可调用，不阻塞主协程。"""
    try:
        asyncio.create_task(send_alert(title, content, level))
    except RuntimeError:
        # 不在事件循环里（比如启动期），降级到 log
        log.warning("alert.no_loop", title=title, content=content[:200])


__all__ = ["send_alert", "alert_fire_and_forget", "Any"]
