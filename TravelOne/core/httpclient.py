# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""HTTP 客户端封装：优先使用 requests（有则用，享受连接复用），
缺失时自动降级到标准库 urllib，保证项目在未安装任何第三方包的机器上仍可运行。
"""
from __future__ import annotations

import json as _json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

try:  # pragma: no cover - 环境相关分支
    import requests as _requests
    HAS_REQUESTS = True
except Exception:  # pragma: no cover
    _requests = None
    HAS_REQUESTS = False


class Response:
    """与 requests.Response 常用属性对齐的最小实现。"""

    def __init__(self, status_code: int, content: bytes, headers: Optional[Dict[str, str]] = None,
                 encoding: str = "utf-8") -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.encoding = encoding

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding, "ignore")

    def json(self) -> Any:
        return _json.loads(self.text)


def _urllib_get(url: str, params: Optional[Dict[str, Any]] = None,
                headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Response:
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = url + ("&" if "?" in url else "?") + query
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return Response(resp.status, content, dict(resp.headers), charset)
    except urllib.error.HTTPError as exc:  # 4xx/5xx 也要返回响应体供反爬识别
        content = exc.read()
        return Response(exc.code, content, dict(exc.headers or {}), "utf-8")


def _encoding_of(resp: Any) -> str:
    enc = getattr(resp, "encoding", None) or "utf-8"
    # 百度等站点不带 charset 时 requests 会误判为 ISO-8859-1，导致中文乱码
    if str(enc).lower() in ("iso-8859-1", "latin-1", "ascii"):
        return "utf-8"
    return str(enc)


def get(url: str, params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Response:
    if HAS_REQUESTS:
        resp = _requests.get(url, params=params, headers=headers, timeout=timeout)
        return Response(resp.status_code, resp.content, dict(resp.headers), _encoding_of(resp))
    return _urllib_get(url, params, headers, timeout)


class Session:
    """轻量会话：保存默认请求头，支持少量连接复用。"""

    def __init__(self, headers: Optional[Dict[str, str]] = None) -> None:
        self.headers: Dict[str, str] = dict(headers or {})
        self._session = _requests.Session() if HAS_REQUESTS else None
        if self._session is not None:
            self._session.headers.update(self.headers)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Response:
        merged = dict(self.headers)
        merged.update(headers or {})
        if self._session is not None:
            resp = self._session.get(url, params=params, headers=headers, timeout=timeout)
            return Response(resp.status_code, resp.content, dict(resp.headers), _encoding_of(resp))
        return _urllib_get(url, params, merged, timeout)