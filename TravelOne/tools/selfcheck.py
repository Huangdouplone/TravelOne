# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""实时抓取自检：真实抓取一个城市，打印并记录景点/酒店条数与价格覆盖率。

用法：
    python tools/selfcheck.py            # 默认北京
    python tools/selfcheck.py 拉萨

输出：
- 控制台：中文摘要（城市、条数、有价条数、样例）
- 文件：logs/selfcheck-<城市>-<时间>.json（原始统计，便于核对）

注意：这是真实网络抓取，不是用预置数据模拟；抓不到时会如实显示 0 条与失败原因。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from services import live  # noqa: E402


def main() -> None:
    city = (sys.argv[1] if len(sys.argv) > 1 else "北京").strip() or "北京"
    started = time.time()
    print(f"[1/3] 实时抓取 {city} 景点…", flush=True)
    attr = live.harvest("attraction", city, force=True, keywords=live.KEYWORDS["attraction"],
                        pages=2, localize=0)
    print(f"[2/3] 实时抓取 {city} 酒店…", flush=True)
    hotel = live.harvest("hotel", city, force=True, keywords=live.KEYWORDS["hotel"],
                         pages=2, localize=0)
    print(f"[3/3] 实时抓取 {city} 地铁站…", flush=True)
    metro = live.harvest("metro", city, force=True, keywords=live.METRO_KEYWORDS,
                         pages=1, localize=0)

    attractions = live.cache_store.items("attraction", city)
    hotels = live.cache_store.items("hotel", city)
    stations = live.metros(city)
    priced_attr = [row for row in attractions if row.get("price") is not None]
    priced_hotel = [row for row in hotels if row.get("price") is not None]

    summary = {
        "city": city,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(time.time() - started, 1),
        "attractions": {"total": len(attractions), "with_price": len(priced_attr),
                        "source": attr.get("source")},
        "hotels": {"total": len(hotels), "with_price": len(priced_hotel),
                   "source": hotel.get("source")},
        "metros": {"total": len(stations), "source": metro.get("source")},
        "samples": {
            "attraction": [{"name": row["name"], "price": row.get("price"),
                            "source": row.get("price_source")} for row in priced_attr[:5]],
            "hotel": [{"name": row["name"], "price": row.get("price"),
                       "source": row.get("price_source")} for row in priced_hotel[:5]],
        },
    }
    log_dir = BASE / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    target = log_dir / f"selfcheck-{city}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("")
    print(f"城市：{city}（耗时 {summary['elapsed_seconds']} 秒，来源 {attr.get('source')}/{hotel.get('source')}）")
    print(f"景点：{len(attractions)} 个，其中有票价 {len(priced_attr)} 个")
    print(f"酒店：{len(hotels)} 家，其中有房价 {len(priced_hotel)} 家")
    print(f"地铁站：{len(stations)} 座")
    for row in summary["samples"]["attraction"]:
        print(f"  · {row['name']}  ¥{row['price']}  {row['source']}")
    for row in summary["samples"]["hotel"]:
        print(f"  · {row['name']}  ¥{row['price']}/晚  {row['source']}")
    print(f"记录已写入：{target}")


if __name__ == "__main__":
    main()