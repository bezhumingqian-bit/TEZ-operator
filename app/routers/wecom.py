"""企微智能机器人回调路由（Webhook 短连接模式）。

- ``GET  /api/v1/wecom/callback``：URL 验证（解密 echostr 原样返回）
- ``POST /api/v1/wecom/callback``：接收用户消息 → 意图路由 → 加密回复

加解密走企业微信标准 :mod:`app.utils.wecom_crypto`。凭证从环境变量读取
（``TEZ_WECOM_BOT_TOKEN`` / ``TEZ_WECOM_BOT_AES_KEY`` / ``TEZ_WECOM_BOT_RECEIVEID``）。

注意：智能机器人「设置接收消息回调地址」模式的消息体为 JSON（aibot_msg_callback），
回复通过本次 HTTP 响应体返回加密包。若后续企微联调发现回复信封格式不同，
仅需调整 :func:`_build_reply_envelope` 与 ``_extract_text`` 即可，加解密核心无需改动。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import get_db_session
from app.services.wecom_bot_service import WecomBotService
from app.utils.logger import get_logger
from app.utils.wecom_crypto import (
    WecomCryptoError,
    build_encrypted_reply,
    decrypt_message,
    verify_url,
)

log = get_logger(__name__)

router = APIRouter(prefix="/wecom", tags=["wecom-bot"])


def _ensure_configured() -> tuple[str, str, str]:
    """读取并校验机器人凭证，未配置则 404（对外不暴露细节）。"""
    s = get_settings()
    if not s.wecom_bot_token or not s.wecom_bot_aes_key:
        raise HTTPException(status_code=404, detail="Not Found")
    return s.wecom_bot_token, s.wecom_bot_aes_key, s.wecom_bot_receiveid


def _extract_text(payload: dict) -> tuple[str, str, str]:
    """从 aibot 回调中提取 (文本内容, req_id, receiveid)。

    仅处理文本消息；非文本 / 事件返回空文本。
    """
    headers = payload.get("headers") or {}
    req_id = headers.get("req_id", "")
    body = payload.get("body") or {}
    msgtype = body.get("msgtype", "")
    if msgtype == "text":
        content = ((body.get("text") or {}).get("content")) or ""
    else:
        content = ""
    return content, req_id, ""


def _build_reply_envelope(
    token: str, aes_key: str, receiveid: str, req_id: str,
    reply_text: str, timestamp: str, nonce: str,
) -> dict:
    """把回复文本封装为加密响应包。"""
    reply_plain = json.dumps(
        {
            "cmd": "aibot_respond_msg",
            "headers": {"req_id": req_id},
            "body": {"msgtype": "text", "text": {"content": reply_text}},
        },
        ensure_ascii=False,
    )
    return build_encrypted_reply(token, aes_key, reply_plain, receiveid, timestamp, nonce)


@router.get("/callback", summary="企微机器人回调 URL 验证")
async def verify_callback(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
) -> PlainTextResponse:
    """GET：企微回调地址校验。校验签名并解密 echostr，原样返回明文。"""
    token, aes_key, _ = _ensure_configured()
    try:
        plain = verify_url(token, aes_key, msg_signature, timestamp, nonce, echostr)
    except WecomCryptoError as exc:
        log.warning("wecom.verify_failed", error=str(exc))
        raise HTTPException(status_code=403, detail="verify failed") from exc
    log.info("wecom.verify_ok")
    return PlainTextResponse(plain)


@router.post("/callback", summary="企微机器人接收消息")
async def receive_callback(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
    """POST：接收加密消息 → 解密 → 意图路由 → 加密回复。"""
    token, aes_key, expect_receiveid = _ensure_configured()

    raw = await request.body()
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("wecom.bad_body", error=str(exc))
        raise HTTPException(status_code=400, detail="bad body") from exc

    encrypt_b64 = envelope.get("encrypt") or envelope.get("Encrypt") or ""
    if not encrypt_b64:
        raise HTTPException(status_code=400, detail="missing encrypt")

    # 解密 + 验签
    try:
        plain, receiveid = decrypt_message(
            token, aes_key, msg_signature, timestamp, nonce, encrypt_b64
        )
    except WecomCryptoError as exc:
        log.warning("wecom.decrypt_failed", error=str(exc))
        raise HTTPException(status_code=403, detail="decrypt failed") from exc

    # receiveid 校验（配置了才校验）
    if expect_receiveid and receiveid and receiveid != expect_receiveid:
        log.warning("wecom.receiveid_mismatch", got=receiveid)
        raise HTTPException(status_code=403, detail="receiveid mismatch")

    try:
        payload = json.loads(plain)
    except Exception as exc:  # noqa: BLE001
        log.warning("wecom.bad_plain", error=str(exc))
        raise HTTPException(status_code=400, detail="bad plain") from exc

    text, req_id, _ = _extract_text(payload)
    if not text:
        # 非文本消息 / 事件：不回复，返回空 200
        log.info("wecom.non_text_ignored", cmd=payload.get("cmd"))
        return JSONResponse(content={})

    log.info("wecom.msg_received", req_id=req_id, length=len(text))
    reply_text = await WecomBotService().handle_text(text, session)

    reply_receiveid = expect_receiveid or receiveid or ""
    reply = _build_reply_envelope(
        token, aes_key, reply_receiveid, req_id, reply_text, timestamp, nonce
    )
    return JSONResponse(content=reply)
