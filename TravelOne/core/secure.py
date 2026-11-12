# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""本地密钥与加密工具。

用途：
1. 浏览器 → 本机服务传输 AK 时，用一次性会话密钥加密（SHA-256 计数器流），
   服务端解密后**只以密文形式**写入 data/runtime_config.json；
2. 服务启动时用本地主密钥解密，解密结果只存在于内存，接口不回传明文。

说明：这是本机离线场景下的对称流加密（SHA-256 计数器模式），用于避免明文落盘与明文传输；
它不是对抗本机高权限攻击者的强方案，如果需要更强保护，可替换为系统密钥库 / KMS。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Dict, Optional

KEY_FILE = Path(__file__).resolve().parent.parent / "data" / ".datakey"
SESSION_TTL = 600

_lock = threading.Lock()
_master: Optional[bytes] = None
_sessions: Dict[str, Dict[str, object]] = {}


def master_key() -> bytes:
    """读取或生成 32 字节本地主密钥（仅本机可见，不随项目分发）。"""
    global _master
    if _master is not None:
        return _master
    with _lock:
        if _master is not None:
            return _master
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if KEY_FILE.exists():
            raw = KEY_FILE.read_bytes()
            if len(raw) == 32:
                _master = raw
                return _master
        raw = secrets.token_bytes(32)
        KEY_FILE.write_bytes(raw)
        try:
            os.chmod(KEY_FILE, 0o600)
        except Exception:
            pass
        _master = raw
        return _master


def _keystream(key: bytes, size: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        out.extend(hashlib.sha256(key + counter.to_bytes(4, "big")).digest())
        counter += 1
    return bytes(out[:size])


def xor_stream(data: bytes, key: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, _keystream(key, len(data))))


def encrypt(text: str) -> str:
    if not text:
        return ""
    payload = xor_stream(text.encode("utf-8"), master_key())
    return "v1:" + base64.b64encode(payload).decode("ascii")


def decrypt(token: str) -> str:
    if not token:
        return ""
    if not token.startswith("v1:"):
        return token  # 兼容早期明文配置
    try:
        payload = base64.b64decode(token[3:].encode("ascii"))
        return xor_stream(payload, master_key()).decode("utf-8")
    except Exception:
        return ""


# ------------------------------ 会话密钥 ------------------------------

def new_session() -> Dict[str, str]:
    sid = secrets.token_hex(8)
    key = secrets.token_bytes(32)
    _sessions[sid] = {"key": key, "ts": time.time()}
    _cleanup()
    return {"sid": sid, "key": base64.b64encode(key).decode("ascii")}


def decrypt_payload(sid: str, cipher: str) -> Optional[str]:
    record = _sessions.get(sid)
    if not record or time.time() - float(record["ts"]) > SESSION_TTL:
        return None
    try:
        raw = base64.b64decode(cipher.encode("ascii"))
    except Exception:
        return None
    plain = xor_stream(raw, record["key"])  # type: ignore[arg-type]
    try:
        return plain.decode("utf-8")
    except Exception:
        return None


def drop_session(sid: str) -> None:
    _sessions.pop(sid, None)


def _cleanup() -> None:
    now = time.time()
    for sid in [k for k, v in _sessions.items() if now - float(v["ts"]) > SESSION_TTL]:
        _sessions.pop(sid, None)


def mask(value: str) -> str:
    """给前端展示用的掩码（不暴露明文，仅显示长度与尾号提示）。"""
    if not value:
        return ""
    tail = value[-4:] if len(value) > 12 else ""
    return "•" * min(12, max(6, len(value) - 4)) + (tail if tail else "")