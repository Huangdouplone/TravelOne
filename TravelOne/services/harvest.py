# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""采集调度：按城市轮转实时抓取景点、酒店与地铁站。

- 默认每 300 秒一轮（COLLECT_INTERVAL_SECONDS 可改）；
- 每轮挑一个城市做完整抓取（景点 19 个检索词 / 酒店 6 个 / 地铁 2 页），
  多城市之间轮转，避免同一时间对上游发太多请求；
- 页面上的「刷新」会立即抓取当前城市，返回本轮真实新增数量；
- 每轮结果写入 core.runs 的 JSON 记录（同样不使用数据库）。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core import runs
from core.config import settings
from services import live

STATE: Dict[str, Any] = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "last_status": "",
    "last_counts": {},
    "interval_seconds": settings.collect_interval_seconds,
    "next_run_at": None,
    "rotation": 0,
    "cities": settings.collect_cities,
}

_RUNNING = threading.Lock()


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _collect_city(city: str, full: bool = True) -> Dict[str, Any]:
    started = time.time()
    parts = {}
    for kind in ("attraction", "hotel"):
        parts[kind] = live.harvest(kind, city, force=True,
                                   keywords=(live.KEYWORDS if full else live.CORE_KEYWORDS).get(kind),
                                   pages=2 if full else 1,
                                   localize=10 if full else 4)
    parts["metro"] = live.harvest("metro", city, keywords=live.METRO_KEYWORDS,
                                  pages=2, force=True, localize=0)
    seen = sum(int(part.get("rows") or 0) for part in parts.values())
    added = sum(int(part.get("added") or 0) for part in parts.values())
    return {
        "status": "ok" if any(part.get("source") == "live" for part in parts.values()) else "degraded",
        "seen": seen,
        "new": added,
        "platforms": {
            "attraction": {"label": "Attractions (Baidu Maps, live)", "status": parts["attraction"].get("source"),
                           "count": parts["attraction"].get("count"), "errors": []},
            "hotel": {"label": "Hotels (Baidu Maps, live rates)", "status": parts["hotel"].get("source"),
                      "count": parts["hotel"].get("count"), "errors": []},
            "metro": {"label": "Metro stations (Baidu Maps, live)", "status": parts["metro"].get("source"),
                      "count": parts["metro"].get("count"), "errors": []},
        },
        "elapsed_ms": int((time.time() - started) * 1000),
    }


def run_collection(trigger: str = "manual", cities: Optional[List[str]] = None,
                   full: bool = True) -> Dict[str, Any]:
    """抓取一批城市；并发调用时后到者直接返回 running。"""
    if not _RUNNING.acquire(blocking=False):
        return {"status": "running", "message": "A fetch is already running"}
    try:
        STATE["running"] = True
        STATE["last_started_at"] = _stamp()
        targets = [c.strip() for c in (cities or []) if c and c.strip()]
        if not targets:
            pool = STATE.get("cities") or settings.collect_cities
            targets = [pool[STATE.get("rotation", 0) % len(pool)]]
            STATE["rotation"] = (STATE.get("rotation", 0) + 1) % len(pool)

        summary: Dict[str, Any] = {"cities": {}, "seen": 0, "new": 0}
        for city in targets:
            result = _collect_city(city, full=full)
            summary["cities"][city] = result
            summary["seen"] += result["seen"]
            summary["new"] += result["new"]

        status = "ok" if any(c["status"] == "ok" for c in summary["cities"].values()) else "degraded"
        finished = _stamp()
        record = {
            "trigger": trigger,
            "started_at": STATE["last_started_at"],
            "finished_at": finished,
            "status": status,
            "cities": targets,
            "items_seen": summary["seen"],
            "items_new": summary["new"],
            "items_updated": max(0, summary["seen"] - summary["new"]),
            "platforms": summary["cities"],
            "cache": live.stats(),
        }
        runs.add(record)
        STATE.update({
            "running": False,
            "last_finished_at": finished,
            "last_status": status,
            "last_counts": {"seen": summary["seen"], "new": summary["new"]},
            "last_cities": targets,
        })
        return dict(record, ok=True)
    finally:
        STATE["running"] = False
        _RUNNING.release()


def start_worker() -> None:
    """启动后台轮转线程（首次启动时先抓默认前两个城市）。"""
    def loop() -> None:
        if settings.collect_on_startup:
            try:
                run_collection("startup", cities=settings.collect_cities[:2], full=False)
            except Exception as exc:
                STATE["last_status"] = f"error: {exc}"
        while True:
            wait = max(30, int(settings.collect_interval_seconds))
            STATE["next_run_at"] = (datetime.now() + timedelta(seconds=wait)).strftime("%Y-%m-%dT%H:%M:%S")
            time.sleep(wait)
            try:
                run_collection("schedule", full=True)
            except Exception as exc:
                STATE["last_status"] = f"error: {exc}"
            finally:
                STATE["next_run_at"] = None

    threading.Thread(target=loop, name="harvest-worker", daemon=True).start()


def status() -> Dict[str, Any]:
    return {
        "state": STATE,
        "interval_seconds": settings.collect_interval_seconds,
        "runs": runs.latest(8),
        "cache": live.stats(),
    }