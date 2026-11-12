# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""全国范围精简抓取：按城市抓景点、酒店、地铁并写入 data/cache 快照。

每城用核心关键词 + 单页，目的是覆盖全国而不是逐城穷举；
进度累积写入 logs/national_harvest.json，便于离线页生成时核对。

用法：python tools/harvest_national.py 北京 上海 天津
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import cache_store  # noqa: E402
from services import live  # noqa: E402

LOG = ROOT / "logs" / "national_harvest.json"


def load_log() -> dict:
    try:
        return json.loads(LOG.read_text(encoding="utf-8"))
    except Exception:
        return {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "cities": {}}


def main() -> None:
    cities = sys.argv[1:]
    if not cities:
        print("usage: harvest_national.py CITY [CITY ...]")
        return
    log = load_log()
    log.setdefault("cities", {})
    for city in cities:
        started = time.time()
        kinds = {}
        fast = os.environ.get("FAST", "") in ("1", "true", "yes")
        words_map = {
            "attraction": live.CORE_KEYWORDS["attraction"][:8] if fast else live.CORE_KEYWORDS["attraction"],
            "hotel": live.CORE_KEYWORDS["hotel"][:3] if fast else live.CORE_KEYWORDS["hotel"],
            "metro": live.METRO_KEYWORDS[:4] if fast else live.METRO_KEYWORDS,
        }
        for kind, words, pages in (("attraction", words_map["attraction"], 1),
                                   ("hotel", words_map["hotel"], 1),
                                   ("metro", words_map["metro"], 1)):
            try:
                res = live.harvest(kind, city, force=True, keywords=words, pages=pages, localize=0)
                kinds[kind] = {"rows": res.get("rows") or 0, "count": res.get("count") or 0,
                               "source": res.get("source")}
            except Exception as exc:
                kinds[kind] = {"rows": 0, "count": 0, "source": "error:%s" % type(exc).__name__}
        log["cities"][city] = {"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                               "seconds": round(time.time() - started, 1), "kinds": kinds}
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        print("%s %ss 景点%s 酒店%s 地铁%s" % (
            city, round(time.time() - started, 1),
            kinds["attraction"]["rows"], kinds["hotel"]["rows"], kinds["metro"]["rows"]))
    snapshots = cache_store.stats() if hasattr(cache_store, "stats") else {}
    print("累计快照：", (snapshots or {}).get("by_kind"))


if __name__ == "__main__":
    main()