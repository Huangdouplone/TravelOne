# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""纯文件快照存储（不是数据库）。

- 每个「类型 + 城市」一份 JSON 快照：data/cache/snap_<kind>_<city>.json
- 快照内容是最近一次实时爬取的原始结果，仅用于上游不可达时回放；
- 内存里保留热点快照，读写不依赖任何数据库引擎、SQL 或索引服务；
- 只提供 put / load / items / find / stats / clear 这几个文件级操作。

这样做的目的：项目随包不携带任何预置数据或 .db 文件，第一次启动是空的，
所有景点、酒店、地铁、价格都来自运行时的实时抓取，抓取结果按城市存档。
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "cache"

_lock = threading.Lock()
_memory: Dict[str, Dict[str, Any]] = {}
_merged_cache: Dict[str, tuple] = {}
_MAX_MEMORY = 48
_MERGED_TTL = 30
_MANIFEST_NAME = "manifest.json"
_manifest: Optional[Dict[str, Dict[str, Any]]] = None

_KIND_LABEL = {"attraction": "景点", "hotel": "酒店", "metro": "地铁站"}


def _slug(value: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value or "")
    return (text.strip("_") or "all")[:40] + "-" + hashlib.md5((value or "all").encode("utf-8")).hexdigest()[:6]


def _manifest_path() -> Path:
    return CACHE_DIR / _MANIFEST_NAME


def _load_manifest() -> Dict[str, Dict[str, Any]]:
    """Lightweight index of snapshots so metadata queries never parse every file."""
    global _manifest
    if _manifest is not None:
        return _manifest
    path = _manifest_path()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("entries"), dict):
                _manifest = raw["entries"]
                return _manifest
        except (OSError, ValueError):
            pass
    entries: Dict[str, Dict[str, Any]] = {}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for file in CACHE_DIR.glob("snap_*.json"):
        try:
            record = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        scope = str(record.get("scope") or "")
        kind = str(record.get("kind") or "")
        if not kind or not scope:
            continue
        entries[f"{kind}|{scope}"] = {"kind": kind, "scope": scope,
                                      "count": int(record.get("count") or len(record.get("items") or [])),
                                      "fetched_at": str(record.get("fetched_at") or "")}
    _manifest = entries
    _write_manifest(entries)
    return entries


