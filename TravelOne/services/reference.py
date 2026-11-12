# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""官方参考层：把 Wikidata 的世界遗产名录匹配到本地景点上。

用途有限但可靠：给详情页加「世界遗产」标签与官方英文名，并在页面标注来源与许可。
数据是名录（静态属性），不是价格；同名但相距过远的条目不采用，避免张冠李戴。
"""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from collectors import wikidata
from core import cache_store

CACHE_FILE: Path = cache_store.CACHE_DIR / "ref_wikidata_heritage.json"
TTL_SECONDS = 7 * 24 * 3600
_STATE: Dict[str, Any] = {"items": None, "fetched_at": 0, "stale": False, "error": ""}

# 匹配时去掉的通用后缀，避免「鼓浪屿」对不上「鼓浪屿风景名胜区」
_SUFFIX = ("国家重点风景名胜区", "风景名胜区", "旅游景区", "旅游度假区", "旅游区", "风景区",
           "游览区", "名胜区", "度假区", "遗址公园", "考古遗址", "博物院", "博物馆",
           "遗址", "景区", "公园")
_PUNCT = re.compile(r"[\s·•\-—_,，。.、()（）\[\]【】\"'“”‘’/\\]+")

# Wikidata 的部分中文标签是繁体（港澳台与老条目），做一次常用字转换，
# 只用于匹配与展示，不改动上游数据本身。
_TRAD = str.maketrans(
    "觀宮瀋慶門樓園館陽東華龍灣濟寧廣臺縣鎮遺產聖廟橋島嶼巖頂頭區國學藝術畫錦麗豐興業樂賞車場際鐵絲綢灣",
    "观宫沈庆门楼园馆阳东华龙湾济宁广台县镇遗产圣庙桥岛屿岩顶头区国学艺术画锦丽丰兴业乐赏车场际铁丝绸湾",
)


def _simp(value: str) -> str:
    return str(value or "").translate(_TRAD)


def _norm(value: str) -> str:
    text = _PUNCT.sub("", _simp(value)).lower()
    changed = True
    while changed:
        changed = False
        for suffix in _SUFFIX:
            if len(text) > len(suffix) + 1 and text.endswith(suffix):
                text = text[: -len(suffix)]
                changed = True
    return text


def _distance_km(lat1: Optional[float], lng1: Optional[float],
                 lat2: Optional[float], lng2: Optional[float]) -> Optional[float]:
    if None in (lat1, lng1, lat2, lng2):
        return None
    try:
        rlat1, rlng1, rlat2, rlng2 = map(math.radians, (lat1, lng1, lat2, lng2))
        dlat, dlng = rlat2 - rlat1, rlng2 - rlng1
        a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
        return round(2 * 6371 * math.asin(math.sqrt(a)), 2)
    except Exception:
        return None


def _read_cache() -> Dict[str, Any]:
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_cache(items: List[Dict[str, Any]]) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {"fetched_at": int(time.time()), "source": wikidata.SOURCE, "items": items}
        with CACHE_FILE.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
    except Exception:
        pass


def heritage(refresh: bool = False, allow_fetch: bool = True) -> Dict[str, Any]:
    """返回 {items, fetched_at, stale, meta}；先内存，再本地快照，最后才联网。

    allow_fetch=False 时只读内存/快照，绝不联网——详情页与数据源面板走这条路径，
    避免首次打开页面被上游延迟卡住；名录由启动时的后台预热或 /api/reference 主动拉取。
    """
    now = int(time.time())
    if not refresh and _STATE["items"] and now - int(_STATE["fetched_at"] or 0) < TTL_SECONDS:
        return _bundle(_STATE["items"], _STATE["fetched_at"], False, "")

    cached = _read_cache()
    cached_items = cached.get("items") if isinstance(cached.get("items"), list) else []
    cached_at = int(cached.get("fetched_at") or 0)
    fresh = cached_items and now - cached_at < TTL_SECONDS

    if fresh and not refresh:
        _STATE.update({"items": cached_items, "fetched_at": cached_at, "stale": False, "error": ""})
        return _bundle(cached_items, cached_at, False, "")

    if not allow_fetch:
        # 不联网：有快照就用快照（过期的标记 stale），没有就报 warming
        if cached_items:
            return _bundle(cached_items, cached_at, True, "Snapshot is older than the refresh window")
        return _bundle([], 0, True, "warming")

    items = wikidata.heritage()
    if items:
        _write_cache(items)
        _STATE.update({"items": items, "fetched_at": now, "stale": False, "error": ""})
        return _bundle(items, now, False, "")

    # 联网失败：有快照就用快照，并如实标记 stale
    error = "Wikidata endpoint unreachable"
    if cached_items:
        _STATE.update({"items": cached_items, "fetched_at": cached_at, "stale": True, "error": error})
        return _bundle(cached_items, cached_at, True, error)
    _STATE.update({"items": [], "fetched_at": 0, "stale": True, "error": error})
    return _bundle([], 0, True, error)


def _bundle(items: List[Dict[str, Any]], fetched_at: int, stale: bool, error: str) -> Dict[str, Any]:
    items = [dict(entry,
                  name_zh=_simp(entry.get("name_zh") or ""),
                  aliases=[_simp(a) for a in (entry.get("aliases") or [])])
             for entry in items]
    meta = {
        "name": wikidata.SOURCE["name"],
        "label": wikidata.SOURCE["label"],
        "license": wikidata.SOURCE["license"],
        "source_url": wikidata.SOURCE["source_url"],
        "note": wikidata.SOURCE["note"],
        "count": len(items),
        "fetched_at": _iso(fetched_at),
        "stale": stale,
        "error": error,
    }
    return {"items": items, "meta": meta, "fetched_at": fetched_at}


def _iso(stamp: int) -> str:
    if not stamp:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))


def match(item: Dict[str, Any], items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """按名称匹配世界遗产条目；有坐标时再用距离校验，避免同名异地。"""
    if not isinstance(item, dict) or not items:
        return None
    names = [_norm(item.get(k) or "") for k in ("name", "name_zh")]
    names = [n for n in names if len(n) >= 2]
    if not names:
        return None
    best = None
    for entry in items:
        primary_zh = _norm(entry.get("name_zh") or "")
        raw_targets = [primary_zh, _norm(entry.get("name_en") or "")]
        raw_targets += [_norm(a) for a in (entry.get("aliases") or [])]
        targets = [t for t in raw_targets if len(t) >= 2]
        hit = 0
        tight_alias = False
        for name in names:
            for index, target in enumerate(targets):
                if name == target:
                    hit = max(hit, 3 if target == primary_zh else 2)
                elif len(name) >= 2 and len(target) >= 2 and name in target:
                    # 只认「景点名是遗产名的一部分」（如鼓浪屿 ⊂ 鼓浪屿风景名胜区），
                    # 反向（遗产名只是景点名的一段，如「厦门鼓浪屿钢琴码头」）不算，避免把码头、店铺标成遗产
                    # 两字名（如「西湖」「故宫」）只在包含关系足够明确时才算命中
                    if len(name) >= 3 or len(target) - len(name) <= 6 or target.startswith(name):
                        hit = max(hit, 1)
                        # 命中条目别名且长度接近，说明就是同一处（如「故宫」对「明清故宫」）
                        if index >= 2 and len(target) - len(name) <= 4:
                            tight_alias = True
        if not hit:
            continue
        distance = _distance_km(item.get("lat"), item.get("lng"), entry.get("lat"), entry.get("lng"))
        if distance is not None and distance > 8 and not tight_alias:
            # 同名但相距 8 km 以上，基本不是同一处，放弃
            continue
        score = (hit, -(distance if distance is not None else 99))
        if best is None or score > best[0]:
            best = (score, entry, distance)
    if not best:
        return None
    _, entry, distance = best
    serial = bool(distance and distance > 20)
    return {
        "qid": entry.get("qid"),
        "name_zh": entry.get("name_zh") or "",
        "name_en": entry.get("name_en") or "",
        "site": entry.get("site") or "",
        # 组合项目（如北京+沈阳的明清皇家宫殿）坐标只取其中一处，不展示距离避免误导
        "distance_km": None if serial else distance,
        "serial_site": serial,
        "source": "wikidata",
        "license": entry.get("license") or wikidata.SOURCE["license"],
        "source_url": wikidata.SOURCE["source_url"],
        "label": "UNESCO World Heritage",
    }


def enrich(item: Dict[str, Any]) -> Dict[str, Any]:
    """给景点详情挂上官方参考字段；无匹配则原样返回。"""
    if not isinstance(item, dict):
        return item
    bundle = heritage(allow_fetch=False)
    hit = match(item, bundle.get("items") or [])
    if not hit:
        return item
    enriched = dict(item)
    enriched["heritage"] = hit
    enriched["name_en_official"] = hit.get("name_en") or ""
    return enriched


def summary() -> Dict[str, Any]:
    bundle = heritage(allow_fetch=False)
    meta = dict(bundle.get("meta") or {})
    labels = []
    for entry in (bundle.get("items") or [])[:400]:
        if entry.get("name_zh"):
            labels.append(entry["name_zh"])
    meta["sample"] = labels[:6]
    return meta