# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""门票价格与评分的第二来源：去哪儿门票频道直连。

作用有三件，且都只做“如实标注”的事：
1. 给景点详情补一条独立报价（平台显示为 Qunar direct），参与最低价与价差计算；
2. 百度侧没有票价或评分的景点，用去哪儿的值补上，并标明来源；
3. 两个评分来源同时存在时都保留，前端分开展示，不合并、不平均。

缓存落在 data/cache/qunar_tickets.json，单文件、键为景点 key、TTL 6 小时；
上游没收录的景点也记成“空结果”，避免每次打开详情都重复请求。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from collectors import qunar_piao
from core import cache_store

CACHE_FILE: Path = cache_store.CACHE_DIR / "qunar_tickets.json"
TTL_SECONDS = 6 * 3600
MAX_ENTRIES = 4000
_SAVE_INTERVAL = 60

_STATE: Dict[str, Any] = {"data": None, "saved_at": 0.0, "hits": 0, "misses": 0}


def _load() -> Dict[str, Any]:
    if _STATE["data"] is not None:
        return _STATE["data"]
    data: Dict[str, Any] = {}
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict):
            data = payload.get("items") if isinstance(payload.get("items"), dict) else {}
    except Exception:
        data = {}
    _STATE["data"] = data
    return data


def _save(force: bool = False) -> None:
    now = time.time()
    if not force and now - float(_STATE["saved_at"] or 0) < _SAVE_INTERVAL:
        return
    _STATE["saved_at"] = now
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        items = _load()
        if len(items) > MAX_ENTRIES:
            keep = sorted(items.items(), key=lambda kv: float(kv[1].get("fetched_at") or 0), reverse=True)
            items = dict(keep[:MAX_ENTRIES])
            _STATE["data"] = items
        with CACHE_FILE.open("w", encoding="utf-8") as handle:
            json.dump({"fetched_at": int(now), "source": qunar_piao.SOURCE, "items": items},
                      handle, ensure_ascii=False)
    except Exception:
        pass


def _key(item: Dict[str, Any]) -> str:
    key = str(item.get("key") or "").strip()
    if key:
        return key
    return "%s::%s" % (item.get("city") or "", item.get("name") or "")


def quote(item: Dict[str, Any], force: bool = False) -> Optional[Dict[str, Any]]:
    """取该景点的去哪儿报价；命中缓存直接返回，空结果也缓存。"""
    if not isinstance(item, dict):
        return None
    key = _key(item)
    if not key or key.endswith("::"):
        return None
    store = _load()
    entry = store.get(key)
    now = int(time.time())
    if entry and not force and now - int(entry.get("fetched_at") or 0) < TTL_SECONDS:
        return entry.get("quote") or None

    found = qunar_piao.lookup(item.get("name") or "", item.get("city") or "",
                              item.get("lat"), item.get("lng"))
    if found is None and entry is not None:
        # 上游这次不可用：沿用上一份报价，不让详情页因网络抖动丢数据
        return entry.get("quote") or None
    store[key] = {"fetched_at": now, "quote": found}
    if found:
        _STATE["hits"] = int(_STATE["hits"]) + 1
    else:
        _STATE["misses"] = int(_STATE["misses"]) + 1
    _save()
    return found


def _offer(quote_row: Dict[str, Any], stamp: str) -> Dict[str, Any]:
    return {
        "platform": "Qunar (direct)",
        "platform_zh": "去哪儿（直连）",
        "code": "qunar_piao",
        "price": float(quote_row["price"]),
        "original_price": None,
        "note": "Ticket price from the Qunar ticket channel",
        "note_zh": "去哪儿门票频道挂牌价",
        "is_reference": False,
        "live": True,
        "updated_at": stamp,
        "specs": [],
        "spec_label": "Ticket type",
        "spec_label_zh": "票种",
    }


def attach(detail: Dict[str, Any]) -> Dict[str, Any]:
    """把去哪儿报价/评分挂到景点详情上；无收录则原样返回。"""
    if not isinstance(detail, dict) or detail.get("kind") not in (None, "attraction"):
        return detail
    row = quote(detail)
    if not row:
        return detail
    enriched = dict(detail)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    price = row.get("price")
    score = row.get("score")

    offers = [o for o in (enriched.get("offers") or []) if isinstance(o, dict)]
    base = enriched.get("price")
    base_price = None if base in (None, "") else float(base)
    free_by_base = base_price == 0
    base_unknown = base_price is None
    # 去哪儿门票频道对免费场馆常给出讲解/研学套餐价（实测有 550 元、477 元），
    # 所以只在“百度有价且量级接近”或“百度缺价且去哪儿标了 A 级、价格合理”时才作为报价展示。
    plausible = False
    if price:
        if base_price and base_price > 0:
            ratio = price / base_price
            plausible = 0.25 <= ratio <= 4
        elif base_unknown:
            plausible = bool(row.get("star")) and price <= 400
    if plausible and not free_by_base:
        if not any(str(o.get("platform") or "") == "Qunar (direct)" for o in offers):
            offers.append(_offer(row, stamp))
            enriched["offers"] = offers
        if base_unknown:
            enriched["price"] = float(price)
            enriched["price_source"] = "Qunar (direct)"
            enriched["price_note"] = "Ticket price from the Qunar ticket channel"
            enriched["price_updated_at"] = stamp

    ratings = []
    base = enriched.get("rating")
    if base not in (None, ""):
        ratings.append({"source": "Baidu Maps", "source_zh": "百度地图",
                        "value": float(base), "count": int(enriched.get("review_count") or 0)})
    if score:
        ratings.append({"source": "Qunar (direct)", "source_zh": "去哪儿（直连）",
                        "value": float(score), "count": 0})
    if ratings:
        enriched["ratings"] = ratings

    enriched["ticket_quote"] = {
        "source": qunar_piao.SOURCE["name"],
        "label": qunar_piao.SOURCE["label"],
        "source_url": qunar_piao.SOURCE["source_url"],
        "price": price,
        "score": score,
        "sales": row.get("sales"),
        "star": row.get("star"),
        "matched_name": row.get("name"),
        "distance_km": row.get("distance_km"),
        "url": row.get("url"),
        "fetched_at": stamp,
    }
    return enriched


def summary() -> Dict[str, Any]:
    store = _load()
    priced = 0
    scored = 0
    latest = 0
    for entry in store.values():
        row = (entry or {}).get("quote") or {}
        if row.get("price"):
            priced += 1
        if row.get("score"):
            scored += 1
        latest = max(latest, int((entry or {}).get("fetched_at") or 0))
    return {
        "name": qunar_piao.SOURCE["name"],
        "label": qunar_piao.SOURCE["label"],
        "source_url": qunar_piao.SOURCE["source_url"],
        "note": qunar_piao.SOURCE["note"],
        "status": "live",
        "needs_key": False,
        "cached": len(store),
        "with_price": priced,
        "with_score": scored,
        "fetched_at": (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(latest)) if latest else ""),
    }