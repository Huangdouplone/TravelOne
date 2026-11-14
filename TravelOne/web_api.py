# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""HTTP API：纯实时抓取 + JSON 快照，无任何数据库依赖。"""
from __future__ import annotations

import json
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

from core import cache_store, i18n, runs, secure, trips
from core.cities import CITIES
from core.config import save_runtime_config, settings
from core.geo import haversine_km
from services import (baidu, coverage, covers, harvest, intl, live, platforms, reference, routing,
                      site_search, templates, ticket_quotes, transport, warmup,
                      intl_warmup)

Response = Tuple[int, Dict[str, str], bytes]

# 初始策展标签（当数据里还没有足够标签时兜底）
SEED_TAGS = ["历史古迹", "博物馆", "免费", "亲子", "夜景", "自然", "古镇", "乐园", "公园", "美食", "演出", "海滨"]
LEVELS = ["5A", "4A", "3A", "2A"]

# 上游标签里混入的行政/商业机构名，不作为旅行主题展示
SKIP_TAGS = {
    "公司", "行政机关", "林业和草原局", "乡镇", "景点附属设施", "门", "村庄",
    "事业单位", "政府机构", "社会团体", "其他", "地名", "道路", "路口",
}
_TAG_CACHE = {"at": 0.0, "value": [], "en": {}}


def dynamic_tags(limit: int = 28) -> List[str]:
    """从已抓取数据里按出现频次汇总旅行主题标签（带缓存，60 秒刷新一次）。

    只保留能映射到英文的主题词，避免语言切换后出现中文标签；
    数据样本不足时回落到策展标签。
    """
    import time as _t

    now = _t.time()
    if now - _TAG_CACHE["at"] < 60 and _TAG_CACHE["value"]:
        return _TAG_CACHE["value"]
    counts: Dict[str, int] = {}
    try:
        rows = cache_store.items("attraction")
    except Exception:
        rows = []
    for row in rows:
        for tag in row.get("tags") or []:
            text = str(tag or "").strip()
            if not text or text in SKIP_TAGS or len(text) > 8:
                continue
            if i18n.tag(text) == text:
                continue  # 无英文映射的主题词不展示，保证中英文一致
            counts[text] = counts.get(text, 0) + 1
    ranked = [tag for tag, hits in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
              if hits >= 6]
    tags, seen = [], set()
    for tag in SEED_TAGS + ranked:
        if tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
        if len(tags) >= limit:
            break
    _TAG_CACHE.update({"at": now, "value": tags, "en": {tag: i18n.tag(tag) for tag in tags}})
    return tags


TAGS = SEED_TAGS


