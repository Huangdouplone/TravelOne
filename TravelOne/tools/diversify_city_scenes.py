# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""对城市实景组图做感知去重与补图，避免同城多张图其实是同一角度/同一主体。

做法：
- 以现有组图为起点，计算 8x8 平均哈希；
- 与已保留图片距离过近（汉明距离 < 10）的删除；
- 不足 6 张时继续用 360 图片搜索按不同关键词补图，仍按哈希去重；
- 优先处理国际城市与数据量大的国内城市。

输出仍写回 data/images 与 logs/city_scenes.json。
用法：python tools/diversify_city_scenes.py [--targets 90] [--pool 6]
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
SCENES_FILE = ROOT / "logs" / "city_scenes.json"
LOCK = threading.Lock()
UA = base.UA


def ahash(image: Image.Image, size: int = 8) -> int:
    small = image.convert("L").resize((size, size), Image.LANCZOS)
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for value in pixels:
        bits = (bits << 1) | (1 if value >= avg else 0)
    return bits


def distance(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def load_scenes() -> Dict[str, List[str]]:
    try:
        return json.loads(SCENES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_scenes(data: Dict[str, List[str]]) -> None:
    tmp = SCENES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(SCENES_FILE)


def image_hash(path: Path) -> int:
    try:
        return ahash(Image.open(path))
    except Exception:
        return 0


def fetch_candidate(url: str) -> Tuple[int, bytes, str] | None:
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": UA, "Referer": "https://image.so.com/"})
        if resp.status_code >= 400 or len(resp.content) < 1500:
            return None
        image = Image.open(io.BytesIO(resp.content)).convert("RGB")
        bits = ahash(image)
        width = min(150, image.width)
        height = max(1, int(image.height * width / image.width))
        buf = io.BytesIO()
        image.resize((width, height), Image.LANCZOS).save(buf, "WEBP", quality=34, method=6)
        data = buf.getvalue()
        if len(data) < 900:
            return None
        digest = hashlib.sha1(resp.content).hexdigest()[:20]
        return bits, data, digest + ".webp"
    except Exception:
        return None


def rebuild_city(city: str, pool_target: int, queries: List[str]) -> Tuple[str, int, int]:
    scenes = load_scenes()
    pool = list(scenes.get(city) or [])
    kept: List[str] = []
    hashes: List[int] = []
    for name in pool:
        path = base.OUT_DIR / name
        if not path.exists():
            continue
        h = image_hash(path)
        if any(distance(h, other) < 10 for other in hashes):
            continue
        kept.append(name)
        hashes.append(h)
    added = 0
    if len(kept) < pool_target:
        used = set(kept)
        for query in queries:
            if len(kept) >= pool_target:
                break
            for url in base.search_images("%s %s" % (city, query), 10):
                cand = fetch_candidate(url)
                if not cand:
                    continue
                bits, data, name = cand
                if name in used or any(distance(bits, other) < 10 for other in hashes):
                    continue
                (base.OUT_DIR / name).write_bytes(data)
                used.add(name)
                kept.append(name)
                hashes.append(bits)
                added += 1
                break
    with LOCK:
        data = load_scenes()
        data[city] = kept
        save_scenes(data)
    return city, len(kept), added


def targets(limit: int) -> List[str]:
    scenes = load_scenes()
    intl, domestic = [], []
    for path in glob.glob(str(ROOT / "data" / "cache" / "snap_attraction-*.json")):
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        scope = str(d.get("scope") or "")
        city = scope.replace("intl::", "")
        if not city:
            continue
        label = city[:-1] if city.endswith("市") and len(city) > 2 else city
        if scope.startswith("intl::"):
            intl.append(label)
        else:
            domestic.append((len(d.get("items") or []), label))
    domestic.sort(reverse=True)
    order = list(dict.fromkeys(intl + [c for _, c in domestic]))
    return order[:limit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=int, default=90)
    parser.add_argument("--pool", type=int, default=6)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    cities = targets(args.targets)
    queries = ["街头", "建筑", "公园", "河", "市场", "夜景", "地标", "风景", "旅游", "城市"]
    print("目标城市 %d，池目标 %d" % (len(cities), args.pool), flush=True)
    started = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(rebuild_city, city, args.pool, queries) for city in cities]
        for future in as_completed(futures):
            city, total, added = future.result()
            done += 1
            if done % 10 == 0 or done == len(cities):
                print("进度 %d/%d，当前 %s 保留 %d 张，新增 %d，已用 %.0fs" % (
                    done, len(cities), city, total, added, time.time() - started), flush=True)
    print("完成 %d 城，已用 %.0fs" % (len(cities), time.time() - started), flush=True)


if __name__ == "__main__":
    main()