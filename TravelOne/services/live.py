# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""实时数据层：纯爬虫抓取 + JSON 快照回放，不使用数据库、不读取任何预置数据。

链路：
    多关键词实时检索 → 清洗/去重 → 门票与房价归一 → 实景图本地化
    → 写入 data/cache/snap_<kind>_<city>.json（上一次抓取的存档）

约定：
- 上游可达时一律返回 source=live，并带上抓取时间；
- 上游不可达时回放该城市快照，source=cache，明确标注「上次抓取」时间；
- 既没有实时结果也没有存档时返回空列表，绝不用预置数据或编造条目填充。
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from collectors import baidu_web
from core import cache_store, i18n
from core.config import BASE_DIR, settings
from core.geo import haversine_km

LIVE_IMAGE_DIR = Path(BASE_DIR) / "static" / "photos" / "live"
LIVE_IMAGE_URL = "/photos/live/"
CACHE_TTL_SECONDS = 300
HARVEST_LOCK = threading.Lock()

# 一个城市的检索词组合：覆盖「标准景点」以及容易被漏掉的类型
# CORE 用于用户首次访问时现场抓取（快），KEYWORDS 用于后台轮转全量抓取（全）
KEYWORDS = {
    "attraction": [
        "景点", "公园", "博物馆", "古镇", "乐园", "动物园", "植物园", "美术馆",
        "纪念馆", "湿地公园", "温泉", "海洋馆", "寺", "塔", "步行街", "观景台",
        "遗址", "山", "湖", "森林公园", "主题公园", "水上乐园", "科技馆",
        "教堂", "城墙", "峡谷", "瀑布", "草原", "岛", "度假区",
        # 覆盖更多类型：古迹、乡村、展馆、夜景、亲子、演出与自然地貌
        "古迹", "古村", "古城", "石窟", "石刻", "陵墓", "庙", "道观",
        "展览馆", "艺术馆", "图书馆", "剧院", "音乐厅", "城市公园", "湿地",
        "保护区", "农家乐", "采摘园", "滑雪场", "漂流", "温泉度假村",
        "乡村旅游", "夜景", "灯光秀", "美食街", "商业街", "广场",
        "海滩", "沙滩", "江", "河", "溪", "石林", "溶洞", "沙漠", "冰川",
    ],
    "hotel": [
        "酒店", "宾馆", "民宿", "青年旅舍", "度假酒店", "公寓酒店",
        "快捷酒店", "连锁酒店", "商务酒店", "客栈", "三星级酒店",
        "四星级酒店", "五星级酒店",
        # 补充：精品/电竞/亲子/会议/温泉/列车站周边与非标住宿
        "精品酒店", "温泉酒店", "亲子酒店", "电竞酒店", "会议酒店",
        "经济型酒店", "招待所", "度假村", "农家乐住宿", "别墅酒店",
        "火车站附近酒店", "机场附近酒店", "景区附近酒店", "公寓",
    ],
}
CORE_KEYWORDS = {
    "attraction": ["景点", "公园", "博物馆", "古镇", "乐园", "动物园", "植物园",
                   "美术馆", "纪念馆", "湿地公园", "温泉", "海洋馆", "寺", "塔", "观景台"],
    "hotel": ["酒店", "宾馆", "民宿", "青年旅舍", "度假酒店", "公寓酒店"],
}
METRO_KEYWORDS = ["地铁站", "地铁", "地铁口", "换乘站", "1号线", "2号线", "4号线",
                  "5号线", "6号线", "10号线", "13号线", "14号线"]

_TAG_FLAGS = {
    "night": ("夜景", "夜游", "夜市", "灯光秀", "夜场"),
    "indoor": ("博物馆", "美术馆", "纪念馆", "展馆", "海洋馆", "剧院", "科技馆", "艺术馆"),
    "nature": ("公园", "山", "湖", "自然", "森林", "湿地", "瀑布", "峡谷", "草原", "海滩", "岛屿"),
}

