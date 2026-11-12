# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""去哪儿门票频道（piao.qunar.com）公开检索接口。

一次 GET 返回 15 条同关键词结果，字段包含门票价 `qunarPrice`、平台评分 `score`、
销量 `saleCount`、A 级 `star`、坐标 `point`、简介与图片。免密钥，不需要登录。

上游没有收录该景点时返回空列表；网络失败返回 None，由上层标注“不可用”，
不猜测价格，也不把销量当点评数。
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from core import httpclient
from core.config import settings

BASE = "https://piao.qunar.com/ticket/list.json"
REFERER = "https://piao.qunar.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

SOURCE = {
    "name": "qunar_piao",
    "label": "Qunar tickets (direct)",
    "source_url": "https://piao.qunar.com/",
    "note": "Ticket price, platform score and sales volume read from the public Qunar ticket search; one request returns 15 rows.",
}

_PUNCT = re.compile(r"[\s·•\-—_,，。.、()（）\[\]【】\"'“”‘’/\\|]+")


def _num(value: Any) -> Optional[float]:
    try:
        text = str(value if value is not None else "").strip()
        if not text:
            return None
        number = float(text)
        return number if number > 0 else None
    except Exception:
        return None


def _norm(value: Any) -> str:
    return _PUNCT.sub("", str(value or "")).lower()


def _distance_km(lat1: Any, lng1: Any, lat2: Any, lng2: Any) -> Optional[float]:
    try:
        rlat1, rlng1, rlat2, rlng2 = map(math.radians, (float(lat1), float(lng1), float(lat2), float(lng2)))
        dlat, dlng = rlat2 - rlat1, rlng2 - rlng1
        a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
        return round(2 * 6371 * math.asin(math.sqrt(a)), 2)
    except Exception:
        return None


def search(keyword: str, page: int = 1) -> Optional[List[Dict[str, Any]]]:
    """按关键词取一页结果；上游失败返回 None，正常但无收录返回 []。"""
    keyword = str(keyword or "").strip()
    if not keyword:
        return []
    try:
        resp = httpclient.get(BASE, params={"keyword": keyword, "page": max(1, int(page))},
                              headers={"User-Agent": UA, "Referer": REFERER,
                                       "Accept-Language": "zh-CN,zh;q=0.9"},
                              timeout=max(6, settings.request_timeout + 2))
    except Exception:
        return None
    if resp.status_code >= 400:
        return None
    try:
        payload = resp.json()
    except Exception:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    rows = (data or {}).get("sightList") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def _row(row: Dict[str, Any]) -> Dict[str, Any]:
    point = str(row.get("point") or "").split(",")
    lat = _num(point[1]) if len(point) == 2 else None
    lng = _num(point[0]) if len(point) == 2 else None
    return {
        "sight_id": row.get("sightId"),
        "name": str(row.get("sightName") or "").strip(),
        "price": _num(row.get("qunarPrice")),
        "score": _num(row.get("score")),
        "sales": _num(row.get("saleCount")),
        "star": str(row.get("star") or "").strip(),
        "address": str(row.get("address") or "").strip(),
        "intro": str(row.get("intro") or "").strip(),
        "image": str(row.get("sightImgURL") or "").strip(),
        "district": str(row.get("districts") or "").strip(),
        "free": bool(row.get("free")),
        "lat": lat,
        "lng": lng,
        "url": ("https://piao.qunar.com/ticket/detail_%s.html" % row.get("sightId")
                if row.get("sightId") else BASE),
    }


def lookup(name: str, city: str = "", lat: Any = None, lng: Any = None) -> Optional[Dict[str, Any]]:
    """按「城市 + 名称」检索并挑最可信的一条；无收录返回 None，网络失败返回 None。"""
    name = str(name or "").strip()
    if not name:
        return None
    rows = search(("%s %s" % (city, name)).strip() if city else name)
    if not rows:
        return None
    target = _norm(name)
    best = None
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = _row(raw)
        candidate = _norm(row["name"])
        if not candidate:
            continue
        if candidate == target:
            score = 3
        elif len(target) >= 3 and len(candidate) >= 3 and target in candidate:
            score = 2
        elif len(target) >= 4 and len(candidate) >= 4 and candidate in target:
            score = 1
        else:
            continue
        distance = _distance_km(lat, lng, row["lat"], row["lng"])
        if score < 3 and distance is not None and distance > 3:
            # 同名但不在同一处，放弃
            continue
        rank = (score, -(distance if distance is not None else 0))
        if best is None or rank > best[0]:
            best = (rank, row, distance)
    if not best:
        return None
    _, row, distance = best
    row = dict(row)
    row["distance_km"] = distance
    return row