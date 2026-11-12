# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""为离线参赛页重建实景图素材（WebP + key 映射）。

背景：data/images 与 logs/image_map.json 曾被清理，离线页只能回落到 SVG 占位。
本脚本按“两条腿”补齐：
1. 城市实景兜底：每个城市抓 1 张城市风景/地标图，映射键 `<城市>::`；
   离线构建会用它给该城所有缺少单品图的条目兜底，避免出现占位封面。
2. 单品实景：重点城市取高分景点/酒店；国内优先复用快照里的图片 URL，
   国际条目用 360 图片搜索按“名称 + 城市”补图，映射键 `<城市>::<条目名>`。

用法：
    python tools/fetch_offline_images.py [--domestic-cities 40] [--items 6]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "images"
MAP_FILE = ROOT / "logs" / "image_map.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
WIDTH = int(os.environ.get("IMG_W", "220"))
QUALITY = int(os.environ.get("IMG_Q", "45"))
_LOCK = threading.Lock()


def label(city: str) -> str:
    city = str(city or "")
    return city[:-1] if city.endswith("市") and len(city) > 2 else city


def load_map() -> Dict[str, str]:
    try:
        return json.loads(MAP_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_map(mapping: Dict[str, str]) -> None:
    MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = MAP_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(mapping, ensure_ascii=False, indent=0), encoding="utf-8")
    tmp.replace(MAP_FILE)


def snapshots() -> List[Tuple[str, str, List[Dict[str, Any]]]]:
    """返回 (scope, 城市名, items) 列表；scope 以 intl:: 区分国际。"""
    out = []
    for path in glob.glob(str(ROOT / "data" / "cache" / "snap_attraction-*.json")):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        scope = str(data.get("scope") or "")
        city = scope.replace("intl::", "")
        out.append((scope, city, data.get("items") or []))
    return out


