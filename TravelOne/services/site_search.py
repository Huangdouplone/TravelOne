# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""Fuzzy search across every tracked attraction and hotel.

- Multi-token fuzzy matching with punctuation/case-insensitive normalisation, so
  partial Chinese or English input works ("北京 希尔顿", "希尔", "Disney").
- Ranks by exact > prefix > substring, then blends cities round-robin so one
  city cannot flood the result list (diversity) while relevance still leads.
- Drops transit duplicates: a metro/railway station that shares a name with a
  real place (and only differs by a missing city) never outranks the place.
- Falls back to a live nationwide Baidu query when the local index has little
  for the term, and merges both sources.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from core import cache_store
from core.geo import haversine_km
from services import live

# Address prefixes that mean "this is a transit stop, not a destination"
_TRANSIT_HINTS = ("地铁", "公交", "轻轨", "有轨电车", "轮渡")


def _norm(text: Any) -> str:
    value = re.sub(r"[（(].*?[)）]", "", str(text or ""))
    value = re.sub(r"[\s\-_·.,，。'\"()（）:：/|+]", "", value.lower())
    return value


def _tokens(query: str) -> List[str]:
    raw = re.split(r"\s+", str(query or "").strip())
    return [t for t in (_norm(x) for x in raw) if t]


def _score(query: str, item: Dict[str, Any], tokens: List[str] = None) -> int:
    name = _norm(item.get("name"))
    if not name or not query:
        return 0
    tokens = tokens or [query]
    if name == query:
        score = 1000
    elif name.startswith(query):
        score = 700
    elif query in name:
        score = 520 - min(180, len(name) - len(query))
    else:
        tags = _norm(" ".join(item.get("tags") or []))
        address = _norm(item.get("address"))
        city = _norm(item.get("city"))
        if query in tags or query in address:
            score = 260
        elif query in city or (len(tokens) == 1 and len(query) >= 2 and city and city in query):
            # 单关键词查询才允许「词里含城市名」（如「北京希尔顿」按整词处理时
            # 不能把北京所有景点都算命中，多词查询走下面的 token 全匹配）。
            score = 180
        elif len(tokens) > 1 and all(t in (name + city) for t in tokens) and any(t in name for t in tokens):
            # 多词查询（"北京 希尔顿"）：每个词都要命中名称或城市，
            # 且至少一个词命中名称，避免"北京路"这类地址巧合把外地酒店带进来。
            score = 430
        else:
            return 0
    # Popular, reviewed places break ties without overwhelming relevance
    score += min(60, int((item.get("review_count") or 0) / 200))
    if item.get("price") is not None:
        score += 5
    return score


def _transit_like(item: Dict[str, Any]) -> bool:
    address = str(item.get("address") or "")
    if any(address.startswith(hint) for hint in _TRANSIT_HINTS):
        return True
    tags = item.get("tags") or []
    return any(t in ("地铁站", "公交站", "轻轨站") for t in tags)


