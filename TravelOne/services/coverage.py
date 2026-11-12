# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""全网动态覆盖：运行时发现行政区点位，并按编码持续轮扫景点与酒店。

不依赖任何地点清单文件：
1. 发现：用百度联想接口按拼音音节/省名检索，得到「名称 + 行政区编码」，
   写入运行时注册表 data/registry/places.json（运行时产物，不随包分发）；
2. 覆盖：按注册表轮扫，每次用行政区编码限定范围抓取景点/酒店/地铁，
   结果写入城市快照，按 uid 全局去重；
3. 跟踪：注册表记录每个点位最近扫描时间与条数，新点位随时加入队列，
   已有点位到龄后自动重扫，形成持续的全网跟踪。

对外状态：/api/coverage 返回已发现点位、已覆盖点位、跟踪条数、当前扫描对象与进度。
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from collectors import baidu_web
from core import cache_store
from core.config import BASE_DIR, settings
from services import live

REGISTRY_FILE = Path(BASE_DIR) / "data" / "registry" / "places.json"
_LOCK = threading.RLock()
_STATE: Dict[str, Any] = {"running": False, "phase": "idle", "current": "", "last_error": ""}
_LAST_DISCOVERY = 0.0
DISCOVERY_BATCH = 16
RESCAN_AFTER_SECONDS = 6 * 3600

PROVINCES = [
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区", "辽宁省", "吉林省",
    "黑龙江省", "上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省",
    "山东省", "河南省", "湖北省", "湖南省", "广东省", "广西壮族自治区", "海南省",
    "重庆市", "四川省", "贵州省", "云南省", "西藏自治区", "陕西省", "甘肃省",
    "青海省", "宁夏回族自治区", "新疆维吾尔自治区", "香港特别行政区",
    "澳门特别行政区", "台湾省",
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _load() -> Dict[str, Any]:
    if REGISTRY_FILE.exists():
        try:
            data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("places"), dict):
                return data
        except (OSError, ValueError):
            pass
    return {"places": {}, "discovery": {"cursor": 0, "rounds": 0, "last_at": ""},
            "sweep": {"scans": 0, "last_at": ""}}


_REGISTRY: Dict[str, Any] = _load()


