"""企业微信回调消息加解密（WXBizMsgCrypt 标准实现）。

适用于「智能机器人 - 设置接收消息回调地址（Webhook 短连接）」模式：
- URL 验证（GET）：校验 msg_signature，解密 echostr 后原样返回明文
- 接收消息（POST）：校验 msg_signature，AES-256-CBC 解密密文
- 回复消息（POST 响应）：加密明文 + 生成 msg_signature

加解密规范（企业微信官方）：
- AES-256-CBC，PKCS#7 填充至 32 byte 倍数
- AESKey = base64decode(EncodingAESKey + "=")，共 32 byte
- IV = AESKey 前 16 byte
- 明文结构：random(16) + msg_len(4, big-endian) + msg + receiveid
- 签名：sha1(sorted([token, timestamp, nonce, encrypt]).join(""))

仅依赖已有的 ``cryptography`` 库，不引入额外依赖。
"""

from __future__ import annotations

import base64
import hashlib
import secrets

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# 企业微信使用 32 byte 块做 PKCS#7 填充（非 AES 默认的 16）
_PKCS7_BLOCK = 32


class WecomCryptoError(Exception):
    """加解密 / 验签失败统一异常。"""


def _aes_key(encoding_aes_key: str) -> bytes:
    """EncodingAESKey(43 位 base64) → 32 byte AESKey。"""
    try:
        key = base64.b64decode(encoding_aes_key + "=")
    except Exception as exc:  # noqa: BLE001
        raise WecomCryptoError(f"EncodingAESKey 解码失败: {exc}") from exc
    if len(key) != 32:
        raise WecomCryptoError(f"AESKey 长度应为 32 byte，实际 {len(key)}")
    return key


def compute_signature(token: str, timestamp: str, nonce: str, encrypt: str) -> str:
    """计算 msg_signature = sha1(字典序排序后拼接)。"""
    items = sorted([token, timestamp, nonce, encrypt])
    return hashlib.sha1("".join(items).encode("utf-8")).hexdigest()  # noqa: S324


def verify_signature(
    token: str, signature: str, timestamp: str, nonce: str, encrypt: str
) -> bool:
    """常量时间比较签名，防止时序侧信道。"""
    expected = compute_signature(token, timestamp, nonce, encrypt)
    return secrets.compare_digest(expected, signature or "")


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise WecomCryptoError("待去填充数据为空")
    pad = data[-1]
    if pad < 1 or pad > _PKCS7_BLOCK or pad > len(data):
        raise WecomCryptoError("PKCS7 填充非法")
    return data[:-pad]


def _pkcs7_pad(data: bytes) -> bytes:
    pad = _PKCS7_BLOCK - (len(data) % _PKCS7_BLOCK)
    if pad == 0:
        pad = _PKCS7_BLOCK
    return data + bytes([pad] * pad)


def decrypt(encoding_aes_key: str, encrypt_b64: str) -> tuple[str, str]:
    """解密密文，返回 (明文消息, receiveid)。

    Raises:
        WecomCryptoError: 解码 / 解密 / 结构异常。
    """
    key = _aes_key(encoding_aes_key)
    iv = key[:16]
    try:
        cipher_bytes = base64.b64decode(encrypt_b64)
    except Exception as exc:  # noqa: BLE001
        raise WecomCryptoError(f"密文 base64 解码失败: {exc}") from exc

    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    try:
        plain = decryptor.update(cipher_bytes) + decryptor.finalize()
    except Exception as exc:  # noqa: BLE001
        raise WecomCryptoError(f"AES 解密失败: {exc}") from exc

    content = _pkcs7_unpad(plain)
    if len(content) < 20:  # 16 随机 + 4 长度
        raise WecomCryptoError("解密内容过短")

    body = content[16:]
    msg_len = int.from_bytes(body[:4], "big")
    if msg_len < 0 or 4 + msg_len > len(body):
        raise WecomCryptoError("消息长度字段非法")

    msg = body[4 : 4 + msg_len].decode("utf-8", errors="strict")
    receiveid = body[4 + msg_len :].decode("utf-8", errors="ignore")
    return msg, receiveid


def encrypt(encoding_aes_key: str, plaintext: str, receiveid: str) -> str:
    """加密明文，返回 base64 密文。"""
    key = _aes_key(encoding_aes_key)
    iv = key[:16]
    msg_bytes = plaintext.encode("utf-8")
    random_16 = secrets.token_bytes(16)
    payload = (
        random_16
        + len(msg_bytes).to_bytes(4, "big")
        + msg_bytes
        + receiveid.encode("utf-8")
    )
    padded = _pkcs7_pad(payload)
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    cipher_bytes = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(cipher_bytes).decode("utf-8")


def verify_url(
    token: str,
    encoding_aes_key: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> str:
    """URL 验证（GET）：校验签名并解密 echostr，返回明文。

    Raises:
        WecomCryptoError: 验签失败或解密失败。
    """
    if not verify_signature(token, msg_signature, timestamp, nonce, echostr):
        raise WecomCryptoError("URL 验证签名校验失败")
    plain, _ = decrypt(encoding_aes_key, echostr)
    return plain


def decrypt_message(
    token: str,
    encoding_aes_key: str,
    msg_signature: str,
    timestamp: str,
    nonce: str,
    encrypt_b64: str,
) -> tuple[str, str]:
    """接收消息（POST）：校验签名并解密，返回 (明文消息, receiveid)。

    Raises:
        WecomCryptoError: 验签失败或解密失败。
    """
    if not verify_signature(token, msg_signature, timestamp, nonce, encrypt_b64):
        raise WecomCryptoError("消息签名校验失败")
    return decrypt(encoding_aes_key, encrypt_b64)


def build_encrypted_reply(
    token: str,
    encoding_aes_key: str,
    plaintext: str,
    receiveid: str,
    timestamp: str,
    nonce: str,
) -> dict[str, str]:
    """构造加密回复包（用于 POST 响应体）。

    Returns:
        {"encrypt", "msgsignature", "timestamp", "nonce"}
    """
    enc = encrypt(encoding_aes_key, plaintext, receiveid)
    sig = compute_signature(token, timestamp, nonce, enc)
    return {
        "encrypt": enc,
        "msgsignature": sig,
        "timestamp": timestamp,
        "nonce": nonce,
    }


__all__ = [
    "WecomCryptoError",
    "compute_signature",
    "verify_signature",
    "decrypt",
    "encrypt",
    "verify_url",
    "decrypt_message",
    "build_encrypted_reply",
]