_harvest_state: Dict[str, Dict[str, Any]] = {}
_DEEPENING: set = set()
_DEEPEN_AT: Dict[str, float] = {}
_DEEPEN_LOCK = threading.Lock()


# ------------------------------ 图片本地化 ------------------------------

def prune_images() -> Dict[str, int]:
    """删除没有被任何快照引用的本地图片，缓存只保留当前这份数据用到的图。"""
    if not LIVE_IMAGE_DIR.exists():
        return {"removed": 0, "freed_bytes": 0}
    referenced = set()
    for row in cache_store.items("attraction") + cache_store.items("hotel"):
        for key in ("cover_image", "images", "photos"):
            value = row.get(key)
            values = value if isinstance(value, list) else [value]
            for item in values:
                text = str(item or "")
                if LIVE_IMAGE_URL in text:
                    referenced.add(text.rsplit("/", 1)[-1])
    removed = 0
    freed = 0
    for path in LIVE_IMAGE_DIR.glob("*"):
        if not path.is_file() or path.name in referenced:
            continue
        try:
            freed += path.stat().st_size
            path.unlink()
            removed += 1
        except OSError:
            pass
    return {"removed": removed, "freed_bytes": freed}


def _download_image(url: str, timeout: int = 5) -> Optional[str]:
    if not url or not url.startswith("http"):
        return None
    LIVE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.md5(url.encode("utf-8")).hexdigest()
    for ext in (".jpg", ".png", ".webp"):
        candidate = LIVE_IMAGE_DIR / f"{digest}{ext}"
        if candidate.exists():
            return LIVE_IMAGE_URL + candidate.name
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": baidu_web.UA,
            "Referer": "https://map.baidu.com/",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except Exception:
        return None
    if len(data) < 6000:
        return None
    ext = ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = ".webp"
    target = LIVE_IMAGE_DIR / f"{digest}{ext}"
    try:
        target.write_bytes(data)
    except OSError:
        return None
    return LIVE_IMAGE_URL + target.name


def _localize(item: Dict[str, Any], budget: int = 1) -> None:
    urls = [item.get("cover_image")] if item.get("cover_image") else []
    urls += [u for u in (item.get("images") or []) if u]
    saved: List[str] = []
    for url in urls[:budget]:
        local = _download_image(url)
        if local and local not in saved:
            saved.append(local)
    if saved:
        item["cover_image"] = saved[0]
        item["images"] = saved
        item["photos"] = saved
        item["image_localized"] = True


def _localize_many(items: List[Dict[str, Any]], budget: int = 1, limit: int = 6) -> None:
    targets = [row for row in items if not row.get("image_localized")][:limit]
    if not targets:
        return
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(targets))) as pool:
        list(pool.map(lambda row: _localize(row, budget=budget), targets))


# ------------------------------ 归一化 ------------------------------

def _flags(item: Dict[str, Any]) -> None:
    tags = " ".join(item.get("tags") or [])
    item["is_free"] = item.get("price") == 0
    item["night_open"] = any(word in tags for word in _TAG_FLAGS["night"])
    item["indoor"] = any(word in tags for word in _TAG_FLAGS["indoor"])
    item["nature"] = any(word in tags for word in _TAG_FLAGS["nature"])
    item["popularity"] = min(100, int((item.get("review_count") or 0) / 60))


def _finalize(items: List[Dict[str, Any]], kind: str, city: str) -> None:
    for item in items:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        item["city"] = str(item.get("city") or city or "").strip()
        item["key"] = f"{item['city']}::{name}"
        seed = (name + str(item.get("uid") or "")).encode("utf-8")
        item["id"] = item.get("id") or "bw-" + hashlib.md5(seed).hexdigest()[:10]
        item["kind"] = kind
        item.setdefault("tags", [])
        item.setdefault("policy", {})
        item.setdefault("ticket_types", [])
        item.setdefault("offers", [])
        item.setdefault("specs", [])
        item.setdefault("images", [])
        item.setdefault("photos", [])
        item.setdefault("intro_zh", item.get("intro") or "")
        for offer in item.get("offers") or []:
            if isinstance(offer, dict):
                offer.setdefault("note_zh", offer.get("note") or "")
                offer.setdefault("platform_zh", i18n.source_zh(offer.get("platform") or ""))
                for spec in offer.get("specs") or []:
                    if isinstance(spec, dict):
                        spec.setdefault("note_zh", spec.get("note") or "")
                        spec.setdefault("name_zh", spec.get("name") or "")
        if not item.get("intro"):
            if kind == "hotel":
                item["intro"] = item.get("landmark") or "Live data from Baidu Maps"
            else:
                item["intro"] = "Live data from Baidu Maps"
        _flags(item)