def _write_manifest(entries: Dict[str, Dict[str, Any]]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _manifest_path().write_text(json.dumps({"entries": entries}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _path(kind: str, scope: str) -> Path:
    return CACHE_DIR / ("snap_%s_%s.json" % (_slug(kind), _slug(scope)))


def _ident(item: Dict[str, Any]) -> str:
    return str(item.get("uid") or item.get("id") or item.get("key") or item.get("name") or "")


def save(kind: str, scope: str, items: Iterable[Dict[str, Any]], source: str = "baidu_web",
         fetched_at: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """把本轮抓取结果并入该城市快照（同一条目更新字段，不重复堆叠）。"""
    stamp = fetched_at or time.strftime("%Y-%m-%dT%H:%M:%S")
    record = load(kind, scope) or {"kind": kind, "scope": scope, "items": []}
    index = {_ident(row): i for i, row in enumerate(record.get("items") or [])}
    merged = list(record.get("items") or [])
    added = 0
    derived = ("metro_station", "metro_distance_m", "metro_walk_min",
               "distance_to_attraction_km", "distance_km")
    for item in items:
        if not isinstance(item, dict):
            continue
        ident = _ident(item)
        if not ident:
            continue
        item = {k: v for k, v in item.items() if k not in derived}
        item["fetched_at"] = stamp
        if ident in index:
            target = merged[index[ident]]
            if not item.get("image_localized") and target.get("image_localized"):
                for key in ("cover_image", "images", "photos", "image_localized"):
                    if target.get(key):
                        item[key] = target[key]
            target.update(item)
            target["fetched_at"] = stamp
        else:
            index[ident] = len(merged)
            merged.append(item)
            added += 1
    payload = {
        "kind": kind,
        "scope": scope,
        "source": source,
        "fetched_at": stamp,
        "count": len(merged),
        "items": merged,
    }
    if extra:
        payload.update(extra)
    with _lock:
        _merged_cache.pop(kind, None)
        _memory[f"{kind}|{scope}"] = payload
        if len(_memory) > _MAX_MEMORY:
            oldest = min(_memory.items(), key=lambda kv: str(kv[1].get("fetched_at") or ""))[0]
            _memory.pop(oldest, None)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _path(kind, scope).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        entries = _load_manifest()
        entries[f"{kind}|{scope}"] = {"kind": kind, "scope": scope,
                                      "count": len(merged), "fetched_at": stamp}
        _write_manifest(entries)
    except OSError:
        pass
    # 每次写入后（限频）把同城的旧快照与残留文件清掉，缓存只留最近一次
    try:
        prune()
    except Exception:
        pass
    return {"count": len(merged), "added": added, "fetched_at": stamp}


def load(kind: str, scope: str) -> Optional[Dict[str, Any]]:
    key = f"{kind}|{scope}"
    with _lock:
        if key in _memory:
            return _memory[key]
    path = _path(kind, scope)
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    with _lock:
        _memory[key] = record
    return record


def age_seconds(record: Optional[Dict[str, Any]]) -> Optional[float]:
    if not record or not record.get("fetched_at"):
        return None
    try:
        from datetime import datetime
        return (datetime.now() - datetime.fromisoformat(str(record["fetched_at"]))).total_seconds()
    except (ValueError, TypeError):
        return None


def items(kind: str, scope: str = "") -> List[Dict[str, Any]]:
    """读取快照条目；scope 为空时合并所有城市快照并按条目去重。"""
    if scope:
        record = load(kind, scope)
        return list((record or {}).get("items") or [])
    with _lock:
        cached = _merged_cache.get(kind)
        if cached and time.time() - cached[0] < _MERGED_TTL:
            return list(cached[1])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    seen = set()
    out: List[Dict[str, Any]] = []
    pattern = "snap_%s_*.json" % _slug(kind)
    for path in sorted(CACHE_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for item in record.get("items") or []:
            if not isinstance(item, dict):
                continue
            ident = _ident(item)
            if not ident or ident in seen:
                continue
            seen.add(ident)
            out.append(item)
    with _lock:
        _merged_cache[kind] = (time.time(), out)
    return list(out)


def find(kind: str, needle: str) -> Optional[Dict[str, Any]]:
    """按 id / key / uid / 名称反查单条。"""
    if not needle:
        return None
    target = needle.strip()
    name = target.split("::")[-1].strip()
    for item in items(kind):
        if target in (str(item.get("id")), str(item.get("uid")), str(item.get("key"))):
            return item
    for item in items(kind):
        if name and str(item.get("name")) == name:
            return item
    for item in items(kind):
        if name and name in str(item.get("name") or ""):
            return item
    return None


def stats() -> Dict[str, Any]:
    """Fast stats from the snapshot manifest (no per-file parsing)."""
    entries = _load_manifest()
    by_kind: Dict[str, int] = {}
    cities: Dict[str, set] = {}
    latest = ""
    for entry in entries.values():
        kind = str(entry.get("kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + int(entry.get("count") or 0)
        scope = str(entry.get("scope") or "")
        if scope:
            cities.setdefault(kind, set()).add(scope)
        latest = max(latest, str(entry.get("fetched_at") or ""))
    return {
        "snapshots": len(entries),
        "by_kind": by_kind,
        "scope_counts": dict(by_kind),
        "cities": {kind: len(pool) for kind, pool in cities.items()},
        "last_fetched_at": latest,
        "memory_entries": len(_memory),
        "storage": "json-snapshot",
    }


def clear(kind: str = "") -> int:
    with _lock:
        if kind:
            _merged_cache.pop(kind, None)
        else:
            _merged_cache.clear()
        if kind:
            for key in [k for k, v in _memory.items() if v.get("kind") == kind]:
                _memory.pop(key, None)
        else:
            _memory.clear()
    removed = 0
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pattern = ("snap_%s_*.json" % _slug(kind)) if kind else "snap_*.json"
    for path in list(CACHE_DIR.glob(pattern)):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    global _manifest
    _manifest = None
    try:
        _manifest_path().unlink()
    except OSError:
        pass
    _load_manifest()
    return removed


_PRUNE_INTERVAL = 90
_last_prune = 0.0
_CITY_SUFFIXES = ("特别行政区", "地区", "自治州", "盟", "市", "县", "区")


def _city_key(scope: str) -> str:
    text = str(scope or "").strip()
    for suffix in _CITY_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            return text[: -len(suffix)]
    return text or "all"


def prune(force: bool = False) -> Dict[str, int]:
    """只保留每个「类型 + 城市」最近一次拉取的快照，其余自动销毁。

    - 同一城市的不同写法（七台河 / 七台河市）只留最新的一份；
    - manifest 里没有记录的残留文件一并删除；
    - 返回删除的文件数与释放的字节数。
    """
    global _manifest, _last_prune
    if not force and time.time() - _last_prune < _PRUNE_INTERVAL:
        return {"removed": 0, "freed_bytes": 0}
    _last_prune = time.time()
    entries = _load_manifest()
    groups: Dict[str, List[str]] = {}
    for key, entry in entries.items():
        groups.setdefault(f"{entry.get('kind')}|{_city_key(entry.get('scope') or '')}", []).append(key)
    removed = 0
    freed = 0
    keep: Dict[str, Dict[str, Any]] = {}
    for keys in groups.values():
        def _rank(key: str):
            entry = entries[key]
            path = _path(str(entry.get("kind") or ""), str(entry.get("scope") or ""))
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            return (str(entry.get("fetched_at") or ""), mtime)

        keys.sort(key=_rank, reverse=True)
        keep[keys[0]] = entries[keys[0]]
        for stale in keys[1:]:
            entry = entries.get(stale) or {}
            path = _path(str(entry.get("kind") or ""), str(entry.get("scope") or ""))
            try:
                freed += path.stat().st_size
                path.unlink()
                removed += 1
            except OSError:
                pass
    expected = {_path(str(e.get("kind") or ""), str(e.get("scope") or "")).name for e in keep.values()}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for path in CACHE_DIR.glob("snap_*.json"):
        if path.name in expected or path.name == _MANIFEST_NAME:
            continue
        try:
            freed += path.stat().st_size
            path.unlink()
            removed += 1
        except OSError:
            pass
    if removed:
        _manifest = keep
        _write_manifest(keep)
        with _lock:
            _merged_cache.clear()
            for key in [k for k in _memory if k.split("|")[0] and k not in keep]:
                _memory.pop(key, None)
    return {"removed": removed, "freed_bytes": freed}


def scopes(kind: str) -> List[str]:
    entries = _load_manifest()
    return [str(entry.get("scope")) for entry in entries.values()
            if entry.get("kind") == kind and entry.get("scope")]