# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""国际版数据层：QLever/Wikidata 取地点，标志性景点按 QID 白名单直取；快照作用域 `intl::<City>`。

对外接口与国内版本的 services.live 同名同形，web_api 按 mode 选择调用方即可，
前端不需要为两种模式写两套逻辑。价格、评分、图片在国际源里通常为空，
统一返回 None/[] 由前端标注“暂无”，不做填充或推测。
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional

from collectors import wikidata_places
from core import cache_store, i18n

CACHE_TTL_SECONDS = 24 * 3600
INTL_VERSION = 4   # 查询口径版本：升级后旧快照自动重抓
SOURCE_LABEL = {"Wikidata": "Wikidata (CC0)"}


def scope(city: str) -> str:
    return "intl::" + str(city or "").strip()


def city_row(name: str) -> Optional[Dict[str, Any]]:
    return wikidata_places.city_by_name(name) or wikidata_places.resolve_city(name)


def all_cities() -> List[Dict[str, Any]]:
    """内置城市 + 运行期动态解析出的城市，去重后统一带上中心坐标。"""
    rows = [wikidata_places.pointed(r) for r in wikidata_places.CITIES]
    known = {r["city"] for r in rows}
    for value in (wikidata_places._load_custom() or {}).values():
        if value.get("city") not in known:
            rows.append(wikidata_places.pointed(value))
            known.add(value.get("city"))
    return rows


def cities() -> List[Dict[str, Any]]:
    out = []
    rows = all_cities()
    for row in rows:
        attractions = cache_store.items("attraction", scope(row["city"]))
        hotels = cache_store.items("hotel", scope(row["city"]))
        out.append({
            "city": row["city"], "city_en": row["en"], "country": row["country"],
            "qid": row["qid"], "count": len(attractions), "hotels": len(hotels),
        })
    return out


def _haversine(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(h)), 2)


def _normalize(kind: str, raw: Dict[str, Any], city: Dict[str, str]) -> Dict[str, Any]:
    name = str(raw.get("name") or "").strip()
    key = "%s::%s" % (city["en"], name)
    base = {
        "key": key, "name": name, "name_en": raw.get("name_en") or name,
        "city": city["city"], "city_en": city["en"], "country": city["country"],
        "lat": raw.get("lat"), "lng": raw.get("lng"),
        "address": raw.get("address") or "", "tags": raw.get("tags") or [],
        "tags_en": [], "photos": [], "cover_image": "",
        "source": raw.get("source") or "Wikidata",
        "price": None, "original_price": None, "price_source": "", "price_note": "",
        "rating": None, "review_count": 0,
    }
    if kind == "hotel":
        base.update({"id": key, "star": 3, "amenities": []})
    if kind == "metro":
        base.update({"line": "", "station": name})
    return base


def harvest(kind: str, city: str, force: bool = False) -> Dict[str, Any]:
    row = city_row(city)
    if not row:
        return {"city": city, "kind": kind, "source": "unsupported", "rows": 0, "count": 0}
    scoped = scope(row["city"])
    record = cache_store.load(kind, scoped)
    age = cache_store.age_seconds(record)
    if record and age is not None and age < CACHE_TTL_SECONDS and not force:
        return {"city": row["city"], "kind": kind, "source": "cache",
                "rows": 0, "count": int(record.get("count") or 0)}

    started = time.time()
    raw = wikidata_places.fetch(kind, row["en"])
    source = "Wikidata"
    items = [_normalize(kind, entry, row) for entry in raw]
    if kind == "attraction":
        # 标志性景点白名单直取，避免只按行政区检索时漏掉埃菲尔铁塔这类条目
        landmarks = wikidata_places.fetch_landmarks(row["city"])
        if landmarks:
            items.extend(_normalize(kind, entry, row) for entry in landmarks)
        # 同一坐标只留一条，优先保留后加入的白名单名称（简体）
        merged: Dict[tuple, Dict[str, Any]] = {}
        for item in items:
            lat, lng = item.get("lat"), item.get("lng")
            marker = (round(float(lat), 3), round(float(lng), 3)) if lat is not None and lng is not None else item.get("key")
            merged[marker] = item
        items = list(merged.values())
    if items:
        result = cache_store.save(kind, scoped, items, source.lower(),
                                  extra={"intl_version": INTL_VERSION})
        count = result["count"]
    else:
        count = int((record or {}).get("count") or 0)
    return {"city": row["city"], "kind": kind, "source": source.lower() if items else "empty",
            "rows": len(items), "count": count,
            "elapsed_ms": int((time.time() - started) * 1000)}