def search_images(query: str, limit: int = 4) -> List[str]:
    try:
        resp = requests.get(
            "https://image.so.com/j",
            params={"q": query, "src": "srp", "sn": 0, "pn": 10},
            headers={"User-Agent": UA, "Referer": "https://image.so.com/",
                     "Accept": "application/json"},
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        rows = resp.json().get("list") or []
    except Exception:
        return []
    urls = []
    for row in rows:
        url = str(row.get("img") or row.get("thumb") or row.get("pic_url") or "")
        width = int(row.get("width") or 0)
        height = int(row.get("height") or 0)
        if url.startswith("http") and (not width or width >= 320) and (not height or height >= 200):
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def download_webp(url: str, target: Path, referer: str) -> bool:
    try:
        resp = requests.get(url, timeout=15,
                            headers={"User-Agent": UA, "Referer": referer})
        if resp.status_code >= 400 or len(resp.content) < 1500:
            return False
        image = Image.open(io.BytesIO(resp.content)).convert("RGB")
        width = min(WIDTH, image.width)
        height = max(1, int(image.height * width / image.width))
        buffer = io.BytesIO()
        image.resize((width, height), Image.LANCZOS).save(buffer, "WEBP", quality=QUALITY, method=6)
        data = buffer.getvalue()
        if len(data) < 900:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return True
    except Exception:
        return False


def fetch_one(key: str, query: str, prefer_url: str = "", referer: str = "") -> Tuple[str, bool, int]:
    """抓一张图并写入映射；返回 (key, 是否成功, 字节数)。"""
    mapping = MAPPING
    existing = mapping.get(key)
    if existing and (OUT_DIR / existing).exists():
        return key, True, 0
    urls = [prefer_url] if prefer_url.startswith("http") else []
    urls += [u for u in search_images(query) if u not in urls]
    for index, url in enumerate(urls[:5]):
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
        target = OUT_DIR / (digest + ".webp")
        ref = referer or ("https://image.so.com/" if "so.com" in url or "qhimg" in url else "https://map.baidu.com/")
        if target.exists() or download_webp(url, target, ref):
            with _LOCK:
                mapping[key] = target.name
            return key, True, target.stat().st_size if target.exists() else 0
        time.sleep(0.2 + index * 0.15)
    return key, False, 0


MAPPING: Dict[str, str] = {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domestic-cities", type=int, default=40)
    parser.add_argument("--items", type=int, default=6)
    parser.add_argument("--hotels", type=int, default=2)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    global MAPPING
    MAPPING = load_map()
    snapshots_list = snapshots()
    domestic = [(s, c, items) for s, c, items in snapshots_list if not s.startswith("intl::")]
    intl = [(s, c, items) for s, c, items in snapshots_list if s.startswith("intl::")]
    domestic.sort(key=lambda row: -len(row[2]))
    print("国内城市 %d，国际城市 %d，已有映射 %d 张" % (len(domestic), len(intl), len(MAPPING)))

    jobs: List[Tuple[str, str, str, str]] = []
    # 1) 所有城市一张城市实景，作为缺图条目的兜底
    for scope, city, items in domestic + intl:
        if not city:
            continue
        query = city + (" 地标" if scope.startswith("intl::") else " 风景")
        jobs.append(("%s::" % label(city), query, "", ""))

    # 2) 单品实景：国内取数据量大的城市，国际取有地标白名单的城市
    target_domestic = {city for _, city, _ in domestic[: args.domestic_cities]}
    for scope, city, items in domestic + intl:
        is_intl = scope.startswith("intl::")
        if not is_intl and city not in target_domestic:
            continue
        ranked = sorted(items, key=lambda i: (-float(i.get("rating") or 0),
                                              -int(i.get("review_count") or 0)))
        picked = []
        seen = set()
        for item in ranked:
            name = str(item.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            picked.append(item)
            if len(picked) >= args.items:
                break
        for item in picked:
            name = str(item.get("name") or "").strip()
            photos = item.get("photos") or []
            prefer = ""
            if not is_intl:
                prefer = str(item.get("cover_image") or (photos[0] if photos else "") or "")
            jobs.append(("%s::%s" % (label(city), name), "%s %s" % (name, city), prefer, ""))

    # 3) 酒店实景
    hotel_paths = glob.glob(str(ROOT / "data" / "cache" / "snap_hotel-*.json"))
    for path in hotel_paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        scope = str(data.get("scope") or "")
        city = scope.replace("intl::", "")
        is_intl = scope.startswith("intl::")
        if not city or (not is_intl and city not in target_domestic):
            continue
        items = sorted(data.get("items") or [],
                       key=lambda i: (-float(i.get("rating") or 0), -int(i.get("review_count") or 0)))
        for item in items[: args.hotels]:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            photos = item.get("photos") or []
            prefer = "" if is_intl else str(item.get("cover_image") or (photos[0] if photos else "") or "")
            jobs.append(("%s::%s" % (label(city), name), "%s %s" % (name, city), prefer, ""))

    # 去重
    unique, seen_keys = [], set()
    for job in jobs:
        if job[0] in seen_keys:
            continue
        seen_keys.add(job[0])
        unique.append(job)
    print("计划抓取 %d 张（城市兜底 + 单品）" % len(unique))

    done = failed = 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_one, *job) for job in unique]
        for future in as_completed(futures):
            key, ok, size = future.result()
            done += 1
            if not ok:
                failed += 1
            if done % 25 == 0 or done == len(unique):
                with _LOCK:
                    save_map(MAPPING)
                print("进度 %d/%d，失败 %d，已用 %.0fs" % (done, len(unique), failed, time.time() - started))
    with _LOCK:
        save_map(MAPPING)

    cities = {s.replace("intl::", "") for s, _, _ in snapshots_list}
    covered = {key.split("::")[0] for key in MAPPING if key.endswith("::")}
    total_bytes = sum(p.stat().st_size for p in OUT_DIR.glob("*.webp")) if OUT_DIR.exists() else 0
    print("完成：映射 %d 张，图片 %.1f MB，城市兜底 %d/%d，失败 %d" % (
        len(MAPPING), total_bytes / 1048576, len(covered & cities), len(cities), failed))


if __name__ == "__main__":
    main()