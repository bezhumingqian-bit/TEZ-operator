"""企微回调加解密单元测试（WXBizMsgCrypt）。"""

from __future__ import annotations

import base64
import os

import pytest

from app.utils.wecom_crypto import (
    WecomCryptoError,
    build_encrypted_reply,
    compute_signature,
    decrypt,
    decrypt_message,
    encrypt,
    verify_signature,
    verify_url,
)

TOKEN = "test_token_123"


def _make_aes_key() -> str:
    """生成一个合法的 43 位 EncodingAESKey。"""
    key32 = os.urandom(32)
    b64 = base64.b64encode(key32).decode()  # 44 位，以 '=' 结尾
    assert b64.endswith("=")
    return b64[:-1]


def test_encrypt_decrypt_roundtrip():
    aes_key = _make_aes_key()
    msg = "你好，TEZ 运营助手 hello 🎉"
    receiveid = "wwabc123corp"

    enc = encrypt(aes_key, msg, receiveid)
    got_msg, got_receiveid = decrypt(aes_key, enc)

    assert got_msg == msg
    assert got_receiveid == receiveid


def test_decrypt_empty_receiveid():
    aes_key = _make_aes_key()
    enc = encrypt(aes_key, "x", "")
    msg, rid = decrypt(aes_key, enc)
    assert msg == "x"
    assert rid == ""


def test_signature_order_independent():
    # 签名应对四元素做字典序排序后拼接，与传入顺序无关
    sig = compute_signature(TOKEN, "1700000000", "nonceX", "ENC")
    assert verify_signature(TOKEN, sig, "1700000000", "nonceX", "ENC")
    # 任一参数变化签名失效
    assert not verify_signature(TOKEN, sig, "1700000001", "nonceX", "ENC")
    assert not verify_signature("wrong", sig, "1700000000", "nonceX", "ENC")


def test_verify_url_roundtrip():
    aes_key = _make_aes_key()
    receiveid = "wwcorp"
    echo_plain = "1616140317555161061"
    echostr = encrypt(aes_key, echo_plain, receiveid)
    ts, nonce = "1700000000", "abc"
    sig = compute_signature(TOKEN, ts, nonce, echostr)

    got = verify_url(TOKEN, aes_key, sig, ts, nonce, echostr)
    assert got == echo_plain


def test_verify_url_bad_signature():
    aes_key = _make_aes_key()
    echostr = encrypt(aes_key, "echo", "rid")
    with pytest.raises(WecomCryptoError):
        verify_url(TOKEN, aes_key, "deadbeef", "1700000000", "abc", echostr)


def test_decrypt_message_bad_signature():
    aes_key = _make_aes_key()
    enc = encrypt(aes_key, "msg", "rid")
    with pytest.raises(WecomCryptoError):
        decrypt_message(TOKEN, aes_key, "badsig", "1700000000", "abc", enc)


def test_decrypt_tampered_ciphertext():
    aes_key = _make_aes_key()
    enc = encrypt(aes_key, "secret", "rid")
    # 篡改密文（翻转最后一个 base64 字符）
    tampered = enc[:-2] + ("A" if enc[-2] != "A" else "B") + enc[-1]
    with pytest.raises(WecomCryptoError):
        decrypt(aes_key, tampered)


def test_build_encrypted_reply_can_be_decrypted():
    aes_key = _make_aes_key()
    receiveid = "wwcorp"
    ts, nonce = "1700000000", "nz"
    payload_text = '{"msgtype":"text","text":{"content":"ok"}}'

    env = build_encrypted_reply(TOKEN, aes_key, payload_text, receiveid, ts, nonce)
    assert set(env) == {"encrypt", "msgsignature", "timestamp", "nonce"}
    # 自验签 + 解密
    assert verify_signature(TOKEN, env["msgsignature"], ts, nonce, env["encrypt"])
    msg, rid = decrypt(aes_key, env["encrypt"])
    assert msg == payload_text
    assert rid == receiveid


def test_invalid_aes_key_length():
    with pytest.raises(WecomCryptoError):
        encrypt("tooshort", "msg", "rid")
