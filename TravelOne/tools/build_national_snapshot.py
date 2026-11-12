# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""一次完成「全国数据快照 + 配图」：抓城市数据并同步下载压缩实景图。

每城：
1. harvest 景点/酒店/地铁（精简关键词，单页），写入 data/cache 快照；
2. 从抓到的条目里取评分最高的 12 个景点 + 2 家酒店，下载首张实景图，
   压成 200px 宽、质量 40 的 WebP（约 3–4 KB/张），按 URL 哈希去重；
3. 映射写入 logs/image_map.json（key 为「城市::名称」，与离线页一致）。

用法：python tools/build_national_snapshot.py 北京 上海 ...
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

from PIL import Image  # noqa: E402

from core import cache_store  # noqa: E402
from services import live  # noqa: E402

OUT_DIR = ROOT / "data" / "images"
MAP_FILE = ROOT / "logs" / "image_map.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TARGET_W = 200
QUALITY = 40
ATTR_PER_CITY = int(os.environ.get('IMG_ATTR', '8'))
HOTEL_PER_CITY = int(os.environ.get('IMG_HOTEL', '2'))
ATTR_WORDS = live.CORE_KEYWORDS["attraction"][:5]
HOTEL_WORDS = live.CORE_KEYWORDS["hotel"][:2]


def load_map() -> Dict[str, str]:
    try:
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_map(data: Dict[str, str]) -> None:
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAP_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def grab(url: str, target: Path) -> bool:
    try:
        resp = requests.get(url, timeout=12, headers={"User-Agent": UA, "Referer": "https://map.baidu.com/"})
        if resp.status_code >= 400 or len(resp.content) < 1200:
            return False
        image = Image.open(io.BytesIO(resp.content)).convert("RGB")
        width = min(TARGET_W, image.width)
        height = max(1, int(image.height * width / image.width))
        buffer = io.BytesIO()
        image.resize((width, height), Image.LANCZOS).save(buffer, "WEBP", quality=QUALITY, method=6)
        data = buffer.getvalue()
        if len(data) < 700:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return True
    except Exception:
        return False


def pick(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    with_photo = [i for i in items if (i.get("photos") or i.get("cover_image")) and i.get("rating")]
    with_photo.sort(key=lambda i: (-float(i.get("rating") or 0), -int(i.get("review_count") or 0)))
    out, seen = [], set()
    for item in with_photo:
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def main() -> None:
    cities = sys.argv[1:]
    if not cities:
        print("usage: build_national_snapshot.py CITY [CITY ...]")
        return
    mapping = load_map()
    added_imgs = 0
    for city in cities:
        started = time.time()
        for kind, words in (("attraction", ATTR_WORDS), ("hotel", HOTEL_WORDS)):
            try:
                live.harvest(kind, city, keywords=words, pages=1, localize=0, force=True)
            except Exception:
                pass
        label = city[:-1] if city.endswith("市") and len(city) > 2 else city
        tasks = []
        for kind, limit in (("attraction", ATTR_PER_CITY), ("hotel", HOTEL_PER_CITY)):
            for item in pick(cache_store.items(kind, city), limit):
                url = (item.get("photos") or [item.get("cover_image")])[0]
                if not url or not str(url).startswith("http"):
                    continue
                key = "%s::%s" % (label, item.get("name"))
                if key in mapping and (OUT_DIR / mapping[key]).exists():
                    continue
                digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
                tasks.append((key, url, OUT_DIR / (digest + ".webp")))

        def run(task):
            key, url, target = task
            if target.exists() or grab(url, target):
                return key, target.name
            return None

        if tasks:
            with ThreadPoolExecutor(max_workers=6) as pool:
                for result in pool.map(run, tasks):
                    if result:
                        mapping[result[0]] = result[1]
                        added_imgs += 1
        save_map(mapping)
        print("%s 完成（%.1fs）图片累计 %d 张" % (city, time.time() - started, len(mapping)))
    total = sum(p.stat().st_size for p in OUT_DIR.glob("*.webp")) if OUT_DIR.exists() else 0
    print("完成：映射 %d 张，新增 %d，图片目录 %.1f MB" % (len(mapping), added_imgs, total / 1048576))


if __name__ == "__main__":
    main()