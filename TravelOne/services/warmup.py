# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""服务启动后的持续预热抓取。

解决的问题：新开系统时缓存是空的，页面只能拿到启动那一刻抓到的少量数据，
不点“刷新”的话可用内容很少。

做法：服务启动即在后台启动一个常驻线程，按城市队列（省会和直辖市优先，
再接 core.cities 的全国城市清单）不间断地抓景点/酒店/地铁，写回 data/cache。
- 不阻塞 HTTP 请求：使用独立线程，并把单城抓取控制在数十秒；
- 有节奏地让路：与手动“刷新”/覆盖轮扫互斥，检测到正在抓取时先等待；
- 失败重试：单类抓取失败会重试一次，仍失败则记错误并在下一轮再试；
- 可观测：/api/warmup 暴露进度（当前城市、已完成城市数、本轮累计新增）。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List

from core.cities import CITIES
from core.config import BASE_DIR

PRIORITY = [
    "北京", "上海", "广州", "深圳", "成都", "重庆", "杭州", "西安",
    "南京", "武汉", "天津", "长沙", "苏州", "青岛", "厦门", "昆明",
    "郑州", "济南", "沈阳", "哈尔滨", "长春", "合肥", "福州", "南昌",
    "石家庄", "太原", "呼和浩特", "南宁", "海口", "贵阳", "拉萨",
    "兰州", "西宁", "银川", "乌鲁木齐",
]
FORCE_REFRESH_FIRST = 6      # 每次启动先强刷前几座城市，保证首屏数据是新的
CITY_GAP_SECONDS = 0.8       # 城市之间的间隔，给上游留出喘息
CYCLE_SLEEP_SECONDS = 600    # 跑完一轮后的休眠，随后继续下一轮
RETRY_DELAY_SECONDS = 3.0
LOG_FILE = BASE_DIR / "logs" / "warmup.log"

STATE: Dict[str, Any] = {
    "running": False,
    "started_at": "",
    "updated_at": "",
    "city": "",
    "index": 0,
    "total": 0,
    "round": 0,
    "done": 0,
    "added": 0,
    "errors": 0,
    "last_result": {},
    "force_rounds": 0,
}

_STARTED = threading.Lock()
_THREAD: Any = None


def _log(message: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            handle.write("[" + stamp + "] " + str(message) + chr(10))
    except Exception:
        pass


def _queue() -> List[str]:
    seen, out = set(), []
    for city in PRIORITY + list(CITIES):
        city = str(city or "").strip()
        if city and city not in seen:
            seen.add(city)
            out.append(city)
    return out


def _fetch(kind: str, city: str, force: bool) -> Dict[str, Any]:
    from services import live  # 延迟导入，避免启动期循环依赖

    keywords = live.CORE_KEYWORDS.get(kind)
    if kind == "metro":
        keywords = live.METRO_KEYWORDS
    return live.harvest(kind, city, keywords=keywords, pages=1, force=force, localize=0)


def _harvest_city(city: str, force: bool) -> Dict[str, Any]:
    """抓一座城市的三类数据；失败重试一次，不抛异常。"""
    from services import harvest

    outcome: Dict[str, Any] = {"city": city, "rows": 0, "added": 0, "sources": {}, "errors": []}
    for kind in ("attraction", "hotel", "metro"):
        for attempt in (1, 2):
            if harvest.STATE.get("running"):
                # 手动刷新或定时轮扫正在跑，先让路
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            try:
                result = _fetch(kind, city, force and attempt == 1)
                outcome["rows"] += int(result.get("rows") or 0)
                outcome["added"] += int(result.get("added") or 0)
                outcome["sources"][kind] = result.get("source")
                break
            except Exception as exc:
                if attempt == 1:
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                outcome["errors"].append("%s:%s" % (kind, type(exc).__name__))
    return outcome


def _run() -> None:
    queue = _queue()
    total = len(queue)
    STATE.update({"_queue": queue, "total": total})
    first_round = True
    while True:
        STATE["round"] = int(STATE["round"]) + 1
        force_budget = FORCE_REFRESH_FIRST if first_round else 0
        added_round = 0
        for index, city in enumerate(queue, start=1):
            STATE.update({
                "city": city, "index": index, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            force = force_budget > 0
            result = _harvest_city(city, force)
            if force:
                force_budget -= 1
            added_round += int(result.get("added") or 0)
            STATE["done"] = int(STATE["done"]) + 1
            STATE["added"] = int(STATE["added"]) + int(result.get("added") or 0)
            STATE["errors"] = int(STATE["errors"]) + len(result.get("errors") or [])
            STATE["last_result"] = result
            if result.get("added"):
                _log("%s 新增 %d 条（%s）" % (city, result["added"], result.get("sources")))
            time.sleep(CITY_GAP_SECONDS)
        first_round = False
        STATE["force_rounds"] = int(STATE["force_rounds"]) + 1
        _log("第 %d 轮结束：本轮新增 %d 条，累计新增 %d 条，错误 %d 次" % (
            STATE["round"], added_round, STATE["added"], STATE["errors"]))
        STATE["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        time.sleep(CYCLE_SLEEP_SECONDS)


def start_worker() -> Dict[str, Any]:
    """启动预热线程（幂等）；返回当前状态。"""
    global _THREAD
    with _STARTED:
        if _THREAD is not None and _THREAD.is_alive():
            return state()
        STATE.update({
            "running": True,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "round": 0, "done": 0, "added": 0, "errors": 0, "index": 0,
        })
        _THREAD = threading.Thread(target=_run, name="boot-warmup", daemon=True)
        _THREAD.start()
        _log("启动预热线程，队列 %d 座城市" % len(_queue()))
    return state()


def state() -> Dict[str, Any]:
    queue = STATE.get("_queue") or []
    return {
        "running": bool(STATE.get("running")),
        "started_at": STATE.get("started_at"),
        "updated_at": STATE.get("updated_at"),
        "city": STATE.get("city"),
        "index": STATE.get("index"),
        "total": STATE.get("total") or len(queue),
        "round": STATE.get("round"),
        "done": STATE.get("done"),
        "added": STATE.get("added"),
        "errors": STATE.get("errors"),
        "force_rounds": STATE.get("force_rounds"),
        "last_result": STATE.get("last_result") or {},
        "pending": max(0, (STATE.get("total") or 0) - (STATE.get("done") or 0) % max(1, STATE.get("total") or 1)),
    }