def _diverse(ranked: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """Spread results across cities, but never let a weak match jump a strong one.

    One city may contribute at most `cap` rows while an under-cap city still has
    a result scoring at least 75% of the best remaining row. Relevance therefore
    leads, and diversity only breaks ties — a city-less metro station can no
    longer leapfrog an exact-name match in a busy city.
    """
    remaining = list(ranked)  # already sorted by score, descending
    counts: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    cap = 2
    while remaining and len(out) < limit:
        best = remaining[0]
        pick = best
        if counts.get(str(best.get("city") or ""), 0) >= cap:
            floor = best["_score"] * 0.75
            for candidate in remaining:
                city = str(candidate.get("city") or "")
                if counts.get(city, 0) < cap and candidate["_score"] >= floor:
                    pick = candidate
                    break
        remaining.remove(pick)
        city = str(pick.get("city") or "")
        counts[city] = counts.get(city, 0) + 1
        out.append(pick)
    return out


_score_cache: Dict[int, int] = {}


def search_points(query: str, kind: str = "all", page: int = 1, page_size: int = 24) -> Dict[str, Any]:
    global _score_cache
    q = _norm(query)
    tokens = _tokens(query) or [q]
    kinds = ["attraction", "hotel"] if kind in ("all", "", None) else [kind]
    rows: List[Dict[str, Any]] = []
    for current in kinds:
        rows.extend(cache_store.items(current))

    _score_cache = {}
    scored: List[Dict[str, Any]] = []
    for item in rows:
        score = _score(q, item, tokens)
        if score <= 0:
            continue
        entry = dict(item)
        entry["_score"] = score
        entry["kind"] = entry.get("kind") or ("hotel" if entry.get("star") else "attraction")
        if _transit_like(entry) and not entry.get("star"):
            # Transit stops are useful for orientation, but never as the top hit
            entry["_score"] = min(entry["_score"], 210)
            entry["transit_stop"] = True
        _score_cache[id(entry)] = entry["_score"]
        scored.append(entry)

    # 查询词本身是地名（城市 / 区县）时，即便名字里没有该词，
    # 也要把该地点的条目算进来，并现场补抓一轮城内 POI。
    place_query = False
    try:
        from services import coverage as coverage_mod
        place_query = any(q and (q == _norm(name) or q in _norm(name)) for name in coverage_mod.place_names()[:4000])             and len(q) <= 8
    except Exception:
        place_query = False

    live_used = False
    # Local index is sparse for brand names and small counties: top up from the
    # live source whenever the term is meaningful and results are thin.
    if query.strip() and len(query.strip()) >= 2 and (len(scored) < 12 or place_query):
        from collectors import baidu_web

        term = query.strip()
        for current in kinds:
            try:
                live_rows = baidu_web.search(term, "", current, 0, 20)
            except Exception:
                live_rows = []
            # 「喀什」「澳门」这类地名查询：再按城市限定抓一轮城内 POI。
            # 上游要求「城市 + 通用词」才返回城内结果，因此用该类目的通用词，
            # 再只保留 city 与查询一致的行，避免把无关城市的结果混进来。
            generic = "景点" if current == "attraction" else "酒店"
            try:
                city_rows = baidu_web.search(generic, term, current, 0, 20)
            except Exception:
                city_rows = []
            for row in city_rows:
                city = str(row.get("city") or "")
                if city and (term in city or city in term):
                    live_rows.append(row)
            if live_rows:
                live._finalize(live_rows, current, "")
                for item in live_rows:
                    score = _score(q, item, tokens)
                    if score <= 0:
                        continue
                    live_used = True
                    entry = dict(item)
                    entry["_score"] = score
                    entry["kind"] = current
                    if _transit_like(entry) and current == "attraction":
                        entry["_score"] = min(entry["_score"], 210)
                        entry["transit_stop"] = True
                    _score_cache[id(entry)] = entry["_score"]
                    scored.append(entry)

    # unique by uid/key, keep the best score
    best: Dict[str, Dict[str, Any]] = {}
    for item in scored:
        ident = str(item.get("uid") or item.get("key") or item.get("id") or item.get("name"))
        if ident not in best or item["_score"] > best[ident]["_score"]:
            best[ident] = item
    ranked = list(best.values())

    # A city-less transit stop that duplicates a named place must not outrank it
    by_name: Dict[str, List[Dict[str, Any]]] = {}
    for item in ranked:
        by_name.setdefault(_norm(item.get("name")), []).append(item)
    for group in by_name.values():
        if len(group) < 2:
            continue
        named = [g for g in group if g.get("city") and not g.get("transit_stop")]
        if not named:
            continue
        top = max(named, key=lambda row: row["_score"])
        for item in group:
            if item is top:
                continue
            if item.get("transit_stop") or not item.get("city"):
                item["_score"] = min(item["_score"], top["_score"] - 180)
                _score_cache[id(item)] = item["_score"]

    ranked.sort(key=lambda row: row["_score"], reverse=True)

    cities = len({str(row.get("city") or "") for row in ranked})
    ordered = _diverse(ranked, len(ranked)) if len(ranked) > 1 else ranked
    for row in ordered:
        row.pop("_score", None)
    total = len(ordered)
    start = max(0, (page - 1) * page_size)
    page_rows = ordered[start:start + page_size]
    return {"items": page_rows, "total": total, "page": page, "page_size": page_size,
            "cities": cities, "source": "live" if live_used else "cache",
            "query": query, "tokens": tokens}


def nearby_hotels(anchor: Dict[str, Any], limit: int = 12) -> List[Dict[str, Any]]:
    """Hotels around a landmark/attraction, sorted by straight-line distance."""
    if anchor.get("lat") is None:
        return []
    rows = live.search("hotel", {"city": anchor.get("city") or "", "page": 1,
                                 "page_size": 60}).get("items") or []
    if not rows:
        rows = cache_store.items("hotel")
    out: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("lat") is None:
            continue
        entry = dict(row)
        entry["distance_to_attraction_km"] = round(
            haversine_km(anchor["lat"], anchor["lng"], row["lat"], row["lng"]), 2)
        out.append(entry)
    out.sort(key=lambda row: row["distance_to_attraction_km"])
    return out[:limit]