# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""按城市抓取景点/酒店实景图，压缩成小尺寸 WebP 供离线页内嵌。

每城取评分最高的若干景点与酒店，各取第一张实景图：
- 下载后统一转 220px 宽、质量 45 的 WebP，控制单图 5–8 KB；
- 按图片 URL 哈希去重，映射写入 logs/image_map.json（key -> 文件名）；
- 单城失败不影响整体，逐城进度打印。

用法：python tools/fetch_city_images.py 北京 上海 ...
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
from PIL import Image  # noqa: E402

from core import cache_store  # noqa: E402
from services import live  # noqa: E402

OUT_DIR = ROOT / "data" / "images"
MAP_FILE = ROOT / "logs" / "image_map.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TARGET_W = int(os.environ.get("IMG_W", "220"))
QUALITY = int(os.environ.get("IMG_Q", "45"))
PER_CITY_ATTRACTION = int(os.environ.get("IMG_ATTR", "6"))
PER_CITY_HOTEL = int(os.environ.get("IMG_HOTEL", "2"))
FAST = os.environ.get("FAST", "") in ("1", "true", "yes")


def load_map() -> Dict[str, Any]:
    try:
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_map(data: Dict[str, Any]) -> None:
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
        if len(data) < 800:
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
        name = str(item.get("name") or "")
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
        print("usage: fetch_city_images.py CITY [CITY ...]")
        return
    mapping = load_map()
    total_saved = total_kb = 0
    for city in cities:
        started = time.time()
        saved = 0
        for kind, limit in (("attraction", PER_CITY_ATTRACTION), ("hotel", PER_CITY_HOTEL)):
            try:
                if kind == "attraction":
                    words = live.CORE_KEYWORDS["attraction"][:4] if FAST else live.CORE_KEYWORDS["attraction"]
                else:
                    words = live.CORE_KEYWORDS["hotel"][:2] if FAST else live.CORE_KEYWORDS["hotel"]
                res = live.harvest(kind, city, keywords=words, pages=1, localize=0, force=False)
            except Exception:
                continue
            items = cache_store.items(kind, city) if res else []
            for item in pick(items, limit):
                url = (item.get("photos") or [item.get("cover_image")])[0]
                if not url or not str(url).startswith("http"):
                    continue
                label = city[:-1] if city.endswith("市") and len(city) > 2 else city
                key = "%s::%s" % (label, item.get("name"))
                if key in mapping and (OUT_DIR / mapping[key]).exists():
                    continue
                digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
                target = OUT_DIR / (digest + ".webp")
                if target.exists() or grab(url, target):
                    mapping[key] = target.name
                    saved += 1
                    total_kb += target.stat().st_size // 1024
        save_map(mapping)
        print("%s 新增图片 %d 张（%.1fs）累计 %d 张" % (city, saved, time.time() - started, len(mapping)))
    total_saved = len(mapping)
    print("完成：映射 %d 张，图片目录约 %.1f MB" % (
        total_saved, sum(p.stat().st_size for p in OUT_DIR.glob("*.webp")) / 1048576 if OUT_DIR.exists() else 0))


if __name__ == "__main__":
    main()