def ensure(kind: str, city: str) -> None:
    row = city_row(city)
    if not row:
        return
    record = cache_store.load(kind, scope(row["city"]))
    age = cache_store.age_seconds(record)
    stale = record is not None and record.get("intl_version") != INTL_VERSION
    if record and age is not None and age < CACHE_TTL_SECONDS and not stale:
        return
    harvest(kind, row["city"], force=stale)


def _rows(kind: str, city: str) -> List[Dict[str, Any]]:
    row = city_row(city)
    if not row:
        return []
    ensure(kind, row["city"])
    rows = cache_store.items(kind, scope(row["city"]))
    if not rows:
        # 首次请求遇到缓存层尚未失效时，强制补抓一次并重试读取
        harvest(kind, row["city"], force=True)
        for _ in range(4):
            rows = cache_store.items(kind, scope(row["city"]))
            if rows:
                break
            time.sleep(0.5)
    return rows


def search(kind: str, params: Dict[str, Any]) -> Dict[str, Any]:
    city = str(params.get("city") or "").strip()
    keyword = str(params.get("keyword") or "").strip().lower()
    page = max(1, int(params.get("page") or 1))
    size = max(1, min(60, int(params.get("page_size") or 12)))

    if city and city_row(city) is None:
        return {"ok": False, "items": [], "total": 0, "page": page, "page_size": size,
                "source": "global",
"message": "该城市未能解析，请尝试英文城市名或换个写法"}
    if city:
        rows = _rows(kind, city)
    else:
        rows = []
        for row in all_cities():
            rows.extend(cache_store.items(kind, scope(row["city"])))

    if keyword:
        rows = [r for r in rows if keyword in str(r.get("name") or "").lower()
                or keyword in str(r.get("name_en") or "").lower()]
        if not city and kind == "attraction" and len(keyword) >= 2 and len(rows) < 3:
            # 缓存里没有时，用 QLever 做一次实时检索，并把结果落进快照
            try:
                known = {str(r.get("name") or "") for r in rows}
                live_rows = wikidata_places.search_landmarks(keyword, 8, known)
                live_rows = [dict(row, kind=kind) for row in live_rows]
                live_items = register_live(live_rows)
                seen = {r.get("key") for r in rows}
                rows.extend(item for item in live_items if item.get("key") not in seen)
            except Exception:
                pass

    min_rating = params.get("min_rating") or 0
    if min_rating:
        rows = [r for r in rows if (r.get("rating") or 0) >= float(min_rating)]

    lat, lng = params.get("lat"), params.get("lng")
    if lat and lng:
        anchor = {"lat": float(lat), "lng": float(lng)}
        rows = [dict(r, distance_km=_haversine(anchor, r)) for r in rows if r.get("lat") is not None]
        rows.sort(key=lambda r: r["distance_km"])
    else:
        rows.sort(key=lambda r: str(r.get("name") or ""))

    # 同一地点可能有多个译名（如“大本钟”与“威斯敏斯特宫”），按坐标合并
    deduped, seen_points = [], set()
    for row in rows:
        lat, lng = row.get("lat"), row.get("lng")
        point = (round(float(lat), 3), round(float(lng), 3)) if lat is not None and lng is not None else None
        marker = point or (str(row.get("name") or ""), str(row.get("city") or ""))
        if marker in seen_points:
            continue
        seen_points.add(marker)
        deduped.append(row)
    rows = deduped

    total = len(rows)
    start = (page - 1) * size
    items = rows[start:start + size]
    return {"ok": True, "items": items, "total": total, "page": page, "page_size": size,
            "source": "global", "source_label": "International snapshot"}


