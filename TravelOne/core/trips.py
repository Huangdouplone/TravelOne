# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""行程存储：单个 JSON 文件，不使用数据库。"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
FILE = BASE_DIR / "data" / "trips.json"
_lock = threading.Lock()


def _load() -> Dict[str, Any]:
    if not FILE.exists():
        return {"next_id": 1, "trips": {}}
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"next_id": 1, "trips": {}}


def _save(data: Dict[str, Any]) -> None:
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def create(title: str, city: str = "", start_date: str = "") -> Dict[str, Any]:
    with _lock:
        data = _load()
        trip_id = data["next_id"]
        data["next_id"] = trip_id + 1
        trip = {"id": trip_id, "title": title or "My Trip", "city": city,
                "start_date": start_date, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "items": []}
        data["trips"][str(trip_id)] = trip
        _save(data)
        return trip


def get(trip_id: int) -> Optional[Dict[str, Any]]:
    return _load()["trips"].get(str(trip_id))


def add_item(trip_id: int, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _load()
        trip = data["trips"].get(str(trip_id))
        if not trip:
            return None
        for existing in trip["items"]:
            if existing.get("key") == item.get("key"):
                return trip
        item = dict(item)
        item["id"] = (max([i.get("id", 0) for i in trip["items"]] or [0]) + 1)
        item.setdefault("day", 1)
        trip["items"].append(item)
        _save(data)
        return trip


def remove_item(trip_id: int, item_id: int) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _load()
        trip = data["trips"].get(str(trip_id))
        if not trip:
            return None
        trip["items"] = [i for i in trip["items"] if i.get("id") != item_id]
        _save(data)
        return trip


def update_items(trip_id: int, updates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    with _lock:
        data = _load()
        trip = data["trips"].get(str(trip_id))
        if not trip:
            return None
        index = {i.get("id"): i for i in trip["items"]}
        for upd in updates:
            target = index.get(upd.get("id"))
            if target:
                target["day"] = int(upd.get("day", target.get("day", 1)))
                target["seq"] = int(upd.get("seq", target.get("seq", 0)))
                target["visit_minutes"] = int(upd.get("visit_minutes", target.get("visit_minutes", 120)))
        _save(data)
        return trip