def _save() -> None:
    try:
        REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_FILE.write_text(json.dumps(_REGISTRY, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def add_places(rows: List[Dict[str, Any]]) -> int:
    """把发现的点位加入注册表；返回新增数量。"""
    added = 0
    changed = False
    stamp = _now()
    with _LOCK:
        places = _REGISTRY.setdefault("places", {})
        for row in rows:
            code = str(row.get("code") or "")
            name = str(row.get("name") or "").strip()
            if not code or not name:
                continue
            province = str(row.get("province") or "")
            # 港澳的行政建制是「堂区 / 区」，统一按城市粒度入库与展示
            if province in ("澳门特别行政区", "香港特别行政区"):
                name = "澳门" if province.startswith("澳门") else "香港"
                row = dict(row, name=name, level="city", city=name, province=province)
            if code in places:
                existing = places[code]
                existing["last_seen"] = stamp
                # 同一编码下区县先入库时，用地级市名升级，保证按城市粒度扫描
                if row.get("level") == "city" and existing.get("level") != "city":
                    existing["name"] = name
                    existing["level"] = "city"
                    existing["city"] = row.get("city") or name
                    existing["province"] = row.get("province") or existing.get("province") or ""
                    changed = True
                continue
            places[code] = {
                "code": code,
                "name": name,
                "province": row.get("province") or "",
                "city": row.get("city") or name,
                "level": row.get("level") or "county",
                "first_seen": stamp,
                "last_seen": stamp,
                "last_scan": "",
                "attractions": 0,
                "hotels": 0,
                "metros": 0,
            }
            added += 1
            changed = True
    if changed:
        _save()
    return added


SEED_ALIASES = {
    "澳门": ["澳门 堂区"],
    "香港": ["香港 区"],
    "台北": ["台北"],
    "高雄": ["高雄"],
    "台中": ["台中"],
    "花莲": ["花莲"],
}


def seed_cities() -> int:
    """把配置城市清单里尚未入库的地级市一次性点名发现，避免拼音游标太慢漏城市。"""
    try:
        from core.cities import CITIES as ALL_CITIES
    except Exception:
        ALL_CITIES = []
    names = set()
    for place in _REGISTRY.get("places", {}).values():
        names.add(str(place.get("name") or ""))
    missing: List[str] = []
    for city in list(settings.collect_cities) + list(ALL_CITIES):
        if any(city in name for name in names):
            continue
        missing.extend(SEED_ALIASES.get(city, [city]))
    if not missing:
        return 0
    added = 0
    for start in range(0, min(len(missing), 360), 90):
        chunk = missing[start:start + 90]
        rows = baidu_web.discover_places(chunk, workers=8)
        added += add_places(rows)
    return added


def bootstrap(seeds: Optional[List[str]] = None) -> None:
    """确保注册表里有初始点位：把配置中的城市解析成行政区编码。"""
    if _REGISTRY.get("places"):
        return
    names = seeds or settings.collect_cities
    rows = baidu_web.discover_places(names, workers=4)
    if not rows:
        rows = [{"name": name, "code": "", "province": "", "city": name, "level": "city"}
                for name in names]
    add_places(rows)


def _discovery_terms() -> List[str]:
    """发现词：拼音音节 + 省名 + 省名×行政区后缀 + 城市名。

    省名加后缀能把「地区 / 自治州 / 盟 / 县」这类非「市」建制拉进来，
    城市名（配置项，不是数据）保证每个地级市都至少被点名一次。
    """
    terms: List[str] = list(baidu_web.PINYIN_SYLLABLES)
    for province in PROVINCES:
        terms.append(province)
        for suffix in ("市", "地区", "自治州", "盟", "县"):
            terms.append(f"{province} {suffix}")
    for city in settings.collect_cities:
        terms.append(city)
    # 配置中的旅游城市清单（config，不是数据）逐个点名，保证不漏掉任何地级市
    try:
        from core.cities import CITIES as ALL_CITIES
        terms.extend(ALL_CITIES)
    except Exception:
        pass
    # 港澳的行政建制不是「市」，单独补发现词（台湾省上游无行政区编码，仅能按名称检索）
    terms.extend(["澳门 堂区", "澳门 半岛", "香港 区", "香港 新界", "香港 九龙"])
    seen, unique = set(), []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        unique.append(term)
    return unique


def discover_batch(size: int = DISCOVERY_BATCH) -> int:
    """按游标发现下一批点位（跑完一轮后继续下一轮，持续发现）。"""
    global _LAST_DISCOVERY, _REGISTRY
    if time.time() - _LAST_DISCOVERY < 20:
        return 0
    _LAST_DISCOVERY = time.time()
    terms = _discovery_terms()
    with _LOCK:
        cursor = int(_REGISTRY.get("discovery", {}).get("cursor", 0)) % max(1, len(terms))
        batch = [terms[(cursor + i) % len(terms)] for i in range(max(1, min(size, len(terms))))]
        _REGISTRY.setdefault("discovery", {})["cursor"] = (cursor + len(batch)) % len(terms)
        if cursor + len(batch) >= len(terms):
            _REGISTRY["discovery"]["rounds"] = int(_REGISTRY["discovery"].get("rounds", 0)) + 1
        _REGISTRY["discovery"]["last_at"] = _now()
    rows = baidu_web.discover_places(batch, workers=6)
    added = add_places(rows)
    _save()
    return added


def place_names() -> List[str]:
    """注册表里的点位名（用于判断一个查询词是不是地名）。"""
    names = []
    for place in _REGISTRY.get("places", {}).values():
        name = str(place.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def _next_place() -> Optional[Dict[str, Any]]:
    places = list(_REGISTRY.get("places", {}).values())
    if not places:
        return None
    unscanned = [p for p in places if not p.get("last_scan")]
    if unscanned:
        # 城市优先于区县，保证「城市级」覆盖先成形
        unscanned.sort(key=lambda p: (0 if p.get("level") == "city" else 1, p.get("name") or ""))
        return unscanned[0]
    stale = sorted(places, key=lambda p: p.get("last_scan") or "")
    return stale[0]


def _scan(place: Dict[str, Any], deep: bool = False) -> Dict[str, Any]:
    code = str(place.get("code") or "")
    name = str(place.get("name") or "")
    scope = name if place.get("level") == "city" else f"{name}#{code}"
    stats = {}
    shelf = live.KEYWORDS if deep else live.CORE_KEYWORDS
    for kind in ("attraction", "hotel"):
        result = live.harvest(kind, name, keywords=shelf.get(kind),
                              pages=1, force=True, localize=2, code=code, scope=scope)
        record = cache_store.load(kind, scope) or {}
        items = record.get("items") or []
        stats[kind] = {
            "count": len(items),
            "priced": sum(1 for item in items if item.get("price") is not None),
            "source": result.get("source"),
        }
    metro = live.harvest("metro", name, keywords=live.METRO_KEYWORDS[:4], pages=1,
                         force=True, localize=0, code=code, scope=name)
    stats["metro"] = {"count": int(metro.get("count") or 0), "priced": 0, "source": metro.get("source")}
    return stats


def tick() -> Dict[str, Any]:
    """一次调度：优先补齐未发现的点位，再扫描一个点位。"""
    if _STATE.get("running"):
        return dict(_STATE)
    _STATE["running"] = True
    try:
        bootstrap()
        if time.time() - _STATE.get("seeded_at", 0) > 1800:
            _STATE["seeded_at"] = time.time()
            try:
                seed_cities()
            except Exception:
                pass
        added = discover_batch()
        place = _next_place()
        if not place:
            _STATE.update({"phase": "discovering", "current": "", "last_error": ""})
            return {"added": added, "phase": "discovering"}
        deep = int(place.get("deep_passes") or 0) >= 1
        _STATE.update({"phase": "scanning", "current": f"{place['name']} ({place['code']})"})
        stats = _scan(place, deep=deep)
        with _LOCK:
            target = _REGISTRY["places"].get(str(place["code"]), {})
            target["last_scan"] = _now()
            target["attractions"] = stats["attraction"]["count"]
            target["hotels"] = stats["hotel"]["count"]
            target["metros"] = stats["metro"]["count"]
            target["deep_passes"] = int(target.get("deep_passes") or 0) + (1 if deep else 0)
            _REGISTRY.setdefault("sweep", {})["scans"] = int(_REGISTRY["sweep"].get("scans", 0)) + 1
            scans = int(_REGISTRY["sweep"]["scans"])
            if scans % 40 == 0:
                try:
                    cache_store.prune(force=True)
                    live.prune_images()
                except Exception:
                    pass
            _REGISTRY["sweep"]["last_at"] = target["last_scan"]
            _save()
        _STATE.update({"phase": "idle", "current": "", "last_error": ""})
        return {"added": added, "place": place["name"], "stats": stats}
    except Exception as exc:  # 网络异常不终止覆盖
        _STATE.update({"phase": "error", "last_error": f"{type(exc).__name__}: {exc}"})
        return {"error": _STATE["last_error"]}
    finally:
        _STATE["running"] = False


def summary() -> Dict[str, Any]:
    """Fast counters for the main page: registry sums, no snapshot merging."""
    places = list(_REGISTRY.get("places", {}).values())
    scanned = [p for p in places if p.get("last_scan")]
    stats = cache_store.stats().get("by_kind", {})
    return {
        "places_discovered": len(places),
        "places_scanned": len(scanned),
        "progress": round(len(scanned) / len(places), 4) if places else 0.0,
        "sweeps": int(_REGISTRY.get("sweep", {}).get("scans", 0)),
        "discovery_rounds": int(_REGISTRY.get("discovery", {}).get("rounds", 0)),
        "tracked": {
            "attractions": sum(int(p.get("attractions") or 0) for p in places),
            "hotels": sum(int(p.get("hotels") or 0) for p in places),
            "metros": stats.get("metro", 0),
        },
        "mode": "dynamic-national-coverage",
    }


def state() -> Dict[str, Any]:
    places = list(_REGISTRY.get("places", {}).values())
    scanned = [p for p in places if p.get("last_scan")]
    stats = cache_store.stats()
    total_items = stats.get("by_kind", {})
    attraction_rows = cache_store.items("attraction")
    hotel_rows = cache_store.items("hotel")
    unique_attractions = len(attraction_rows)
    unique_hotels = len(hotel_rows)
    price_attractions = sum(1 for item in attraction_rows if item.get("price") is not None)
    price_hotels = sum(1 for item in hotel_rows if item.get("price") is not None)
    return {
        "places_discovered": len(places),
        "places_scanned": len(scanned),
        "city_level": sum(1 for p in places if p.get("level") == "city"),
        "county_level": sum(1 for p in places if p.get("level") != "city"),
        "sweeps": int(_REGISTRY.get("sweep", {}).get("scans", 0)),
        "last_scan_at": _REGISTRY.get("sweep", {}).get("last_at", ""),
        "discovery_rounds": int(_REGISTRY.get("discovery", {}).get("rounds", 0)),
        "discovery_cursor": int(_REGISTRY.get("discovery", {}).get("cursor", 0)),
        "progress": round(len(scanned) / len(places), 4) if places else 0.0,
        "tracked": {"attractions": unique_attractions, "hotels": unique_hotels,
                    "metros": total_items.get("metro", 0)},
        "priced": {"attractions": price_attractions, "hotels": price_hotels},
        "current": _STATE.get("current", ""),
        "phase": _STATE.get("phase", "idle"),
        "running": bool(_STATE.get("running")),
        "last_error": _STATE.get("last_error", ""),
        "mode": "dynamic-national-coverage",
    }


def top_places(limit: int = 12) -> List[Dict[str, Any]]:
    """按已跟踪条数排序的点位，用于页面的城市筛选。"""
    places = list(_REGISTRY.get("places", {}).values())
    places.sort(key=lambda p: (p.get("attractions") or 0) + (p.get("hotels") or 0), reverse=True)
    return [{"city": p.get("name"), "code": p.get("code"), "count": p.get("attractions") or 0,
             "hotels": p.get("hotels") or 0} for p in places[:limit] if p.get("last_scan")]


def start_worker() -> None:
    """启动覆盖线程：首屏先抓两个种子城市，然后持续发现 + 轮扫。"""

    def loop() -> None:
        try:
            bootstrap()
            try:
                seed_cities()
            except Exception as exc:
                _STATE.update({"last_error": f"seed: {type(exc).__name__}: {exc}"})
            seeds = [p for p in _REGISTRY.get("places", {}).values() if p.get("level") == "city"][:2]
            for place in seeds:
                stats = _scan(place)
                with _LOCK:
                    target = _REGISTRY["places"].get(str(place["code"]), {})
                    target["last_scan"] = _now()
                    target["attractions"] = stats["attraction"]["count"]
                    target["hotels"] = stats["hotel"]["count"]
                    target["metros"] = stats["metro"]["count"]
                    _save()
        except Exception as exc:
            _STATE.update({"last_error": f"startup: {type(exc).__name__}: {exc}"})
        while True:
            try:
                tick()
            except Exception as exc:
                _STATE.update({"last_error": f"{type(exc).__name__}: {exc}"})
            time.sleep(2)

    threading.Thread(target=loop, name="coverage-worker", daemon=True).start()


def manual_scan(city: str) -> Dict[str, Any]:
    """用户手动刷新某城市：不依赖注册表，直接按名称抓取并记入注册表。"""
    rows = baidu_web.discover_places([city], workers=1)
    add_places(rows)
    result = live.harvest("attraction", city, keywords=live.KEYWORDS["attraction"],
                          pages=2, force=True, localize=6)
    hotel = live.harvest("hotel", city, keywords=live.KEYWORDS["hotel"],
                         pages=2, force=True, localize=4)
    # 手动扫描同样写回注册表，让页面城市列表与覆盖统计反映真实数据
    with _LOCK:
        hits = [p for p in _REGISTRY.get("places", {}).values()
                if str(p.get("name") or "") == city or city in str(p.get("name") or "")]
        for place in hits or []:
            place["last_scan"] = _now()
            place["attractions"] = int(result.get("count") or 0)
            place["hotels"] = int(hotel.get("count") or 0)
            place["metros"] = int(place.get("metros") or 0)
        _save()
    return {"city": city, "attraction": result, "hotel": hotel}