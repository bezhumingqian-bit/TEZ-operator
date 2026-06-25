"""企微智能机器人 WebSocket 长连接客户端。

协议规范（企业微信官方）：
- 连接地址：``wss://openws.work.weixin.qq.com``
- 订阅命令：``aibot_subscribe`` —— 发送 BotID + Secret 完成身份校验
- 消息回调：``aibot_msg_callback`` —— 用户文本消息（群内 @ 或单聊）
- 事件回调：``aibot_event_callback`` —— 进入会话 / 模板卡片等
- 回复消息：``aibot_respond_msg`` —— 以 ``req_id`` 关联回调回复
- 回复欢迎语：``aibot_respond_welcome_msg``
- 心跳保活：每 30 秒发一次 WebSocket ping 帧
- 断线重连：指数退避 1s → ... → 60s，连接成功重置

全明文 JSON，无需加解密。
"""

from __future__ import annotations

import asyncio
import json
import uuid

import websockets
from websockets.asyncio.client import ClientConnection

from app.config import get_settings
from app.services.wecom_bot_service import WecomBotService
from app.utils.logger import get_logger

log = get_logger(__name__)

WS_URL = "wss://openws.work.weixin.qq.com"
HEARTBEAT_INTERVAL = 30
RECONNECT_BASE = 1.0
RECONNECT_MAX = 60.0

WELCOME_TEXT = (
    "欢迎使用 TEZ 运营助手！\n"
    "你可以直接问我：\n"
    "• 某可用区还有多少库存？\n"
    "• 某节点能否上线新设备？\n"
    "• 查某台机器的状态\n\n"
    "也可以使用快捷命令：\n"
    "`库存 <可用区>` / `能否上线 <可用区>` / `帮助`"
)


