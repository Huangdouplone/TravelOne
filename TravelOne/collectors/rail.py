# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""12306 公开时刻表文件解析：给出真实车次与起讫站，票价仍不可匿名获取。

数据来自 12306 自己发布的静态文件：
- otn/resources/js/framework/station_name.js  车站名与电报码
- otn/resources/js/query/train_list.js        车次号与起讫站（约 13MB，缓存 6 小时）

只解析，不做签名、不伪造字段。余票接口目前返回加密载荷，票价仍按公开运价估算。
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional

from core import httpclient

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
STATION_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
TRAIN_URL = "https://kyfw.12306.cn/otn/resources/js/query/train_list.js"
TTL = 6 * 3600

_lock = threading.Lock()
_cache: Dict[str, Any] = {"stations_at": 0.0, "stations": {}, "trains_at": 0.0, "trains": []}


def _get(url: str, timeout: int = 40) -> str:
    try:
        resp = httpclient.get(url, headers={"User-Agent": UA, "Referer": "https://kyfw.12306.cn/otn/leftTicket/init"},
                              timeout=timeout)
        return resp.text if resp.status_code < 400 else ""
    except Exception:
        return ""


def _stations() -> Dict[str, str]:
    now = time.time()
    with _lock:
        if _cache["stations"] and now - _cache["stations_at"] < 24 * 3600:
            return _cache["stations"]
    text = _get(STATION_URL, timeout=25)
    mapping: Dict[str, str] = {}
    for entry in str(text or "").split("@"):
        parts = entry.split("|")
        if len(parts) < 3:
            continue
        name, code = parts[1].strip(), parts[2].strip()
        if name and re.fullmatch(r"[A-Z]+", code):
            mapping.setdefault(name, code)
    if mapping:
        with _lock:
            _cache["stations"] = mapping
            _cache["stations_at"] = now
    return mapping


def _trains() -> List[Dict[str, str]]:
    now = time.time()
    with _lock:
        if _cache["trains"] and now - _cache["trains_at"] < TTL:
            return _cache["trains"]
    text = _get(TRAIN_URL, timeout=60)
    if not text:
        return []
    body = text[text.find("{"):]
    try:
        raw = json.loads(body)
    except Exception:
        return []
    rows: List[Dict[str, str]] = []
    for _date, groups in (raw or {}).items():
        if not isinstance(groups, dict):
            continue
        for kind, items in groups.items():
            for item in items or []:
                code = str(item.get("station_train_code") or "")
                if not code:
                    continue
                match = re.match(r"([A-Z]+)(\d+)\((.+?)-(.+?)\)", code)
                if not match:
                    continue
                rows.append({"kind": kind, "code": match.group(1) + match.group(2),
                             "train_no": str(item.get("train_no") or ""),
                             "from": match.group(3), "to": match.group(4)})
        break  # 文件只保留一个日期的快照，取第一组即可
    if rows:
        with _lock:
            _cache["trains"] = rows
            _cache["trains_at"] = now
    return rows


def _city_terms(city: str) -> List[str]:
    base = str(city or "").strip()
    for suffix in ("市", "地区", "自治州", "盟"):
        if base.endswith(suffix) and len(base) > len(suffix) + 1:
            base = base[: -len(suffix)]
            break
    return [base] if base else []


def corridor(city_from: str, city_to: str, limit: int = 24) -> List[Dict[str, str]]:
    """返回经过这两座城市的真实车次（按车次号排序）。"""
    a, b = _city_terms(city_from), _city_terms(city_to)
    if not a or not b:
        return []
    out: List[Dict[str, str]] = []
    seen = set()
    for row in _trains():
        frm, to = row.get("from") or "", row.get("to") or ""
        if not frm or not to:
            continue
        if not any(t in frm for t in a) or not any(t in to for t in b):
            continue
        code = row.get("code")
        if code in seen:
            continue
        seen.add(code)
        out.append(dict(row))
        if len(out) >= limit:
            break
    out.sort(key=lambda r: (r.get("kind") != "G", r.get("code") or ""))
    return out[:limit]


def station_code(name: str) -> Optional[str]:
    return _stations().get(str(name or "").strip())