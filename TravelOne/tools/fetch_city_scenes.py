# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""为每个城市补充多张实景组图，供离线页按条目哈希打散分配。

背景：此前每城基本只有 1 张城市封面，导致同城卡片大面积重复；条目级图片
又可能因名称模糊抓到无关图（人物、文字截图）。这里改为“城市实景组图”：
每城抓 5 张风景/城市/夜景/街景/旅游图，与已有封面一起形成图片池，
构建时按条目 key 哈希取图，同城不同条目尽量落在不同图片上。

输出：
- data/images/*.webp（约 150px、质量 36）
- logs/city_scenes.json：{城市标签: [文件名, ...]}

用法：python tools/fetch_city_scenes.py [--per-city 5] [--workers 6]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import fetch_offline_images as base  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCENES_FILE = ROOT / "logs" / "city_scenes.json"
LOCK = threading.Lock()


def label(city: str) -> str:
    city = str(city or "")
    return city[:-1] if city.endswith("市") and len(city) > 2 else city


def load_scenes() -> Dict[str, List[str]]:
    try:
        return json.loads(SCENES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_scenes(data: Dict[str, List[str]]) -> None:
    SCENES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SCENES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(SCENES_FILE)


def cities() -> List[str]:
    out = set()
    for path in glob.glob(str(ROOT / "data" / "cache" / "snap_*.json")):
        if "manifest" in path:
            continue
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        scope = str(data.get("scope") or "")
        if scope:
            out.add(label(scope.replace("intl::", "")))
    return sorted(out)


def grab_city(city: str, per_city: int, mapping: Dict[str, str]) -> tuple:
    scenes = load_scenes()
    pool = scenes.get(city) or []
    if not pool and mapping.get(city + "::"):
        pool = [mapping[city + "::"]]
    if len(pool) >= per_city + (1 if city + "::" in mapping else 0):
        return city, len(pool), 0
    used = set(pool)
    queries = ["风景", "城市", "夜景", "街景", "旅游", "地标"]
    saved = 0
    for query in queries:
        if len(pool) >= per_city + (1 if city + "::" in mapping else 0):
            break
        urls = base.search_images("%s %s" % (city, query), 8)
        for url in urls:
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
            name = digest + ".webp"
            if name in used:
                continue
            target = base.OUT_DIR / name
            if not target.exists() and not base.download_webp(url, target, "https://image.so.com/"):
                continue
            used.add(name)
            pool.append(name)
            saved += 1
            break
        time.sleep(0.15)
    with LOCK:
        data = load_scenes()
        data[city] = pool
        save_scenes(data)
    return city, len(pool), saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-city", type=int, default=5)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    base.WIDTH = 150
    base.QUALITY = 36
    mapping = base.load_map()
    targets = cities()
    print("城市 %d，已有组图 %d" % (len(targets), len(load_scenes())))
    started = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(grab_city, city, args.per_city, mapping) for city in targets]
        for future in as_completed(futures):
            city, total, saved = future.result()
            done += 1
            if done % 25 == 0 or done == len(targets):
                print("进度 %d/%d，当前 %s 共 %d 张，已用 %.0fs" % (
                    done, len(targets), city, total, time.time() - started), flush=True)
    total_files = len(list(base.OUT_DIR.glob("*.webp")))
    print("完成：%d 城，图片文件 %d 张，已用 %.0fs" % (
        len(targets), total_files, time.time() - started), flush=True)


if __name__ == "__main__":
    main()