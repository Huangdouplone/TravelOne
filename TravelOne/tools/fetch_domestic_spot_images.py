# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""补全国内景点的条目级实景图，优先热门城市，按预算限量。

数据来源：快照里已经存在的 Baidu Maps 图片 URL（`photos` / `cover_image`），
不再做关键词搜索，避免抓到无关图；统一压成 150px、质量 36 的 WebP，
写入 logs/image_map.json 的 `<城市>::<景点名>` 键，离线构建会优先使用。

用法：
    python tools/fetch_domestic_spot_images.py [--limit 1600] [--workers 8]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import fetch_offline_images as base  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOCK = threading.Lock()
PRIORITY = ["北京", "上海", "广州", "深圳", "成都", "重庆", "杭州", "西安",
            "南京", "武汉", "天津", "长沙", "苏州", "青岛", "厦门", "昆明",
            "大理", "丽江", "三亚", "桂林", "哈尔滨", "西安", "洛阳", "开封"]


def label(city: str) -> str:
    city = str(city or "")
    return city[:-1] if city.endswith("市") and len(city) > 2 else city


def load_cities() -> List[Tuple[str, int, List[Dict[str, Any]]]]:
    out = []
    for path in glob.glob(str(ROOT / "data" / "cache" / "snap_attraction-*.json")):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        scope = str(data.get("scope") or "")
        if scope.startswith("intl::"):
            continue
        city = label(scope)
        if not city:
            continue
        out.append((city, len(data.get("items") or []), data.get("items") or []))
    order = {name: i for i, name in enumerate(PRIORITY)}
    out.sort(key=lambda row: (order.get(row[0], len(PRIORITY)), -row[1]))
    return out


def quota(rank: int) -> int:
    if rank < len(PRIORITY):
        return 30
    if rank < 50:
        return 15
    return 6


def grab(item: Dict[str, Any], city: str) -> Tuple[str, bool, int]:
    name = str(item.get("name") or "").strip()
    if not name:
        return "", False, 0
    key = "%s::%s" % (city, name)
    mapping = base.load_map()
    if key in mapping and (base.OUT_DIR / mapping[key]).exists():
        return key, True, 0
    url = item.get("cover_image") or (item.get("photos") or [""])[0]
    if not str(url).startswith("http"):
        return key, False, 0
    digest = hashlib.sha1(str(url).encode("utf-8")).hexdigest()[:20]
    target = base.OUT_DIR / (digest + ".webp")
    if target.exists():
        with LOCK:
            data = base.load_map()
            data[key] = target.name
            base.save_map(data)
        return key, True, target.stat().st_size
    if not base.download_webp(str(url), target, "https://map.baidu.com/"):
        return key, False, 0
    with LOCK:
        data = base.load_map()
        data[key] = target.name
        base.save_map(data)
    return key, True, target.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1600)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    base.WIDTH = 150
    base.QUALITY = 36
    mapping = base.load_map()
    cities = load_cities()
    jobs: List[Tuple[Dict[str, Any], str]] = []
    for rank, (city, _count, items) in enumerate(cities):
        cap = quota(rank)
        picked = 0
        ranked = sorted(items, key=lambda i: (-float(i.get("rating") or 0),
                                              -int(i.get("review_count") or 0)))
        for item in ranked:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            if "%s::%s" % (city, name) in mapping:
                continue
            if not (item.get("cover_image") or item.get("photos")):
                continue
            jobs.append((item, city))
            picked += 1
            if picked >= cap:
                break
        if len(jobs) >= args.limit:
            break
    jobs = jobs[: args.limit]
    print("计划补图 %d 张（%d 城）" % (len(jobs), len({c for _, c in jobs})), flush=True)
    started = time.time()
    done = ok = 0
    bytes_total = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(grab, item, city) for item, city in jobs]
        for future in as_completed(futures):
            key, success, size = future.result()
            done += 1
            if success:
                ok += 1
                bytes_total += size
            if done % 100 == 0 or done == len(jobs):
                print("进度 %d/%d，成功 %d，新增 %.1f MB，已用 %.0fs" % (
                    done, len(jobs), ok, bytes_total / 1048576, time.time() - started), flush=True)
    print("完成：成功 %d/%d，新增 %.1f MB" % (ok, len(jobs), bytes_total / 1048576), flush=True)


if __name__ == "__main__":
    main()