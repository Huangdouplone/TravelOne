# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""国际版预热：服务启动后按城市队列抓取景点 / 酒店 / 地铁，写入 intl:: 快照。

设计目标与国内预热一致但更轻：
- 独立守护线程，不阻塞 HTTP 请求；
- 队列先是内置 50 城的常用顺序，再接运行期动态解析出来的城市；
- 单城三类抓取之间留出间隔，避免把公共端点打满；
- 已新鲜（24 小时内且口径版本一致）的城市直接跳过，所以第一轮会很快跑完；
- 跑完一轮后休眠再从头开始，保证冷启动也能自己长出数据；
- 状态通过 /api/warmup?mode=global 与数据源面板暴露。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List

from collectors import wikidata_places
from core.config import BASE_DIR

# 首轮优先补的城市：常见出行目的地，先让首屏有内容
PRIORITY = [
    "巴黎", "伦敦", "东京", "纽约", "罗马", "巴塞罗那", "新加坡", "迪拜",
    "首尔", "悉尼", "曼谷", "阿姆斯特丹", "柏林", "马德里", "米兰", "维也纳",
    "苏黎世", "慕尼黑", "布拉格", "伊斯坦布尔", "洛杉矶", "旧金山", "多伦多",
    "温哥华", "吉隆坡", "雅加达", "河内", "孟买", "新德里", "开罗",
]
CITY_GAP_SECONDS = 1.0        # 城市之间的间隔
CYCLE_SLEEP_SECONDS = 900     # 跑完一轮后的休眠
KINDS = ("attraction", "hotel", "metro")
LOG_FILE = BASE_DIR / "logs" / "intl_warmup.log"

STATE: Dict[str, Any] = {
    "running": False,
    "started_at": "",
    "updated_at": "",
    "city": "",
    "index": 0,
    "total": 0,
    "round": 0,
    "added": 0,
    "errors": 0,
    "last_result": {},
}

_STARTED = threading.Lock()
_THREAD: Any = None
_STOP = threading.Event()


def _log(message: str) -> None:
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            handle.write("[" + stamp + "] " + str(message) + chr(10))
    except Exception:
        pass


def _queue() -> List[Dict[str, str]]:
    """内置城市按优先级排前，再接动态解析出来的城市；按中文名去重。"""
    rows = [wikidata_places.pointed(r) for r in wikidata_places.CITIES]
    seen = {r["city"] for r in rows}
    for value in (wikidata_places._load_custom() or {}).values():
        if value.get("city") and value["city"] not in seen:
            rows.append(wikidata_places.pointed(value))
            seen.add(value["city"])
    order = {name: i for i, name in enumerate(PRIORITY)}
    rows.sort(key=lambda r: (order.get(r["city"], len(PRIORITY)), r["city"]))
    return rows


def _run() -> None:
    while not _STOP.is_set():
        STATE.update({"round": STATE.get("round", 0) + 1, "index": 0, "added": 0,
                      "errors": 0, "city": "", "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        queue = _queue()
        STATE["total"] = len(queue)
        _log("round %d start, %d cities" % (STATE["round"], len(queue)))
        for index, row in enumerate(queue, start=1):
            if _STOP.is_set():
                return
            STATE.update({"index": index - 1, "city": row["city"],
                          "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            try:
                from services import intl  # 延迟导入，避免启动期循环依赖
                for kind in KINDS:
                    result = intl.harvest(kind, row["city"])
                    STATE["added"] = STATE.get("added", 0) + int(result.get("rows") or 0)
                    STATE["last_result"] = {"city": row["city"], "kind": kind,
                                            "source": result.get("source"),
                                            "rows": result.get("rows")}
                    time.sleep(0.4)
            except Exception as exc:  # 单城失败不终止整轮
                STATE["errors"] = STATE.get("errors", 0) + 1
                _log("fail %s: %s: %s" % (row["city"], type(exc).__name__, exc))
            STATE["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            time.sleep(CITY_GAP_SECONDS)
        STATE.update({"index": len(queue), "city": "",
                      "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        _log("round %d done, +%d rows, %d errors" % (STATE["round"], STATE.get("added", 0),
                                                    STATE.get("errors", 0)))
        _STOP.wait(CYCLE_SLEEP_SECONDS)


def start_worker() -> Dict[str, Any]:
    global _THREAD
    with _STARTED:
        if _THREAD and _THREAD.is_alive():
            return state()
        _STOP.clear()
        STATE.update({"running": True, "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        _THREAD = threading.Thread(target=_run, name="intl-warmup", daemon=True)
        _THREAD.start()
    return state()


def state() -> Dict[str, Any]:
    snapshot = dict(STATE)
    snapshot["running"] = bool(_THREAD and _THREAD.is_alive())
    snapshot.setdefault("total", 0)
    return snapshot