def _merge(parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, merged = set(), []
    for item in parts:
        ident = item.get("uid") or (str(item.get("name")), round(item.get("lat") or 0, 3))
        if ident in seen:
            continue
        seen.add(ident)
        merged.append(item)
    return merged


# ------------------------------ 抓取 ------------------------------

def harvest(kind: str, city: str, keywords: Optional[List[str]] = None,
            pages: int = 1, force: bool = False, localize: int = 6,
            code: str = "", scope: Optional[str] = None) -> Dict[str, Any]:
    """抓取一个城市/行政区的某一类数据并写入快照；返回快照统计。

    code 为行政区编码（限定检索范围），scope 为快照归档键（默认取城市名）。
    """
    scope = scope or city or "全国"
    record = cache_store.load(kind, scope)
    age = cache_store.age_seconds(record)
    if record and age is not None and age < CACHE_TTL_SECONDS and not force:
        return {"city": scope, "kind": kind, "source": "cache", "count": int(record.get("count") or 0),
                "fetched_at": record.get("fetched_at"), "age_seconds": int(age), "added": 0}

    words = keywords or CORE_KEYWORDS.get(kind, ["景点"])
    started = time.time()
    rows = baidu_web.search_many(city, words, kind, pages=pages, workers=5, code=code)
    _finalize(rows, kind, city)
    if rows:
        _localize_many(rows, budget=1, limit=localize)
        result = cache_store.save(kind, scope, rows, "baidu_web")
        stats = {"city": scope, "kind": kind, "source": "live", "count": result["count"],
                 "added": result["added"], "fetched_at": result["fetched_at"],
                 "elapsed_ms": int((time.time() - started) * 1000), "rows": len(rows)}
    else:
        stats = {"city": scope, "kind": kind, "source": "cache" if record else "empty",
                 "count": int((record or {}).get("count") or 0),
                 "fetched_at": (record or {}).get("fetched_at", ""),
                 "elapsed_ms": int((time.time() - started) * 1000), "rows": 0}
    _harvest_state[f"{kind}|{scope}"] = dict(stats, at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    return stats


def harvest_async(kind: str, city: str, **kwargs) -> None:
    """后台补抓，避免阻塞当前请求。"""
    def run() -> None:
        try:
            harvest(kind, city, **kwargs)
        except Exception:
            pass

    threading.Thread(target=run, name=f"harvest-{kind}-{city}", daemon=True).start()


def ensure(kind: str, city: str) -> None:
    """保证某城市有可用的实时/缓存数据；已有新鲜快照时直接返回。"""
    if not settings.live_enabled:
        return
    record = cache_store.load(kind, city or "全国")
    age = cache_store.age_seconds(record)
    if record and age is not None and age < CACHE_TTL_SECONDS:
        if city and kind in ("attraction", "hotel"):
            _schedule_deepen(kind, city)
        return
    lock_key = f"{kind}|{city or '全国'}"
    with HARVEST_LOCK:
        if _harvest_state.get(lock_key, {}).get("running"):
            busy = True
        else:
            busy = False
            _harvest_state[lock_key] = dict(_harvest_state.get(lock_key) or {}, running=True)
    if busy:
        # 已有同城市抓取在进行：等它写出一份新鲜快照，避免首屏空白
        for _ in range(40):
            time.sleep(0.5)
            record2 = cache_store.load(kind, city or "全国")
            age2 = cache_store.age_seconds(record2)
            if record2 and age2 is not None and age2 < CACHE_TTL_SECONDS:
                return
        return
    try:
        harvest(kind, city)
    finally:
        _harvest_state.setdefault(lock_key, {})["running"] = False
    if city and kind in ("attraction", "hotel"):
        _schedule_deepen(kind, city)


# ------------------------------ 检索 ------------------------------

def _match_price(item: Dict[str, Any], low: Optional[float], high: Optional[float]) -> bool:
    price = item.get("price")
    if low in (None, "") and high in (None, ""):
        return True
    if price is None:
        return False
    if low not in (None, "") and float(price) < float(low):
        return False
    if high not in (None, "") and float(price) > float(high):
        return False
    return True


def _schedule_deepen(kind: str, city: str) -> None:
    """首屏用少量关键词快速出结果，随后后台补齐全量关键词（不阻塞页面）。"""
    key = f"{kind}|{city}"
    with _DEEPEN_LOCK:
        if key in _DEEPENING:
            return
        last = _DEEPEN_AT.get(key, 0)
        if time.time() - last < 1800:
            return
        _DEEPENING.add(key)
        _DEEPEN_AT[key] = time.time()

    def run() -> None:
        try:
            harvest(kind, city, keywords=KEYWORDS.get(kind), pages=2, force=True, localize=4)
        except Exception:
            pass
        finally:
            with _DEEPEN_LOCK:
                _DEEPENING.discard(key)

    threading.Thread(target=run, name=f"deepen-{kind}-{city}", daemon=True).start()


def search(kind: str, params: Dict[str, Any]) -> Dict[str, Any]:
    city = str(params.get("city") or "").strip()
    keyword = str(params.get("keyword") or "").strip()
    page = max(1, int(params.get("page") or 1))
    size = max(1, min(60, int(params.get("page_size") or 12)))

    if city:
        ensure(kind, city)

    live_rows: List[Dict[str, Any]] = []
    source = "cache"
    fetched_at = ""
    if settings.live_enabled:
        if city and keyword and keyword not in KEYWORDS.get(kind, []):
            # 用户给了具体关键词：直接实时检索，避免只依赖预抓取的通用词
            try:
                live_rows = baidu_web.search(keyword, city, kind, 0, 10)
                _finalize(live_rows, kind, city)
                if live_rows:
                    _localize_many(live_rows, limit=4)
                    cache_store.save(kind, city, live_rows, "baidu_web")
            except Exception:
                live_rows = []
        if keyword and not city:
            try:
                live_rows = baidu_web.search(keyword, "", kind, 0, 10)
                _finalize(live_rows, kind, "")
                if live_rows:
                    cache_store.save(kind, "全国", live_rows, "baidu_web")
            except Exception:
                live_rows = []

    rows = list(live_rows)
    fresh = False
    if not rows:
        if city:
            record = cache_store.load(kind, city)
            rows = list((record or {}).get("items") or [])
            fetched_at = str((record or {}).get("fetched_at") or "")
            age = cache_store.age_seconds(record)
            fresh = bool(record and age is not None and age < CACHE_TTL_SECONDS)
        else:
            rows = cache_store.items(kind)
        source = ("live" if fresh else "cache") if rows else "empty"

    # 城市 + 关键词二次过滤（缓存里可能混入相邻城市结果）
    if city:
        rows = [row for row in rows if baidu_web._match_city(str(row.get("city") or ""), city)]
    if keyword:
        lower = keyword.lower()
        rows = [row for row in rows if lower in str(row.get("name") or "").lower()
                or lower in " ".join(row.get("tags") or []).lower()]

    min_rating = params.get("min_rating")
    min_price = params.get("min_price")
    max_price = params.get("max_price")
    tags = params.get("tags") or []
    level = str(params.get("level") or "")
    free_only = str(params.get("free") or "") in ("1", "true", "yes")
    lat, lng = params.get("lat"), params.get("lng")
    radius = params.get("max_distance")
    min_star = params.get("min_star")
    max_metro = params.get("max_metro")

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        if min_rating and (row.get("rating") or 0) < float(min_rating):
            continue
        if level and row.get("level") != level:
            continue
        if tags and not set(tags) & set(row.get("tags") or []):
            continue
        if free_only and row.get("price") not in (0, 0.0):
            continue
        if not _match_price(row, min_price, max_price):
            continue
        if min_star and int(row.get("star") or 0) < int(min_star):
            continue
        if lat is not None and lng is not None and radius not in (None, ""):
            if row.get("lat") is None:
                continue
            km = haversine_km(float(lat), float(lng), float(row["lat"]), float(row["lng"]))
            row["distance_km"] = round(km, 2)
            if km > float(radius):
                continue
        filtered.append(row)

    if min_star or max_metro:
        _enrich_hotels(filtered, city, max_metro)

    sort = str(params.get("sort") or "")
    if sort == "rating":
        filtered.sort(key=lambda row: -(row.get("rating") or 0))
    elif sort == "price_asc":
        filtered.sort(key=lambda row: (row.get("price") is None, row.get("price") or 0))
    elif sort == "price_desc":
        filtered.sort(key=lambda row: -(row.get("price") or 0))
    elif sort == "distance" and lat is not None:
        filtered.sort(key=lambda row: row.get("distance_km") or 9e9)
    else:
        filtered.sort(key=lambda row: -(row.get("review_count") or 0))

    start = (page - 1) * size
    items = filtered[start:start + size]
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        for row in items:
            if row.get("lat") is not None:
                row["distance_km"] = round(haversine_km(float(lat), float(lng),
                                                        float(row["lat"]), float(row["lng"])), 2)
    if live_rows or fresh:
        label = "Live · Baidu Maps (built-in)"
    elif fetched_at:
        label = "Cached · last fetch " + fetched_at.replace("T", " ")[:16]
    else:
        label = ""
    return {
        "items": items,
        "total": len(filtered),
        "page": page,
        "page_size": size,
        "source": "live" if (live_rows or fresh) else source,
        "source_label": label,
        "fetched_at": fetched_at or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "city": city,
        "keyword": keyword,
    }


def _enrich_hotels(items: List[Dict[str, Any]], city: str, max_metro: Any) -> None:
    if not items:
        return
    rows = metros(city or str(items[0].get("city") or ""))
    for hotel in items:
        if hotel.get("lat") is None:
            continue
        best = None
        for station in rows:
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
    if max_metro not in (None, ""):
        items[:] = [h for h in items if h.get("metro_distance_m") is not None
                    and h["metro_distance_m"] <= int(max_metro)]


# ------------------------------ 详情 ------------------------------

def detail(kind: str, key: str, force: bool = False) -> Optional[Dict[str, Any]]:
    city, _, name = key.partition("::")
    item = cache_store.find(kind, key)
    if item and not force:
        fresh = dict(item)
    else:
        fresh = None
        if settings.live_enabled:
            try:
                fresh = baidu_web.detail(key, city, kind)
            except Exception:
                fresh = None
        if fresh:
            _finalize([fresh], kind, city)
            cache_store.save(kind, city or "全国", [fresh], "baidu_web")
    if not fresh:
        return None
    fresh = dict(fresh)
    if kind == "attraction" and not fresh.get("ticket_types") and fresh.get("specs"):
        fresh["ticket_types"] = [{"name": row.get("name"), "price": row.get("price"),
                                  "note": row.get("note")} for row in fresh["specs"]]
    fresh["source"] = "live" if force or not item else "cache"
    fresh["source_label"] = "Live · Baidu Maps" if fresh["source"] == "live" else "Cached · last fetch"
    fresh["fetched_at"] = fresh.get("fetched_at") or time.strftime("%Y-%m-%dT%H:%M:%S")
    if kind == "attraction":
        fresh["nearby_hotels"] = nearby_hotels(fresh, limit=4)
        fresh["nearest_metro"] = nearest_metro(fresh)
    _localize(fresh, budget=2)
    return fresh


def resolve_anchor(kind: str, key: str) -> Optional[Dict[str, Any]]:
    """快速定位一个参照点（景点/酒店）：先查快照，再用同城检索兜底。

    比 detail() 便宜得多：不做逐条上游详情请求，因此「按景点找周边酒店」
    不会因为一条详情请求卡住十几秒。
    """
    item = cache_store.find(kind, key)
    if item and item.get("lat") is not None:
        return dict(item)
    city, _, name = key.partition("::")
    rows = search(kind, {"city": city, "keyword": name, "page": 1, "page_size": 10}).get("items") or []
    for row in rows:
        if str(row.get("name") or "").strip() == name.strip() and row.get("lat") is not None:
            return dict(row)
    for row in rows:
        if name.strip() and name.strip() in str(row.get("name") or "") and row.get("lat") is not None:
            return dict(row)
    return dict(item) if item else None


def detail_by_id(kind: str, ident: str) -> Optional[Dict[str, Any]]:
    item = cache_store.find(kind, ident)
    return dict(item) if item else None


def nearby_hotels(attraction: Dict[str, Any], limit: int = 4) -> List[Dict[str, Any]]:
    if attraction.get("lat") is None:
        return []
    city = str(attraction.get("city") or "")
    if city:
        ensure("hotel", city)
    rows = cache_store.items("hotel", city) if city else cache_store.items("hotel")
    out = []
    for row in rows:
        if row.get("lat") is None:
            continue
        dist = haversine_km(attraction["lat"], attraction["lng"], row["lat"], row["lng"])
        enriched = dict(row)
        enriched["distance_to_attraction_km"] = round(dist, 2)
        out.append(enriched)
    out.sort(key=lambda row: row["distance_to_attraction_km"])
    return out[:limit]


def nearest_metro(place: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    city = str(place.get("city") or "")
    if place.get("lat") is None or not city:
        return None
    best = None
    for row in metros(city):
        km = haversine_km(place["lat"], place["lng"], row["lat"], row["lng"])
        if best is None or km < best["distance_km"]:
            best = {"name": row["name"], "line": row.get("line", ""), "city": city,
                    "distance_km": round(km, 2), "walk_min": int(round(km * 1000 / 75))}
    if best and best["distance_km"] > 5:
        return None
    return best


def metros(city: str) -> List[Dict[str, Any]]:
    if not city:
        return []
    record = cache_store.load("metro", city)
    age = cache_store.age_seconds(record)
    if record and age is not None and age < 6 * 3600:
        return _dedupe_stations(record.get("items") or [])
    if not settings.live_enabled:
        return _dedupe_stations((record or {}).get("items") or [])
    try:
        rows = baidu_web.search_many(city, METRO_KEYWORDS, "metro", pages=2, workers=2)
    except Exception:
        rows = []
    out, seen = [], set()
    for row in rows:
        if row.get("lat") is None or row["name"] in seen:
            continue
        seen.add(row["name"])
        out.append({"name": row["name"], "city": city, "line": "",
                    "lat": row["lat"], "lng": row["lng"], "uid": row.get("uid", "")})
    # 没有地铁的城市也写一份空快照作为负缓存，避免每次请求都重新抓一遍
    cache_store.save("metro", city, out, "baidu_web")
    return out or _dedupe_stations((record or {}).get("items") or [])


def _dedupe_stations(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for row in rows:
        name = str(row.get("name") or "")
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(row)
    return out


def stats() -> Dict[str, Any]:
    data = cache_store.stats()
    data["live_enabled"] = settings.live_enabled
    data["ttl_seconds"] = CACHE_TTL_SECONDS
    data["harvest"] = list(_harvest_state.values())[-6:]
    return data


def health() -> Dict[str, Any]:
    result = baidu_web.health()
    result["source"] = "baidu_web"
    result["label"] = "Built-in live source (Baidu Maps, no configuration)"
    result["cache"] = cache_store.stats()
    return result