class WecomWSClient:
    """企微智能机器人长连接客户端。

    在 FastAPI lifespan 中启动，作为后台任务运行，负责：
    1. 建立 WebSocket 连接并发送订阅请求
    2. 维持心跳
    3. 接收消息回调 → 委托 ``WecomBotService`` 处理 → 发送回复
    4. 断线自动重连
    """

    def __init__(self) -> None:
        self._reconnect_delay = RECONNECT_BASE
        self._should_stop = False

    async def run(self) -> None:
        """主循环：连接 → 服务 → 断线重连。"""
        settings = get_settings()
        if not settings.wecom_bot_id or not settings.wecom_bot_secret:
            log.info("wecom_ws.disabled")
            return

        bot_id = settings.wecom_bot_id
        secret = settings.wecom_bot_secret

        log.info("wecom_ws.starting", bot_id=bot_id[:8] + "***")

        while not self._should_stop:
            try:
                await self._connect_and_serve(bot_id, secret)
            except websockets.exceptions.ConnectionClosed as exc:
                log.warning("wecom_ws.connection_lost", code=exc.code, reason=exc.reason)
            except asyncio.CancelledError:
                log.info("wecom_ws.cancelled")
                break
            except Exception as exc:  # noqa: BLE001
                log.error("wecom_ws.unexpected_error", error=str(exc))

            if self._should_stop:
                break

            # 指数退避重连
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, RECONNECT_MAX)
            log.info("wecom_ws.reconnecting", delay=self._reconnect_delay)

    def stop(self) -> None:
        """设置停止标志，退出 run() 循环。"""
        self._should_stop = True

    async def _connect_and_serve(self, bot_id: str, secret: str) -> None:
        """建立连接 → 订阅 → 处理消息循环。"""
        async with websockets.connect(
            WS_URL, ping_interval=None, close_timeout=5,
        ) as ws:
            log.info("wecom_ws.connected")
            await self._subscribe(ws, bot_id, secret)

            # 连接成功，重连延迟重置
            self._reconnect_delay = RECONNECT_BASE

            # 启动应用层心跳任务（企微要求显式发送 ping 命令）
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

            try:
                log.info("wecom_ws.listening")
                async for raw in ws:
                    if self._should_stop:
                        break
                    await self._dispatch(ws, raw)
            except asyncio.CancelledError:
                pass
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _heartbeat_loop(self, ws: ClientConnection) -> None:
        """应用层心跳：每 30 秒发送 ping 命令（企微要求）。"""
        while not self._should_stop:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await ws.send(json.dumps({"cmd": "ping"}))
                log.info("wecom_ws.ping_sent")
            except Exception:  # noqa: BLE001, S110
                break  # 发送失败则退出心跳，run() 会触发重连

    async def _subscribe(self, ws: ClientConnection, bot_id: str, secret: str) -> None:
        """发送订阅请求进行身份校验。"""
        req_id = uuid.uuid4().hex[:16]
        payload = {
            "cmd": "aibot_subscribe",
            "headers": {"req_id": req_id},
            "body": {"bot_id": bot_id, "secret": secret},
        }
        await ws.send(json.dumps(payload, ensure_ascii=False))
        log.info("wecom_ws.subscribe_sent", req_id=req_id)

        # 等待响应（通常秒级返回）
        raw = await asyncio.wait_for(ws.recv(), timeout=15)
        resp = json.loads(raw)
        errcode = resp.get("errcode", -1)
        if errcode == 0:
            log.info("wecom_ws.subscribe_ok")
        else:
            log.error("wecom_ws.subscribe_failed", errcode=errcode, errmsg=resp.get("errmsg"))
            raise ConnectionError(f"订阅失败: {resp.get('errmsg', 'errcode=' + str(errcode))}")

    async def _dispatch(self, ws: ClientConnection, raw: str | bytes) -> None:
        """分发消息回调或事件回调。"""
        try:
            data = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode())
        except json.JSONDecodeError:
            log.debug("wecom_ws.bad_json", raw_length=len(str(raw)))
            return

        cmd = data.get("cmd", "")
        errcode = data.get("errcode")
        if errcode is not None and errcode != 0:
            log.warning("wecom_ws.server_error", cmd=cmd, errcode=errcode,
                        errmsg=data.get("errmsg", ""), full=data)
        if cmd == "aibot_msg_callback":
            await self._on_msg_callback(ws, data)
        elif cmd == "aibot_event_callback":
            await self._on_event_callback(ws, data)
        elif cmd in ("pong", "ping"):
            # 心跳响应，忽略
            log.debug("wecom_ws.heartbeat", cmd=cmd)
        else:
            # 订阅响应 / 其他，忽略
            log.debug("wecom_ws.ignored_cmd", cmd=cmd)

    # ── 消息回调 ──

    async def _on_msg_callback(self, ws: ClientConnection, data: dict) -> None:
        """处理用户消息（仅文本）。"""
        headers = data.get("headers") or {}
        req_id = headers.get("req_id", "")
        body = data.get("body") or {}
        msgtype = body.get("msgtype", "")

        if msgtype != "text":
            log.debug("wecom_ws.non_text", msgtype=msgtype)
            return

        content = (body.get("text") or {}).get("content") or ""
        chatid = body.get("chatid", "")
        chattype = body.get("chattype", "")
        log.info(
            "wecom_ws.msg_received",
            req_id=req_id,
            length=len(content),
            chattype=chattype,
        )

        reply_text = await self._process_message(content)
        log.info("wecom_ws.reply_ready", req_id=req_id, length=len(reply_text))
        await self._send_text_reply(ws, req_id, reply_text, chatid=chatid, chattype=chattype)

    async def _process_message(self, content: str) -> str:
        """调用 WecomBotService 处理消息（带 DB session）。"""
        from app.deps import _get_session_factory

        factory = _get_session_factory()
        try:
            async with factory() as session:
                return await WecomBotService().handle_text(content, session)
        except Exception as exc:  # noqa: BLE001
            log.error("wecom_ws.process_failed", error=str(exc))
            return f"处理失败：{str(exc)[:150]}"

    # ── 事件回调 ──

    async def _on_event_callback(self, ws: ClientConnection, data: dict) -> None:
        """处理事件回调（进入会话 / 连接断开）。"""
        headers = data.get("headers") or {}
        req_id = headers.get("req_id", "")
        body = data.get("body") or {}
        event_type = (body.get("event") or {}).get("eventtype", "")

        if event_type == "enter_chat":
            log.info("wecom_ws.enter_chat", req_id=req_id)
            await self._send_welcome(ws, req_id)
        elif event_type == "disconnected_event":
            log.warning("wecom_ws.disconnected_by_server")
        else:
            log.debug("wecom_ws.event_ignored", event_type=event_type)

    # ── 发送回复 ──

    async def _send_text_reply(
        self, ws: ClientConnection, req_id: str, text: str,
        chatid: str = "", chattype: str = "",
    ) -> None:
        """发送普通文本回复。"""
        # 截断超长文本（企微单条文本约 2048 byte 限制）
        if len(text.encode("utf-8")) > 1800:
            text = text.encode("utf-8")[:1800].decode("utf-8", errors="ignore") + "…"

        payload = {
            "cmd": "aibot_respond_msg",
            "headers": {"req_id": req_id},
            "body": {"msgtype": "markdown", "markdown": {"content": text}},
        }
        try:
            await ws.send(json.dumps(payload, ensure_ascii=False))
            log.info("wecom_ws.reply_sent", req_id=req_id, length=len(text))
        except Exception:  # noqa: BLE001, S110
            log.warning("wecom_ws.reply_failed", req_id=req_id)

    async def _send_welcome(self, ws: ClientConnection, req_id: str) -> None:
        """发送进入会话欢迎语。"""
        payload = {
            "cmd": "aibot_respond_welcome_msg",
            "headers": {"req_id": req_id},
            "body": {"msgtype": "text", "text": {"content": WELCOME_TEXT}},
        }
        try:
            await ws.send(json.dumps(payload, ensure_ascii=False))
            log.debug("wecom_ws.welcome_sent", req_id=req_id)
        except Exception:  # noqa: BLE001, S110
            log.warning("wecom_ws.welcome_failed", req_id=req_id)


__all__ = ["WecomWSClient"]