def register_live(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把实时检索到的条目写进对应城市快照，返回规范化后的条目（详情页可直接打开）。"""
    grouped: Dict[tuple, Dict[str, Any]] = {}
    out: List[Dict[str, Any]] = []
    for row in rows:
        city = {"city": row.get("city") or "国际", "en": row.get("city_en") or "Global",
                "country": row.get("country") or ""}
        raw = {"name": row.get("name"), "name_en": row.get("name_en"),
               "lat": row.get("lat"), "lng": row.get("lng"),
               "tags": ["live-search"], "source": "Wikidata"}
        item = _normalize(row.get("kind") or "attraction", raw, city)
        item["source"] = "Wikidata"
        item["live_search"] = True
        key = (row.get("kind") or "attraction", city["city"])
        grouped.setdefault(key, {"city": city, "items": []})["items"].append(item)
        out.append(item)
    for (kind, _name), entry in grouped.items():
        cache_store.save(kind, scope(entry["city"]["city"]), entry["items"], "wikidata",
                         extra={"intl_version": INTL_VERSION})
    return out


def detail(kind: str, key: str, force: bool = False) -> Optional[Dict[str, Any]]:
    city_en, _, name = key.partition("::")
    row = city_row(city_en)
    if not row:
        return None
    ensure(kind, row["city"])
    item = cache_store.find(kind, key)
    if not item:
        return None
    fresh = dict(item)
    fresh["source"] = "cache"
    fresh["source_label"] = SOURCE_LABEL.get(item.get("source") or "Wikidata", "International source")
    fresh["fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    if kind == "attraction":
        fresh["nearby_hotels"] = nearby_hotels(fresh, limit=4)
        fresh["nearest_metro"] = nearest_metro(fresh)
    return fresh


def _cached_rows(kind: str, city: str) -> List[Dict[str, Any]]:
    """只读缓存，不触发网络抓取：详情页的“周边”用它，避免一次详情等十几秒。"""
    row = city_row(city)
    if not row:
        return []
    return cache_store.items(kind, scope(row["city"]))


def nearby_hotels(attraction: Dict[str, Any], limit: int = 4) -> List[Dict[str, Any]]:
    if attraction.get("lat") is None:
        return []
    rows = _cached_rows("hotel", attraction.get("city_en") or attraction.get("city") or "")
    out = []
    for row in rows:
        if row.get("lat") is None:
            continue
        out.append(dict(row, distance_km=_haversine(attraction, row)))
    out.sort(key=lambda r: r["distance_km"])
    return out[:limit]


def nearest_metro(place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if place.get("lat") is None:
        return None
    rows = _cached_rows("metro", place.get("city_en") or place.get("city") or "")
    best = None
    for row in rows:
        if row.get("lat") is None:
            continue
        dist = _haversine(place, row)
        if best is None or dist < best["distance_km"]:
            best = dict(row, distance_km=dist)
    return best


def metros(city: str) -> List[Dict[str, Any]]:
    return _rows("metro", city)


def stats() -> Dict[str, Any]:
    rows = all_cities()
    by_kind = {}
    for kind in ("attraction", "hotel", "metro"):
        by_kind[kind] = sum(len(cache_store.items(kind, scope(row["city"]))) for row in rows)
    return {"by_kind": by_kind, "cities": len(rows)}


def meta() -> Dict[str, Any]:
    rows = cities()
    counts = stats()["by_kind"]
    return {
        "cities": rows,
        "tags": [],
        "tag_en": {},
        "levels": [],
        "counts": {"attractions": counts.get("attraction", 0), "hotels": counts.get("hotel", 0),
                   "metro": counts.get("metro", 0)},
        "mode": "global",
        "source": "Wikidata",
    }


# ---------------------------------------------------------------------------
# 城际交通与费用估算（国际版）
#
# 与国内版共用同一套输出结构（mode/label/duration_min/price_from/price_to/
# breakdown_label/source_label），前端只按字段渲染，不区分版本。
#
# 口径说明：
# 1) 机票：按航距分段的单程经济舱含税区间，再乘航线因子（国内线 / 同区域 /
#    洲际）与枢纽因子（两端均为枢纽机场时竞争更充分，价格更低）；跨洲且两端
#    都不是枢纽时按一次中转加时并加价。不含旺季与提前购票折扣。
# 2) 铁路：仅在同一区域且距离 ≤1600 km 时给出，按区域每公里票价 + 基础价，
#    再乘“提前购票 / 灵活票价”区间；跨境有加价与边检时间。
# 3) 自驾：油价按“当地货币挂牌价 × 固定参考汇率”折算人民币，跨境取两国均值，
#    通行费取两国费率均值；岛国跨境需轮渡/隧道，只提示不计价。
# 4) 汇率是写死的参考值，不是实时行情，页面会标注。
# ---------------------------------------------------------------------------

FLIGHT_BANDS = [
    # (上限航距 km, 价格下限, 价格上限, 段名)
    (800, 420, 1050, "短途"),
    (1500, 700, 1750, "中短途"),
    (3000, 1300, 3300, "中途"),
    (6000, 2300, 5600, "长途"),
    (20000, 3500, 9000, "洲际"),
]

FLIGHT_ROUTE_FACTOR = {"domestic": 0.78, "region": 0.92, "inter": 1.0}
FLIGHT_HUB_FACTOR = {"both": 0.88, "one": 0.95, "none": 1.06}
HUBS = {
    "london", "paris", "frankfurt", "amsterdam", "madrid", "rome", "istanbul",
    "dubai", "doha", "singapore", "hong kong", "tokyo", "seoul", "beijing",
    "shanghai", "new york", "los angeles", "chicago", "toronto", "sydney",
    "bangkok", "kuala lumpur", "mumbai", "delhi", "johannesburg",
}

REGION = {
    "法国": "Europe", "德国": "Europe", "英国": "Europe", "意大利": "Europe",
    "西班牙": "Europe", "荷兰": "Europe", "比利时": "Europe", "瑞士": "Europe",
    "奥地利": "Europe", "捷克": "Europe", "波兰": "Europe", "丹麦": "Europe",
    "瑞典": "Europe", "挪威": "Europe", "芬兰": "Europe", "葡萄牙": "Europe",
    "希腊": "Europe", "爱尔兰": "Europe", "匈牙利": "Europe", "俄罗斯": "Europe",
    "美国": "North America", "加拿大": "North America", "墨西哥": "North America",
    "巴西": "South America", "阿根廷": "South America",
    "日本": "East Asia", "韩国": "East Asia", "中国": "East Asia",
    "新加坡": "Southeast Asia", "泰国": "Southeast Asia", "马来西亚": "Southeast Asia",
    "印度尼西亚": "Southeast Asia", "越南": "Southeast Asia", "菲律宾": "Southeast Asia",
    "印度": "South Asia",
    "澳大利亚": "Oceania", "新西兰": "Oceania",
    "阿联酋": "Middle East", "土耳其": "Middle East",
    "埃及": "Africa", "南非": "Africa",
}

# 当地货币挂牌价（元/升）与币种；折算用下面的固定参考汇率
COUNTRY_FUEL = {
    "法国": (1.85, "EUR"), "德国": (1.78, "EUR"), "意大利": (1.80, "EUR"),
    "西班牙": (1.58, "EUR"), "荷兰": (1.82, "EUR"), "比利时": (1.75, "EUR"),
    "奥地利": (1.60, "EUR"), "葡萄牙": (1.68, "EUR"), "希腊": (1.70, "EUR"),
    "爱尔兰": (1.68, "EUR"), "芬兰": (1.72, "EUR"),
    "英国": (1.45, "GBP"), "瑞士": (1.72, "CHF"),
    "捷克": (38.5, "CZK"), "波兰": (6.4, "PLN"), "匈牙利": (590, "HUF"),
    "丹麦": (13.5, "DKK"), "瑞典": (17.5, "SEK"), "挪威": (19.0, "NOK"),
    "美国": (0.95, "USD"), "加拿大": (1.55, "CAD"), "墨西哥": (24.0, "MXN"),
    "巴西": (5.9, "BRL"), "阿根廷": (950, "ARS"),
    "日本": (175, "JPY"), "韩国": (1650, "KRW"), "新加坡": (2.75, "SGD"),
    "泰国": (38.0, "THB"), "马来西亚": (2.05, "MYR"), "印度尼西亚": (13500, "IDR"),
    "越南": (23000, "VND"), "菲律宾": (58.0, "PHP"), "印度": (105, "INR"),
    "澳大利亚": (1.85, "AUD"), "新西兰": (2.60, "NZD"),
    "阿联酋": (2.75, "AED"), "土耳其": (43.0, "TRY"),
    "埃及": (13.0, "EGP"), "南非": (23.5, "ZAR"), "俄罗斯": (58.0, "RUB"),
}

# 固定参考汇率（1 当地货币 = x 人民币），仅用于量级折算，不是实时行情
FX_TO_CNY = {
    "CNY": 1.0, "EUR": 7.60, "GBP": 8.90, "CHF": 8.00, "USD": 7.10,
    "CAD": 5.20, "MXN": 0.36, "BRL": 1.30, "ARS": 0.0075,
    "JPY": 0.048, "KRW": 0.0052, "SGD": 5.30, "THB": 0.20, "MYR": 1.60,
    "IDR": 0.00045, "VND": 0.00028, "PHP": 0.125, "INR": 0.085,
    "AUD": 4.70, "NZD": 4.30, "AED": 1.93, "TRY": 0.21,
    "EGP": 0.14, "ZAR": 0.39, "RUB": 0.078,
    "CZK": 0.31, "PLN": 1.78, "HUF": 0.019, "DKK": 1.02,
    "SEK": 0.67, "NOK": 0.66,
}

# 通行费（折算后 元/km），岛国跨境另需轮渡/隧道
COUNTRY_TOLL = {
    "法国": 0.90, "德国": 0.0, "英国": 0.0, "意大利": 0.75, "西班牙": 0.55,
    "荷兰": 0.0, "比利时": 0.0, "瑞士": 0.55, "奥地利": 0.60, "捷克": 0.35,
    "波兰": 0.30, "丹麦": 0.0, "瑞典": 0.0, "挪威": 0.45, "芬兰": 0.0,
    "葡萄牙": 0.55, "希腊": 0.45, "匈牙利": 0.40, "美国": 0.10, "加拿大": 0.12,
    "墨西哥": 0.20, "日本": 1.05, "韩国": 0.55, "新加坡": 0.30, "泰国": 0.25,
    "马来西亚": 0.15, "印度尼西亚": 0.12, "越南": 0.18, "菲律宾": 0.10,
    "印度": 0.12, "澳大利亚": 0.0, "新西兰": 0.0, "阿联酋": 0.15,
    "土耳其": 0.25, "巴西": 0.20, "阿根廷": 0.15, "南非": 0.15,
    "埃及": 0.10, "俄罗斯": 0.10,
}

ISLAND_COUNTRIES = {
    "英国", "爱尔兰", "日本", "印度尼西亚", "菲律宾", "新加坡", "澳大利亚",
    "新西兰", "斯里兰卡", "冰岛", "马耳他", "塞浦路斯",
}

# 岛国与大陆之间有固定陆路通道（隧道/跨海大桥/长堤）的国家对，才允许自驾过境
LAND_LINKS = {
    ("英国", "法国"), ("法国", "英国"),
    ("丹麦", "瑞典"), ("瑞典", "丹麦"),
    ("新加坡", "马来西亚"), ("马来西亚", "新加坡"),
}
MODE_ORDER = {"rail": 0, "flight": 1, "drive": 2}

RAIL_REGIONS = {
    "Europe": {"rate": 1.15, "speed": 190, "label": "欧洲铁路", "label_en": "Europe rail"},
    "East Asia": {"rate": 0.95, "speed": 200, "label": "东亚高铁", "label_en": "East Asia high-speed rail"},
    "North America": {"rate": 0.80, "speed": 110, "label": "北美铁路", "label_en": "North America rail"},
}
RAIL_BASE = 45.0
RAIL_BAND = (0.60, 1.70)
RAIL_MIN_KM = 80
RAIL_MAX_KM = 1600


def _flight_band(km: float) -> tuple:
    for high, low, top, _label in FLIGHT_BANDS:
        if km <= high:
            return low, top
    return FLIGHT_BANDS[-1][1], FLIGHT_BANDS[-1][2]


def _region_of(country: str) -> str:
    return REGION.get(country) or "Other"


def _fuel_cny(country: str) -> Optional[float]:
    entry = COUNTRY_FUEL.get(country)
    if not entry:
        return None
    price, cur = entry
    rate = FX_TO_CNY.get(cur)
    if not rate:
        return None
    return round(price * rate, 2)


def _flight(km: float, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    low, high = _flight_band(km)
    same_country = (a.get("country") or "") == (b.get("country") or "")
    same_region = _region_of(a.get("country") or "") == _region_of(b.get("country") or "")
    route_kind = "domestic" if same_country else ("region" if same_region else "inter")
    route_factor = FLIGHT_ROUTE_FACTOR[route_kind]

    hub_a = str(a.get("en") or "").lower() in HUBS
    hub_b = str(b.get("en") or "").lower() in HUBS
    hub_kind = "both" if hub_a and hub_b else ("one" if hub_a or hub_b else "none")
    hub_factor = FLIGHT_HUB_FACTOR[hub_kind] if km > 1200 else 1.0

    stops = 0
    transfer_min = 0
    if route_kind == "inter" and hub_kind == "none" and km > 7000:
        stops = 1
        transfer_min = 100

    price_low = int(round(low * route_factor * hub_factor / 10.0) * 10)
    price_high = int(round(high * route_factor * hub_factor / 10.0) * 10)

    air_min = int(round(km / 800 * 60 + 35))
    ground_min = 130 if km <= 1500 else 170
    duration = air_min + ground_min + transfer_min

    route_label = {"domestic": "国内航线", "region": "同区域航线", "inter": "洲际航线"}[route_kind]
    route_label_en = {"domestic": "Domestic route", "region": "Same-region route",
                      "inter": "Intercontinental route"}[route_kind]
    return {
        "mode": "flight", "label": "Flight", "label_zh": "飞机",
        "duration_min": duration, "price_from": price_low, "price_to": price_high,
        "seats": "economy one-way", "estimated": True, "source": "estimate",
        "stops": stops,
        "source_label": ("Distance-band estimate; %s route, hub factor %.2f, taxes included"
                         % (route_kind, hub_factor)),
        "source_label_zh": ("按航距分段估算（%s，枢纽系数 %.2f，含税费）" % (route_label, hub_factor)),
        "breakdown": {
            "distance_km": round(km, 1), "band": [low, high], "route": route_kind,
            "route_factor": route_factor, "hub": hub_kind, "hub_factor": hub_factor,
            "stops": stops, "speed_kmh": 800, "ground_min": ground_min,
            "transfer_min": transfer_min,
        },
        "breakdown_label": ("%s band CNY%d-%d x route %.2f x hub %.2f = CNY%d-%d; %d km / 800 km/h + %d min ground%s"
                            % (route_label_en, low, high, route_factor, hub_factor, price_low, price_high,
                               km, ground_min, (" + %d min transfer" % transfer_min) if transfer_min else "")),
        "breakdown_label_zh": ("%s区间 %d–%d 元 × 航线系数 %.2f × 枢纽系数 %.2f = %d–%d 元；%d km ÷ 800 km/h + %d 分钟地面时间%s"
                               % (route_label, low, high, route_factor, hub_factor, price_low, price_high,
                                  km, ground_min, ("，另加 %d 分钟中转" % transfer_min) if transfer_min else "")),
    }


def _rail(km: float, a: Dict[str, Any], b: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if km < RAIL_MIN_KM or km > RAIL_MAX_KM:
        return None
    region = _region_of(a.get("country") or "")
    cfg = RAIL_REGIONS.get(region)
    if not cfg or _region_of(b.get("country") or "") != region:
        return None
    if a.get("country") in ISLAND_COUNTRIES and b.get("country") != a.get("country"):
        return None

    cross_border = a.get("country") != b.get("country")
    rail_km = km * 1.15
    fare = (RAIL_BASE + rail_km * cfg["rate"]) * (1.25 if cross_border else 1.0)
    price_low = int(round(fare * RAIL_BAND[0] / 5.0) * 5)
    price_high = int(round(fare * RAIL_BAND[1] / 5.0) * 5)
    duration = int(round(rail_km / cfg["speed"] * 60 + 35 + (35 if cross_border else 0)))
    return {
        "mode": "rail", "label": "Rail", "label_zh": "铁路",
        "duration_min": duration, "price_from": price_low, "price_to": price_high,
        "seats": "standard / flexible", "estimated": True, "source": "estimate",
        "source_label": ("%s tariff reference: CNY%.2f/km + CNY%d base, advance/flexible band; cross-border +25%%"
                         % (cfg.get("label_en") or cfg["label"], cfg["rate"], RAIL_BASE)),
        "source_label_zh": ("%s运价参考：%.2f 元/km + %d 元基础价，提前购票/灵活票价区间；跨境 +25%%"
                            % (cfg.get("label_en") or cfg["label"], cfg["rate"], RAIL_BASE)),
        "breakdown": {
            "rail_km": round(rail_km, 1), "rate": cfg["rate"], "base": RAIL_BASE,
            "cross_border": cross_border, "band": list(RAIL_BAND), "speed_kmh": cfg["speed"],
        },
        "breakdown_label": ("Rail %.0f km x CNY%.2f + CNY%d base = CNY%.0f x 0.60-1.70; %.0f km/h"
                            % (rail_km, cfg["rate"], RAIL_BASE, fare, cfg["speed"])),
        "breakdown_label_zh": ("铁路里程 %.0f km × %.2f 元/km + 基础价 %d 元 = %.0f 元，再乘 0.60–1.70 区间；按 %.0f km/h 计"
                               % (rail_km, cfg["rate"], RAIL_BASE, fare, cfg["speed"])),
    }


def _drive(km: float, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    country_a = a.get("country") or ""
    country_b = b.get("country") or ""
    cross_border = bool(country_a and country_b and country_a != country_b)
    road_km = km * (1.28 if cross_border else 1.22)

    fuel_a, fuel_b = _fuel_cny(country_a), _fuel_cny(country_b)
    known = [p for p in (fuel_a, fuel_b) if p]
    fuel_price = round(sum(known) / len(known), 2) if known else None
    toll_a = COUNTRY_TOLL.get(country_a)
    toll_b = COUNTRY_TOLL.get(country_b)
    known_toll = [t for t in (toll_a, toll_b) if t is not None]
    toll_rate = round(sum(known_toll) / len(known_toll), 2) if known_toll else None

    minutes = int(round(road_km / (75 if cross_border else 80) * 60 + (45 if cross_border else 0)))
    crosses_water = cross_border and (country_a in ISLAND_COUNTRIES or country_b in ISLAND_COUNTRIES)
    land_linked = (country_a, country_b) in LAND_LINKS
    if crosses_water and land_linked:
        minutes += 40          # 跨海隧道/跨海大桥的通行与排队时间
    option: Dict[str, Any] = {
        "mode": "drive", "label": "Self-drive", "label_zh": "自驾",
        "duration_min": minutes, "price_from": None, "price_to": None,
        "seats": "fuel + toll", "estimated": True, "source": "estimate",
        "distance_km": round(road_km, 1), "cross_border": cross_border,
        "crosses_water": crosses_water, "feasible": not (crosses_water and not land_linked),
        "fuel_price": fuel_price, "toll_rate": toll_rate,
        "fuel_source": "country-table" if fuel_price else "none",
    }
    if crosses_water and not land_linked:
        option.update({
            "price_from": None, "price_to": None, "duration_min": None,
            "source_label": "No land route between these countries; self-drive not applicable",
            "source_label_zh": "这两国之间没有陆路通道，自驾不适用",
            "breakdown_label": "No land route; option not priced",
            "breakdown_label_zh": "无陆路通道，不给费用（不按直线距离硬算）",
        })
        return option
    if fuel_price is None:
        option.update({
            "source_label": "No fuel price on file for these countries; mileage and time only",
            "source_label_zh": "这两国暂无油价参数，只给里程与时长，不给费用",
            "breakdown_label": "No fuel parameter; cost left blank",
            "breakdown_label_zh": "缺少油价参数，费用留空（不猜测）",
        })
        return option

    liters = road_km / 100 * 7.5
    fuel_cost = liters * fuel_price
    toll_cost = road_km * (toll_rate or 0)
    option.update({
        "price_from": round(fuel_cost),
        "price_to": round(fuel_cost + toll_cost),
        "liters": round(liters, 1),
        "source_label": "Fuel from country pump-price table x fixed FX; tolls and consumption are stated assumptions",
        "source_label_zh": "油价取该国挂牌价 × 固定参考汇率；油耗与通行费为公开假设值",
        "breakdown": {
            "road_km": round(road_km, 1), "fuel_per_100km": 7.5, "fuel_price": fuel_price,
            "fuel_cost": round(fuel_cost, 2), "toll_rate": toll_rate, "toll": round(toll_cost, 2),
            "cross_border": cross_border, "crosses_water": crosses_water,
        },
        "breakdown_label": ("Fuel %.0f km / 100 x 7.5 L x CNY%.2f = CNY%.0f; toll %.0f km x CNY%.2f = CNY%.0f%s"
                            % (road_km, fuel_price, fuel_cost, road_km, toll_rate or 0, toll_cost,
                               "; border 45 min" if cross_border else "")),
        "breakdown_label_zh": ("油费 %.0f km ÷ 100 × 7.5 L × %.2f 元/L = %.0f 元；通行费 %.0f km × %.2f 元/km = %.0f 元%s"
                              % (road_km, fuel_price, fuel_cost, road_km, toll_rate or 0, toll_cost,
                                 "；跨境另加 45 分钟边检" if cross_border else "")),
    })
    return option


def transport(from_city: str, to_city: str) -> Dict[str, Any]:
    a, b = city_row(from_city), city_row(to_city)
    if not a or not b:
        return {"ok": False, "message": "国际版仅支持已收录或可解析的城市"}
    ca = a.get("lat") and {"lat": a["lat"], "lng": a["lng"]} or wikidata_places.city_center(a["en"])
    cb = b.get("lat") and {"lat": b["lat"], "lng": b["lng"]} or wikidata_places.city_center(b["en"])
    if not ca or not cb:
        return {"ok": False, "message": "缺少城市坐标，无法估算"}
    km = _haversine(ca, cb)
    if km < 30:
        return {"ok": False, "message": "两座城市距离过近，城际交通不适用"}

    options: List[Dict[str, Any]] = [_flight(km, a, b)]
    rail = _rail(km, a, b)
    if rail:
        options.append(rail)
    options.append(_drive(km, a, b))
    options.sort(key=lambda o: (MODE_ORDER.get(o.get("mode"), 9),
                        o.get("price_from") is None, o.get("price_from") or 0))

    fuel_a, fuel_b = _fuel_cny(a.get("country") or ""), _fuel_cny(b.get("country") or "")
    known = [p for p in (fuel_a, fuel_b) if p]
    fuel_price = round(sum(known) / len(known), 2) if known else None

    return {
        "ok": True,
        "from": {"name": a["city"], "name_en": a["en"], "lat": ca["lat"], "lng": ca["lng"]},
        "to": {"name": b["city"], "name_en": b["en"], "lat": cb["lat"], "lng": cb["lng"]},
        "distance_km": km, "mode": "global",
        "price_currency": "CNY",
        "fuel": {"prices": ({"p92": fuel_price} if fuel_price else {}),
                 "label": "95 RON reference" if fuel_price else "",
                 "source": "country-table" if fuel_price else "none",
                 "country": a.get("country") or ""},
        "options": options,
        "params": {
            "flight_bands": [[b[0], b[1], b[2]] for b in FLIGHT_BANDS],
            "route_factor": FLIGHT_ROUTE_FACTOR,
            "hub_factor": FLIGHT_HUB_FACTOR,
            "rail": {"base": RAIL_BASE, "band": list(RAIL_BAND), "regions": RAIL_REGIONS,
                     "max_km": RAIL_MAX_KM},
            "fuel_table": "country pump price x fixed FX (CNY/L)",
            "toll_table": "country toll rate (CNY/km)",
            "road_factor": 1.22, "road_factor_cross_border": 1.28,
            "fuel_per_100km": 7.5, "fx_note": "fixed reference FX, not live rates",
        },
        "sources": [
            {"key": "flight", "name": "Distance bands", "status": "estimate",
             "detail": "5 bands, one-way economy, route & hub factors, taxes included", "url": ""},
            {"key": "rail", "name": "Rail tariff reference", "status": "estimate" if rail else "not_applicable",
             "detail": ("regional per-km rate, CNY%d base" % RAIL_BASE) if rail else "route outside rail scope",
             "url": ""},
            {"key": "drive", "name": "Country fuel table", "status": "estimate" if fuel_price else "unavailable",
             "detail": (("%s%s · %.2f CNY/L" % (a.get("country") or "",
                                                ("/" + b.get("country")) if b.get("country") != a.get("country") else "",
                                                fuel_price)) if fuel_price else "no fuel price"),
             "url": ""},
        ],
        "as_of": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "Estimates in CNY; no booking channel. Fares exclude peak season and advance-purchase discounts.",
        "note_zh": "均为人民币估算值，不提供购买渠道；不含旺季溢价与提前购票折扣。",
    }