def _json(payload: Any, status: int = 200) -> Response:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    return status, {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"}, body


def _str(q: Dict[str, List[str]], key: str, default: str = "") -> str:
    return q.get(key, [default])[0].strip()


def _int(q: Dict[str, List[str]], key: str, default: int) -> int:
    try:
        return int(q.get(key, [str(default)])[0])
    except (TypeError, ValueError):
        return default


def _float(q: Dict[str, List[str]], key: str, default: Optional[float] = None) -> Optional[float]:
    raw = q.get(key, [""])[0]
    if raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _tags(q: Dict[str, List[str]]) -> List[str]:
    return [t.strip() for t in q.get("tags", [""])[0].split(",") if t.strip()]


def cover_url(name: str, city: str, variant: int = 0) -> str:
    return f"/api/cover?name={quote(name)}&city={quote(city or '')}&v={variant}"


def _normalize_offers(item: Dict[str, Any]) -> None:
    """Translate channel names to English, but keep the Chinese originals.

    Older snapshots only carry Chinese labels, so the English display value is
    derived first and the Chinese one is preserved for the zh UI.
    """
    for offer in item.get("offers") or []:
        if not isinstance(offer, dict):
            continue
        raw_platform = str(offer.get("platform") or "")
        offer.setdefault("platform_zh", i18n.source_zh(raw_platform) or raw_platform)
        offer["platform"] = i18n.source(raw_platform)
        if offer.get("note"):
            raw_note = str(offer.get("note_zh") or offer.get("note") or "")
            if not offer.get("note_zh"):
                # 旧快照只有英文房型说明，尽量还原中文
                offer["note_zh"] = i18n.room_text_zh(raw_note)
            offer["note"] = i18n.note_en(i18n.source(raw_note))
        if offer.get("spec_label"):
            offer["spec_label"] = i18n.note_en(offer["spec_label"])
        for spec in offer.get("specs") or []:
            if not isinstance(spec, dict):
                continue
            raw_name = str(spec.get("name_zh") or spec.get("name") or "")
            spec["name_zh"] = raw_name
            spec["name"] = i18n.note_en(raw_name)
            if not spec.get("note_zh"):
                spec["note_zh"] = i18n.room_text_zh(spec.get("note") or "")
            spec["note"] = i18n.note_en(spec.get("note") or spec.get("note_zh") or "")


def _decorate(items: List[Dict[str, Any]], kind: str) -> None:
    """Fill template fields and add English display names for UI chrome."""
    for item in items:
        _normalize_offers(item)
        item["city_en"] = i18n.city(item.get("city") or "")
        item["tags_en"] = i18n.tags(item.get("tags") or [])
        item["level_en"] = item.get("level") or ""
        if kind == "hotel":
            item["star_label_en"] = i18n.hotel_level(item.get("star_label") or "")
            item["price_source_en"] = i18n.source(item.get("price_source") or "")
            item["price_source_zh"] = i18n.source_zh(item.get("price_source_en") or "") or item.get("price_source") or ""
        else:
            item["price_source_en"] = i18n.source(item.get("price_source") or "")
            item["price_source_zh"] = i18n.source_zh(item["price_source_en"]) or item.get("price_source") or ""
        if not item.get("cover_image"):
            item["cover_image"] = cover_url(item.get("name") or "Place", item.get("city") or "",
                                            5 if kind == "hotel" else 0)
        item.setdefault("gallery", item.get("photos") or [item["cover_image"]])
        item.setdefault("price_stats", templates.price_stats(item.get("offers") or [], item.get("price")))


# ------------------------------ 基础 ------------------------------

def _platform_ratings(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for offer in item.get("offers") or []:
        label = str(offer.get("platform") or "")
        if "Qunar" in label:
            rows.append({"platform": "Qunar", "platform_zh": "去哪儿", "price": offer.get("price"),
                         "rating": None, "reviews": None, "status": "live-price",
                         "url": ""})
    try:
        ctrip = platforms.ctrip_rating(str(item.get("name") or ""), str(item.get("city") or ""))
    except Exception:
        ctrip = None
    if ctrip:
        rows.append({"platform": "Ctrip",
                     "price": None,
                     "rating": ctrip.get("score"),
                     "reviews": ctrip.get("reviews"),
                     "status": "live-rating",
                     "url": ctrip.get("url") or "",
                     "match": ctrip.get("match")})
    return rows


def api_platforms(query: Dict[str, List[str]]) -> Response:
    return _json({"ok": True, "platforms": platforms.status(),
                  "notes": "Prices are only shown when a platform actually returns one; "
                           "Ctrip ratings come from public SEO content."})


def api_health(query: Dict[str, List[str]]) -> Response:
    stats = live.stats()
    return _json({
        "ok": True, "service": "TravelOne", "version": "4.0",
        "mode": "pure-crawl", "storage": "json-snapshot", "database": False,
        "cache": stats,
        "live_enabled": settings.live_enabled,
        "map": {"browser_ak_configured": settings.map_enabled,
                "server_ak_configured": settings.server_route_enabled},
    })


def _mode(query: Dict[str, List[str]]) -> str:
    """国内版 cn / 国际版 global；默认国内。"""
    return "global" if _str(query, "mode") == "global" else "cn"


def api_meta(query: Dict[str, List[str]]) -> Response:
    """Fast metadata: registry counters only, no nationwide snapshot merging."""
    if _mode(query) == "global":
        return _json(intl.meta())
    cover = coverage.summary()
    counts_by_city: Dict[str, int] = {}
    hotels_by_city: Dict[str, int] = {}
    def _label(name: str) -> str:
        text = str(name or "").strip()
        for suffix in ("市", "地区", "自治州", "盟"):
            if text.endswith(suffix) and len(text) > 2:
                return text[: -len(suffix)]
        return text

    merged: Dict[str, Dict[str, Any]] = {}

    def _add(raw_name: str, count: int, hotels: int, code: str = "") -> None:
        label = _label(raw_name)
        if not label:
            return
        key = i18n.city(label)
        if key == label:
            # 未收录英文名的点位不放进语言切换列表，避免界面出现中文城市名
            return
        entry = merged.setdefault(key, {"city": label, "count": 0, "hotels": 0, "code": code})
        entry["count"] = max(int(entry["count"]), int(count or 0))
        entry["hotels"] = max(int(entry["hotels"]), int(hotels or 0))
        if code and not entry["code"]:
            entry["code"] = code

    for item in coverage.top_places(140):
        _add(str(item.get("city") or ""), int(item.get("count") or 0),
             int(item.get("hotels") or 0), str(item.get("code") or ""))
    for city, count in counts_by_city.items():
        _add(city, count, hotels_by_city.get(city, 0))
    for city in settings.collect_cities:
        _add(city, counts_by_city.get(city, 0), hotels_by_city.get(city, 0))
    ordered = list(merged.values())
    ordered.sort(key=lambda row: row["count"] + row["hotels"], reverse=True)
    stats = live.stats()
    by_kind = stats.get("by_kind") or {}
    tracked = cover.get("tracked", {})
    # 快照里已有的条数优先：启动预热写盘后首页统计立即反映，不必等覆盖轮扫
    tags_now = dynamic_tags()
    return _json({
        "cities": [dict(row, city_en=i18n.city(row.get("city") or "")) for row in ordered],
        "tags": tags_now, "tag_en": {tag: i18n.tag(tag) for tag in tags_now},
        "levels": LEVELS,
        "counts": {"attractions": max(int(tracked.get("attractions", 0)), int(by_kind.get("attraction", 0))),
                   "hotels": max(int(tracked.get("hotels", 0)), int(by_kind.get("hotel", 0))),
                   "metros": tracked.get("metros", 0),
                   "cities": cover.get("places_scanned", 0)},
        "cache": stats,
        "storage": "json-snapshot",
        "database": False,
        "providers": [],
        "coverage": cover,
        "map": {"enabled": settings.map_enabled, "server_enabled": settings.server_route_enabled},
        "platforms": platforms.status(),
        "interval_seconds": settings.collect_interval_seconds,
        "recent_runs": runs.latest(6),
        "collect_cities": settings.collect_cities,
    })


def api_config(query: Dict[str, List[str]]) -> Response:
    return _json({
        "baidu_js_ak": settings.baidu_js_ak,
        "ak_masked": secure.mask(settings.baidu_js_ak),
        "ak_configured": bool(settings.baidu_js_ak),
        "server_ak_configured": settings.server_route_enabled,
        "map_enabled": settings.map_enabled,
        "coord_type": "gcj02",
        "live_enabled": settings.live_enabled,
        "storage": "json-snapshot",
    })


def api_config_update(body: Dict[str, Any]) -> Response:
    payload: Dict[str, Any] = {}
    sid, cipher = body.get("sid"), body.get("cipher")
    if sid and cipher:
        plain = secure.decrypt_payload(str(sid), str(cipher))
        secure.drop_session(str(sid))
        if plain is None:
            return _json({"ok": False, "message": "The secure session expired. Reopen the configuration dialog."}, 400)
        try:
            decrypted = json.loads(plain)
        except Exception:
            return _json({"ok": False, "message": "Could not decode the encrypted payload."}, 400)
        payload = {k: v for k, v in decrypted.items() if k in ("baidu_js_ak", "baidu_server_ak")}
    else:
        payload = {k: v for k, v in body.items() if k in ("baidu_js_ak", "baidu_server_ak")}
    if not payload:
        return _json({"ok": False, "message": "Nothing to save."}, 400)
    result = save_runtime_config(payload)
    return _json({"ok": True, "message": "Saved and applied", **result})


def api_crypto_session(query: Dict[str, List[str]]) -> Response:
    return _json(secure.new_session())


def api_cover(query: Dict[str, List[str]]) -> Response:
    svg = covers.make_cover(_str(query, "name", "Place"), _int(query, "v", 0), subtitle=_str(query, "city", ""))
    return 200, {"Content-Type": "image/svg+xml; charset=utf-8", "Cache-Control": "public, max-age=86400"}, svg.encode("utf-8")


# ------------------------------ 数据源与教学 ------------------------------

def api_sources(query: Dict[str, List[str]]) -> Response:
    if _mode(query) == "global":
        stat = intl.stats()
        return _json({
            "mode": "global",
            "builtin": {
                "name": "international", "label": "国际版 · Wikidata",
                "kind": "attraction+hotel+metro", "needs_key": False, "status": "ok",
                "note": "地点、坐标与类别来自 Wikidata（CC0）；底图瓦片为 © OpenStreetMap contributors。价格与评分通常为空。",
                "cache": {"snapshots": stat["cities"], "by_kind": stat["by_kind"]},
                "coverage": {"tracked": {"attractions": stat["by_kind"].get("attraction", 0),
                                          "hotels": stat["by_kind"].get("hotel", 0)},
                             "places_discovered": stat["cities"], "places_scanned": stat["cities"]},
            },
            "transport": {"fuel": {"status": "not_connected"},
                          "rail": {"status": "not_connected"}},
            "warmup": intl_warmup.state(),
            "storage": {"type": "json-snapshot", "database": False,
                        "path": "data/cache/snap_<kind>_intl::<city>.json"},
            "license": "Data: Wikidata (CC0) · Basemap tiles: © OpenStreetMap contributors",
        })
    stats = live.stats()
    runs_list = runs.latest(6)
    return _json({
        "builtin": {
            "name": "baidu_web",
            "label": "Baidu Maps web search (built-in)",
            "kind": "attraction+hotel+metro",
            "needs_key": False,
            "fields": ["Name", "Address", "Coordinates", "Rating", "Review count", "Photos",
                       "Opening hours", "Ticket price (online / list)", "Live hotel rates and room types"],
            "source_url": "https://map.baidu.com/",
            "interval_seconds": settings.collect_interval_seconds,
            "cities": settings.collect_cities,
            "cache": stats,
            "runs": runs_list,
            "status": "ok" if stats.get("snapshots") else "warming",
            "note": "Built in. No keys, crawlers, or configuration required: administrative areas are discovered at runtime and continuously re-scanned nationwide.",
            "coverage": coverage.summary(),
        },
        "optional": [
            {"name": "baidu_js_ak", "label": "Baidu Maps JS API (real basemap / geolocation)",
             "configured": settings.map_enabled, "usage": "Map rendering and browser geolocation",
             "guide": "/api/map/guide"},
            {"name": "baidu_server_ak", "label": "Baidu Maps Web Service AK (routing / geocoding)",
             "configured": settings.server_route_enabled, "usage": "Driving, walking and cycling routes plus address lookup",
             "guide": "/api/map/guide"},
        ],
        "transport": {
            "fuel": {"name": "icauto.com.cn", "label": "Fuel price table (national)",
                     "status": "live", "needs_key": False,
                     "note": "Provincial pump prices for 90#/92#/95#/97# petrol and 0# diesel, fetched live and cached for six hours."},
            "rail": {"name": "12306", "label": "China Railway timetable",
                     "status": "timetable", "needs_key": False,
                     "note": "Train numbers and origin/destination come from the public 12306 timetable files, so a corridor shows its real trains. The ticket API itself returns an encrypted payload, so fares are estimated from the published tariff and labelled as such."},
            "flight": {"name": "Ctrip / Qunar flight lists", "label": "Flight schedules and fares",
                       "status": "signed", "needs_key": False,
                       "note": "Both endpoints require a signed client session. No anonymous fare feed is used, so time and price ranges are labelled as estimates instead of being passed off as live quotes."},
            "booking": {"supported": False,
                        "note": "TravelOne has no booking or payment channel; it only compares published prices and travel time."},
        },
        "warmup": warmup.state(),
        "tickets": ticket_quotes.summary(),
        "reference": {
            "wikidata": reference.summary(),
            "note": "Official label layer only: China's World Heritage sites with Chinese and English names and coordinates. It carries no prices, ratings or photos, so it never overrides the live source.",
        },
        "storage": {"type": "json-snapshot", "database": False,
                    "path": "data/cache/snap_<kind>_<city>.json",
                    "policy": "Keeps only the newest snapshot per kind and area; older copies and unreferenced images are deleted automatically. No bundled datasets."},
    })


MAP_GUIDE = {
    "title": "Baidu Maps AK: real basemap and real routes",
    "intro": "No AK? Everything still works: lists, price comparison, the offline schematic map, "
             "nearest-first sorting and locally estimated routes. With an AK, the map switches to the "
             "real basemap, browser geolocation becomes available, and routes are computed live by Baidu.",
    "links": [
        {"label": "Baidu LBS Open Platform", "url": "https://lbsyun.baidu.com/"},
        {"label": "Console · My Apps", "url": "https://lbsyun.baidu.com/apiconsole/key"},
        {"label": "JavaScript API docs", "url": "https://lbsyun.baidu.com/index.php?title=jspopularGL"},
    ],
    "steps": [
        {"title": "Register and verify", "detail": "Open lbsyun.baidu.com and sign up with a phone number. Individual developers must complete identity verification, otherwise calls are limited."},
        {"title": "Create a browser-side app", "detail": "Console → App Management → My Apps → Create App. Choose the Browser type and enable JavaScript API."},
        {"title": "Set the Referer whitelist", "detail": "For local demos use * (or add 127.0.0.1 and localhost as well). For production, replace it with your domain, e.g. https://your.site/*."},
        {"title": "Copy the AK", "detail": "After saving, the list shows a 24-character AK. That is the Browser-side AK to paste below."},
        {"title": "(Optional) create a server-side app", "detail": "For real driving/transit routes and address lookup, create a second app of type Server with IP whitelist 127.0.0.1 for local use, then paste its AK into Server AK."},
        {"title": "Paste, save, verify", "detail": "Paste the AK into the map configuration (the field accepts paste only), save, then reload the page. The map header shows Baidu Maps when it is active."},
    ],
    "errors": [
        {"code": "APP service disabled", "reason": "JavaScript API was not enabled when the app was created", "fix": "Edit the app, enable JavaScript API, save again"},
        {"code": "AK does not exist / INVALID_USER_SCODE", "reason": "The AK was copied incompletely or has been deleted", "fix": "Copy it again from the console without spaces"},
        {"code": "Referer whitelist validation failed", "reason": "The whitelist does not include the current origin", "fix": "Use * for the browser app, or add 127.0.0.1"},
        {"code": "Permission denied", "reason": "A browser AK was used against a server-side endpoint", "fix": "Create a separate server-side AK for server endpoints"},
        {"code": "Quota exceeded", "reason": "The daily free quota is used up", "fix": "It resets the next day, or raise the quota in the console"},
    ],
    "verification": [
        "After saving, click Test AK: it loads the Baidu Maps JS API once and reports success or the exact error code.",
        "The map panel header changes to Baidu Maps and real roads/place labels appear when the browser AK works.",
        "Generate a route in Trip & Route: if each leg is labelled Live Baidu route, the server AK is active.",
    ],
    "notes": [
        "Both AKs can be the same app if it enables JavaScript API and Web Service API together, or two separate apps for cleaner permissions.",
        "AKs are stored only on this machine in data/runtime_config.json, encrypted at rest. Delete that file to revoke the local configuration.",
    ],
}


def api_map_guide(query: Dict[str, List[str]]) -> Response:
    return _json(MAP_GUIDE)


# ------------------------------ 实时源状态 ------------------------------

def api_live_health(query: Dict[str, List[str]]) -> Response:
    result = live.health()
    return _json({"ok": result.get("ok", False), **result})


def api_live_cache(query: Dict[str, List[str]]) -> Response:
    op = _str(query, "op")
    if op == "clear":
        removed = cache_store.clear(_str(query, "kind"))
        images = live.prune_images()
        runs.add({"type": "cache-clear", "removed": removed, "trigger": "manual"})
        return _json({"ok": True, "removed": removed, "images_removed": images.get("removed", 0),
                      "cache": live.stats()})
    if op == "prune":
        pruned = cache_store.prune(force=True)
        images = live.prune_images()
        return _json({"ok": True, **pruned, "images_removed": images.get("removed", 0),
                      "cache": live.stats()})
    return _json({"ok": True, "cache": live.stats()})


# ------------------------------ 列表与详情 ------------------------------

def api_search(query: Dict[str, List[str]]) -> Response:
    term = (_str(query, "q") or _str(query, "keyword")).strip()
    if not term:
        return _json({"ok": False, "message": "Enter an attraction, hotel or landmark name."}, 400)
    kind = _str(query, "kind", "all")
    if kind not in ("all", "attraction", "hotel"):
        kind = "all"
    if _mode(query) == "global":
        page, size = _int(query, "page", 1), min(48, _int(query, "page_size", 20))
        items = []
        for one in (("attraction", "hotel") if kind == "all" else (kind,)):
            got = intl.search(one, {"keyword": term, "page": 1, "page_size": 48}).get("items") or []
            items.extend(dict(row, kind=one) for row in got)
        total = len(items)
        start = (page - 1) * size
        payload = {"ok": True, "items": items[start:start + size], "total": total,
                   "page": page, "page_size": size, "source": "global",
                   "summary": {"attractions": sum(1 for i in items if i["kind"] == "attraction"),
                               "hotels": sum(1 for i in items if i["kind"] == "hotel")},
                   "cities": len({i.get("city") for i in items})}
        return _json(payload)
    result = site_search.search_points(term, kind, _int(query, "page", 1),
                                       min(48, _int(query, "page_size", 20)))
    _decorate(result["items"], "hotel" if kind == "hotel" else "attraction")
    for item in result["items"]:
        item["kind"] = item.get("kind") or ("hotel" if item.get("star") else "attraction")
        if item["kind"] == "hotel":
            item["star_label_en"] = i18n.hotel_level(item.get("star_label") or "")
            item["price_source_en"] = i18n.source(item.get("price_source") or "")
    result["ok"] = True
    return _json(result)


def api_attractions(query: Dict[str, List[str]]) -> Response:
    if _mode(query) == "global":
        result = intl.search("attraction", {
            "keyword": _str(query, "keyword"), "city": _str(query, "city"),
            "min_rating": _float(query, "min_rating", 0.0) or 0.0,
            "lat": _float(query, "lat"), "lng": _float(query, "lng"),
            "page": _int(query, "page", 1), "page_size": _int(query, "page_size", 12),
        })
        _decorate(result["items"], "attraction")
        return _json(result)
    result = live.search("attraction", {
        "keyword": _str(query, "keyword"), "city": _str(query, "city"),
        "min_rating": _float(query, "min_rating", 0.0) or 0.0,
        "min_price": _float(query, "min_price"), "max_price": _float(query, "max_price"),
        "tags": _tags(query), "level": _str(query, "level"),
        "free": _str(query, "free"),
        "lat": _float(query, "lat"), "lng": _float(query, "lng"),
        "max_distance": _float(query, "max_distance"),
        "sort": _str(query, "sort", "recommend"),
        "page": _int(query, "page", 1), "page_size": _int(query, "page_size", 12),
    })
    _decorate(result["items"], "attraction")
    return _json(result)


def api_attraction_detail(key: str, mode: str = "cn") -> Response:
    if mode == "global":
        detail = intl.detail("attraction", key)
        if not detail:
            return _json({"ok": False, "message": "该城市尚未收录或快照为空，请先在国际版检索一次。"}, 404)
        return _json(templates.attraction_detail(detail))
    detail = live.detail("attraction", key)
    if detail:
        _normalize_offers(detail)
    if not detail:
        return _json({"ok": False, "message": "No live match for this attraction and no cached snapshot for the area."}, 404)
    if not detail.get("gallery"):
        detail["gallery"] = detail.get("photos") or [detail.get("cover_image") or cover_url(detail["name"], detail.get("city") or "")]
    detail = reference.enrich(detail)
    detail = ticket_quotes.attach(detail)
    return _json(templates.attraction_detail(detail))


def api_reference(query: Dict[str, List[str]]) -> Response:
    """官方参考层：目前只有 Wikidata 的中国世界遗产名录（CC0）。"""
    if _str(query, "refresh") in ("1", "true", "yes"):
        bundle = reference.heritage(refresh=True)
    else:
        bundle = reference.heritage()
    meta = dict(bundle.get("meta") or {})
    items = bundle.get("items") or []
    return _json({
        "ok": True,
        "meta": meta,
        "count": len(items),
        "items": items[: int(_float(query, "limit", 0) or len(items))],
    })


def api_hotels(query: Dict[str, List[str]]) -> Response:
    if _mode(query) == "global":
        result = intl.search("hotel", {
            "keyword": _str(query, "keyword"), "city": _str(query, "city"),
            "lat": _float(query, "lat"), "lng": _float(query, "lng"),
            "page": _int(query, "page", 1), "page_size": _int(query, "page_size", 8),
        })
        _decorate(result["items"], "hotel")
        return _json(result)
    near = None
    near_key = _str(query, "near")
    city = _str(query, "city")
    if near_key:
        attraction = live.resolve_anchor("attraction", near_key)
        if attraction:
            near = {"name": attraction["name"], "lat": attraction.get("lat"),
                    "lng": attraction.get("lng"), "city": attraction.get("city") or ""}
            if not city:
                city = near["city"]
    sort = _str(query, "sort")
    near_radius = _float(query, "max_distance", 50.0 if near else None)
    result = live.search("hotel", {
        "keyword": _str(query, "keyword"), "city": city,
        "min_price": _float(query, "min_price"), "max_price": _float(query, "max_price"),
        "min_rating": _float(query, "min_rating") or 0.0,
        "min_star": _int(query, "min_star", 0),
        "max_metro": _int(query, "max_metro", 0),
        "lat": near.get("lat") if near else None,
        "lng": near.get("lng") if near else None,
        "max_distance": near_radius,
        "sort": sort or ("distance" if near else ""),
        "page": _int(query, "page", 1), "page_size": _int(query, "page_size", 8),
    })
    _decorate(result["items"], "hotel")
    _attach_metro(result["items"], city)
    if near and near.get("lat") is not None:
        for item in result["items"]:
            if item.get("lat") is not None:
                item["distance_to_attraction_km"] = round(
                    haversine_km(near["lat"], near["lng"], item["lat"], item["lng"]), 2)
    result["near"] = near
    return _json(result)


def _attach_metro(items: List[Dict[str, Any]], city: str) -> None:
    if not items:
        return
    pool = live.metros(city or str(items[0].get("city") or ""))
    for hotel in items:
        if hotel.get("lat") is None:
            continue
        best = None
        for station in pool:
            km = haversine_km(hotel["lat"], hotel["lng"], station["lat"], station["lng"])
            if best is None or km < best[0]:
                best = (km, station)
        if best and best[0] <= 5:
            hotel["metro_station"] = best[1]["name"]
            hotel["metro_distance_m"] = int(round(best[0] * 1000))
            hotel["metro_walk_min"] = int(round(best[0] * 1000 / 75))
        else:
            hotel["metro_station"] = ""
            hotel["metro_distance_m"] = None


def api_hotel_detail(hotel_id: str, mode: str = "cn") -> Response:
    if mode == "global":
        hotel = intl.detail("hotel", hotel_id)
        if not hotel:
            return _json({"ok": False, "message": "国际版快照中没有这家住宿。"}, 404)
        return _json(templates.hotel_detail(hotel))
    hotel = live.detail_by_id("hotel", hotel_id) or live.detail("hotel", hotel_id)
    if hotel:
        _normalize_offers(hotel)
        hotel["platform_ratings"] = _platform_ratings(hotel)
    if not hotel:
        return _json({"ok": False, "message": "No live match for this hotel and no cached snapshot for the area."}, 404)
    _attach_metro([hotel], str(hotel.get("city") or ""))
    hotel["nearest_metro"] = live.nearest_metro(hotel)
    if hotel.get("lat") is not None:
        related = live.search("attraction", {"city": hotel.get("city"), "page": 1,
                                             "page_size": 8}).get("items", [])
        attrs = []
        for row in related:
            if row.get("lat") is None:
                continue
            entry = dict(row)
            entry["distance_km"] = round(haversine_km(hotel["lat"], hotel["lng"],
                                                      row["lat"], row["lng"]), 2)
            attrs.append(entry)
        attrs.sort(key=lambda x: x["distance_km"])
        hotel["nearby_attractions"] = attrs[:4]
    if not hotel.get("gallery"):
        hotel["gallery"] = hotel.get("photos") or [hotel.get("cover_image") or cover_url(hotel["name"], hotel.get("city") or "", 5)]
    return _json(templates.hotel_detail(hotel))


def api_metros(query: Dict[str, List[str]]) -> Response:
    return _json({"items": live.metros(_str(query, "city"))})


# ------------------------------ 比价 ------------------------------

def api_compare(query: Dict[str, List[str]]) -> Response:
    keys = [k for k in query.get("attractions", [""])[0].split(",") if k]
    hotel_ids = [h for h in query.get("hotels", [""])[0].split(",") if h]
    attractions, hotels = [], []
    for key in keys[:6]:
        item = live.detail("attraction", key)
        if not item:
            continue
        _normalize_offers(item)
        item = ticket_quotes.attach(item)
        attractions.append({
            "key": item["key"], "name": item["name"], "city": item.get("city"),
            "city_en": i18n.city(item.get("city") or ""),
            "rating": item.get("rating"), "review_count": item.get("review_count", 0),
            "price": item.get("price"), "offers": item.get("offers") or [],
            "price_source": item.get("price_source", ""),
            "policy": item.get("policy") or {},
        })
    for hid in hotel_ids[:8]:
        item = live.detail_by_id("hotel", hid)
        if not item:
            continue
        _normalize_offers(item)
        hotels.append({
            "id": item.get("id"), "name": item["name"], "city": item.get("city"),
            "city_en": i18n.city(item.get("city") or ""),
            "platform_ratings": _platform_ratings(item),
            "star": item.get("star", 3), "rating": item.get("rating"),
            "price": item.get("price"), "offers": item.get("offers") or [],
            "metro_station": item.get("metro_station", ""),
            "metro_distance_m": item.get("metro_distance_m"),
            "price_source": item.get("price_source", ""),
        })
    platforms = sorted({o["platform"] for a in attractions + hotels for o in a.get("offers", [])})
    return _json({"attractions": attractions, "hotels": hotels,
                  "platforms": platforms or ["Live fetch"]})


# ------------------------------ 行程 ------------------------------

def api_trip_create(body: Dict[str, Any]) -> Response:
    trip = trips.create((body.get("title") or "").strip() or "My Trip",
                        body.get("city") or "", body.get("start_date") or "")
    return _json({"ok": True, "trip": trip}, 201)


def api_trip_import(body: Dict[str, Any]) -> Response:
    if not isinstance(body, dict):
        raise ValueError("Trip payload must be a JSON object")
    payload = body.get("trip") if isinstance(body.get("trip"), dict) else body
    trip = trips.import_trip(payload)
    return _json({"ok": True, "trip": trip}, 201)


def api_trip_get(trip_id: int) -> Response:
    trip = trips.get(trip_id)
    if not trip:
        return _json({"ok": False, "message": "Trip not found"}, 404)
    return _json({"ok": True, "trip": trip})


def api_trip_add_item(trip_id: int, body: Dict[str, Any]) -> Response:
    if not trips.get(trip_id):
        return _json({"ok": False, "message": "Trip not found"}, 404)
    key = (body.get("key") or "").strip()
    kind = body.get("kind") or "attraction"
    item = live.detail_by_id(kind, key) if kind == "hotel" else live.detail("attraction", key)
    if not item:
        item = live.detail("attraction", key) or live.detail_by_id(kind, key)
    if not item:
        return _json({"ok": False, "message": "Place not found in live data. Search again and add it from the results."}, 400)
    snapshot = {
        "key": item.get("key") or key, "name": item.get("name"),
        "attraction_name": item.get("name"), "city": item.get("city"),
        "address": item.get("address"), "lat": item.get("lat"), "lng": item.get("lng"),
        "rating": item.get("rating"), "price": item.get("price"), "kind": kind,
        "cover_image": item.get("cover_image"), "tags": item.get("tags") or [],
        "day": int(body.get("day") or 1),
        "visit_minutes": int(body.get("visit_minutes") or (0 if kind == "hotel" else 120)),
    }
    trip = trips.add_item(trip_id, snapshot)
    return _json({"ok": True, "trip": trip}, 201)


def api_trip_remove_item(trip_id: int, item_id: int) -> Response:
    trip = trips.remove_item(trip_id, item_id)
    if trip is None:
        return _json({"ok": False, "message": "Trip or item not found"}, 404)
    return _json({"ok": True, "trip": trip})


def api_trip_update_items(trip_id: int, body: Dict[str, Any]) -> Response:
    trip = trips.update_items(trip_id, body.get("items") or [])
    if trip is None:
        return _json({"ok": False, "message": "Trip not found"}, 404)
    return _json({"ok": True, "trip": trip})


def api_plan(trip_id: int, body: Dict[str, Any]) -> Response:
    trip = trips.get(trip_id)
    if not trip:
        return _json({"ok": False, "message": "Trip not found"}, 404)
    if not trip["items"]:
        return _json({"ok": False, "message": "This trip has no places yet"}, 400)
    result = routing.plan_route(
        trip["items"], mode=body.get("mode") or "driving",
        origin=body.get("origin") or None, start_time=body.get("start_time") or "09:00",
        optimize=bool(body.get("optimize", True)),
        daily_limit_hours=float(body.get("daily_limit_hours") or 10),
        allow_remote=settings.server_route_enabled and bool(body.get("use_baidu", True)),
    )
    result["trip"] = {"id": trip["id"], "title": trip["title"], "city": trip.get("city")}
    runs.add({"type": "plan", "trip": trip["id"], "stops": result["summary"]["stops"]})
    return _json(result)


def api_route_preview(query: Dict[str, List[str]]) -> Response:
    keys = [k for k in query.get("keys", [""])[0].split(",") if k]
    if not keys:
        return _json({"ok": False, "message": "Provide a list of place keys."}, 400)
    items = []
    for key in keys[:12]:
        item = live.detail("attraction", unquote(key))
        if item:
            items.append({**item, "day": 1, "visit_minutes": 120})
    if not items:
        return _json({"ok": False, "message": "None of these places were found in live data."}, 404)
    origin = None
    lat, lng = _float(query, "origin_lat"), _float(query, "origin_lng")
    if lat is not None and lng is not None:
        origin = {"lat": lat, "lng": lng, "name": _str(query, "origin_name", "Origin")}
    return _json(routing.plan_route(items, mode=_str(query, "mode", "driving"), origin=origin,
                                    optimize=_str(query, "optimize", "1") == "1"))


def api_geocode(query: Dict[str, List[str]]) -> Response:
    address = _str(query, "q") or _str(query, "address")
    if not address:
        return _json({"ok": False, "message": "Missing query text."}, 400)
    if not settings.server_route_enabled:
        return _json({"ok": False, "message": "No Baidu server AK configured", "configured": False})
    result = baidu.geocode(address, _str(query, "city"))
    return _json({"ok": bool(result), **(result or {})})


# ------------------------------ 采集 ------------------------------

def api_collect(query: Dict[str, List[str]], body: Dict[str, Any]) -> Response:
    """立即抓取。默认后台执行并返回 started，前端轮询 /api/collect/status。

    单城市全量抓取约 10-20 秒，同步返回会超过浏览器请求超时，因此改为异步。
    """
    import threading

    city = _str(query, "city") or str(body.get("city") or "").strip()
    cities = [city] if city else None
    wait = _str(query, "wait") in ("1", "true", "yes")
    if wait:
        result = harvest.run_collection("manual", cities=cities, full=True)
        payload = dict(result)
        payload["cache"] = live.stats()
        return _json(payload)
    if harvest.STATE.get("running"):
        return _json({"ok": True, "status": "running", "cities": cities or [],
                      "message": "A fetch is already running."})
    threading.Thread(target=harvest.run_collection, args=("manual",),
                     kwargs={"cities": cities, "full": True}, daemon=True).start()
    return _json({"ok": True, "status": "started", "cities": cities or [],
                  "message": "Fetch started; the page refreshes when it finishes."})


def api_collect_status(query: Dict[str, List[str]]) -> Response:
    payload = harvest.status()
    payload["coverage"] = coverage.state()
    return _json(payload)


def api_transport(query: Dict[str, List[str]]) -> Response:
    """城际交通比对：机票 / 高铁 / 自驾的时间和费用区间（不含购买渠道）。"""
    from_city = _str(query, "from")
    to_city = _str(query, "to")
    if not from_city or not to_city:
        return _json({"ok": False, "message": "from and to are required"}, 400)
    if _mode(query) == "global":
        return _json(intl.transport(from_city, to_city))
    result = transport.compare(from_city, to_city, _str(query, "date"), _str(query, "province"))
    return _json(result)


def api_fuel(query: Dict[str, List[str]]) -> Response:
    """省级成品油挂牌价（元/升）。"""
    province = _str(query, "province") or "北京"
    data = transport.fuel_prices(province)
    payload = {"ok": True, **data}
    if not data.get("prices"):
        payload.update({"ok": False, "message": "Fuel price source unavailable right now"})
    return _json(payload)


def api_coverage(query: Dict[str, List[str]]) -> Response:
    return _json({"ok": True, **coverage.state(), "top_places": coverage.top_places(20)})


# ------------------------------ 分发 ------------------------------

def dispatch(method: str, raw_path: str, query: Dict[str, List[str]], body: bytes) -> Response:
    path = unquote(raw_path.split("?")[0])
    try:
        if path == "/api/health":
            return api_health(query)
        if path == "/api/meta":
            return api_meta(query)
        if path == "/api/config":
            return api_config_update(_body(body)) if method == "POST" else api_config(query)
        if path == "/api/crypto/session":
            return api_crypto_session(query)
        if path == "/api/cover":
            return api_cover(query)
        if path == "/api/sources":
            return api_sources(query)
        if path == "/api/reference":
            return api_reference(query)
        if path == "/api/warmup":
            if _mode(query) == "global":
                return _json({"ok": True, **intl_warmup.state()})
            return _json({"ok": True, **warmup.state()})
        if path == "/api/map/guide":
            return api_map_guide(query)
        if path == "/api/providers":
            return _json({"providers": [], "settings": {}, "map_enabled": settings.map_enabled})
        if path == "/api/providers/test" and method == "POST":
            return _json({"ok": False, "message": "All data sources are built in; no third-party POI provider is required."}, 400)
        if path == "/api/live/health":
            return api_live_health(query)
        if path == "/api/live/cache":
            return api_live_cache(query)
        if path == "/api/search":
            return api_search(query)
        if path == "/api/attractions":
            return api_attractions(query)
        if path.startswith("/api/attractions/"):
            return api_attraction_detail(path[len("/api/attractions/"):], _mode(query))
        if path == "/api/hotels":
            return api_hotels(query)
        if path.startswith("/api/hotels/"):
            return api_hotel_detail(path[len("/api/hotels/"):], _mode(query))
        if path == "/api/metros":
            return api_metros(query)
        if path == "/api/compare":
            return api_compare(query)
        if path == "/api/route/preview":
            return api_route_preview(query)
        if path == "/api/geocode":
            return api_geocode(query)
        if path == "/api/collect" and method == "POST":
            return api_collect(query, _body(body))
        if path == "/api/collect/status":
            return api_collect_status(query)
        if path == "/api/transport":
            return api_transport(query)
        if path == "/api/fuel":
            return api_fuel(query)
        if path == "/api/coverage":
            return api_coverage(query)
        if path == "/api/platforms":
            return api_platforms(query)
        if path == "/api/trips" and method == "POST":
            return api_trip_create(_body(body))
        if path == "/api/trips/import" and method == "POST":
            return api_trip_import(_body(body))
        if path.startswith("/api/trips/"):
            parts = [p for p in path[len("/api/trips/"):].split("/") if p]
            trip_id = int(parts[0])
            if len(parts) == 1 and method == "GET":
                return api_trip_get(trip_id)
            if len(parts) == 2 and parts[1] == "items" and method == "POST":
                return api_trip_add_item(trip_id, _body(body))
            if len(parts) == 2 and parts[1] == "items" and method == "PUT":
                return api_trip_update_items(trip_id, _body(body))
            if len(parts) == 3 and parts[1] == "items" and method == "DELETE":
                return api_trip_remove_item(trip_id, int(parts[2]))
            if len(parts) == 2 and parts[1] == "plan" and method == "POST":
                return api_plan(trip_id, _body(body))
        return _json({"ok": False, "message": f"No such API endpoint: {path}"}, 404)
    except ValueError as exc:
        return _json({"ok": False, "message": f"Invalid parameter: {exc}"}, 400)
    except Exception as exc:
        traceback.print_exc()
        return _json({"ok": False, "message": f"Server error: {type(exc).__name__}: {exc}"}, 500)


def _body(raw: bytes) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}