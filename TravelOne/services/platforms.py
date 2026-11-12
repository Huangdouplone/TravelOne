# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""Traditional OTA platform adapters.

Reality check (verified 2026-11-11):
- Qunar: prices are available through the built-in Baidu Maps aggregation
  (field pc_price_src = "qunar"); this is a live channel price, labelled honestly.
- Ctrip: public SEO pages expose hotel names, stars, guest scores and review
  counts, but room prices are rendered only after an authenticated app/API
  session (restapi/soa2/34951/fetchHotelList returns "Success" with empty data
  and requires a signed client context). We therefore use Ctrip for live
  ratings, never for prices.
- Tongcheng: the H5 list is a signed SPA (/tapi/v2/list requires h5sign); no
  anonymous price feed is available.
- Meituan: ihotel.meituan.com/hbsearch/HotelSearch returns 403 without an
  mtgsig-signed session; i.meituan.com/hotel/ is a JS shell.

No platform is scraped with forged signatures. Unavailable prices are reported
as unavailable instead of being replaced with made-up values.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import httpclient
from core.config import BASE_DIR

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
REGISTRY_DIR = Path(BASE_DIR) / "data" / "registry"
CITY_CACHE = REGISTRY_DIR / "ctrip_cities.json"
ID_CACHE = REGISTRY_DIR / "ctrip_city_ids.json"
LIST_CACHE = REGISTRY_DIR / "ctrip_lists.json"
LIST_TTL = 3600

_list_memory: Dict[str, Dict[str, Any]] = {}


def _dates() -> tuple[str, str]:
    day = datetime.now() + timedelta(days=1)
    return day.strftime("%Y-%m-%d"), (day + timedelta(days=1)).strftime("%Y-%m-%d")


def _get(url: str, timeout: int = 15) -> Optional[str]:
    try:
        resp = httpclient.get(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"},
                              timeout=timeout)
        if resp.status_code >= 400:
            return None
        return resp.text
    except Exception:
        return None


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save_json(path: Path, data: Any) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def city_ids() -> Dict[str, int]:
    """Ctrip domestic city name -> cityId, discovered from its public static list."""
    cached = _load_json(CITY_CACHE, {})
    if cached:
        return {str(k): int(v) for k, v in cached.items()}
    mapping: Dict[str, int] = {}
    for letter in "abcdefghijklmnopqrstuvwxyz":
        url = ("https://m.ctrip.com/webapp/hotel/j/hoteldetail/dianping/api/static/city"
               f"?oversea=false&index={letter.upper()}")
        text = _get(url, timeout=12)
        if not text:
            continue
        try:
            payload = json.loads(text)
        except ValueError:
            continue
        for row in payload.get("cities") or []:
            name = str(row.get("cname") or "").strip()
            cid = row.get("cityId")
            if name and isinstance(cid, int):
                mapping.setdefault(name, cid)
    if mapping:
        _save_json(CITY_CACHE, mapping)
    return mapping


def _discover_major_ids() -> Dict[str, int]:
    """Ctrip city ids 1..60 are its classic domestic destinations (Beijing=1...).
    Discovered once from public list page titles, then cached locally."""
    cached = _load_json(ID_CACHE, {})
    if cached:
        return {str(k): int(v) for k, v in cached.items()}
    import concurrent.futures

    def probe(cid: int):
        html = _get(f"https://hotels.ctrip.com/hotels/list?city={cid}", timeout=20)
        if not html:
            return None
        match = re.search(r"<title>([^<]+)</title>", html)
        if not match:
            return None
        name = re.match(r"(.+?)酒店", match.group(1))
        if not name:
            return None
        city = name.group(1).strip().rstrip(",")
        if not city or len(city) > 12:
            return None
        return city, cid

    mapping: Dict[str, int] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for row in pool.map(probe, range(1, 61)):
            if row:
                mapping.setdefault(row[0], row[1])
    if mapping:
        _save_json(ID_CACHE, mapping)
    return mapping


def resolve_city(name: str) -> Optional[int]:
    text = str(name or "").strip()
    if not text:
        return None
    mapping = city_ids()
    if text in mapping:
        return mapping[text]
    major = _discover_major_ids()
    if text in major:
        return major[text]
    for suffix in ("市", "地区", "自治州", "盟", "县"):
        if text.endswith(suffix) and text[: -len(suffix)] in major:
            return major[text[: -len(suffix)]]
    for suffix in ("市", "地区", "自治州", "盟", "县"):
        if text.endswith(suffix) and text[: -len(suffix)] in mapping:
            return mapping[text[: -len(suffix)]]
    return None


def _parse_cards(html: str) -> List[Dict[str, Any]]:
    starts = [m.start() for m in re.finditer(r'data-offline-hotelId="(\d+)"', html)]
    rows: List[Dict[str, Any]] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else min(len(html), start + 12000)
        segment = html[start:end]
        hotel_id = re.search(r'data-offline-hotelId="(\d+)"', segment)
        name = re.search(r'<span class="hotelName">([^<]+)</span>', segment)
        if not name:
            continue
        star = re.search(r'aria-label="(\d) out of 5 stars"', segment)
        score = (re.search(r'comment-score[^>]*aria-label="([\d.]+) out of 10"', segment)
                 or re.search(r'<span class="score"[^>]*>([\d.]+)</span>', segment))
        reviews = re.search(r'<span class="comment-num"[^>]*>([^<]+)</span>', segment)
        count = 0
        if reviews:
            count = int(re.sub(r"[^\d]", "", reviews.group(1)) or 0)
        rows.append({
            "platform": "Ctrip",
            "hotel_id": hotel_id.group(1) if hotel_id else "",
            "name": re.sub(r"\s+", " ", name.group(1)).strip(),
            "star": int(star.group(1)) if star else None,
            "score": float(score.group(1)) if score else None,
            "reviews": count,
            "url": ("https://hotels.ctrip.com/hotels/detail/?hotelId=" + hotel_id.group(1)) if hotel_id else "",
        })
    return rows


def ctrip_city_hotels(city: str) -> List[Dict[str, Any]]:
    cid = resolve_city(city)
    if not cid:
        return []
    key = str(cid)
    now = time.time()
    memory = _list_memory.get(key)
    if memory and now - memory["at"] < LIST_TTL:
        return memory["rows"]
    disk = _load_json(LIST_CACHE, {})
    cached = disk.get(key)
    if cached and now - float(cached.get("at") or 0) < LIST_TTL:
        rows = cached.get("rows") or []
        _list_memory[key] = {"at": cached.get("at"), "rows": rows}
        return rows
    check_in, check_out = _dates()
    url = (f"https://hotels.ctrip.com/hotels/list?city={cid}"
           f"&checkin={check_in}&checkout={check_out}")
    html = _get(url, timeout=25)
    rows = _parse_cards(html) if html else []
    _list_memory[key] = {"at": now, "rows": rows}
    disk[key] = {"at": now, "rows": rows}
    _save_json(LIST_CACHE, disk)
    return rows


def _normalize(name: str) -> str:
    text = re.sub(r"[（(].*?[)）]", "", str(name or ""))
    text = re.sub(r"[\s\-_·.,，。'\"()（）]", "", text.lower())
    return text


def ctrip_rating(hotel_name: str, city: str) -> Optional[Dict[str, Any]]:
    rows = ctrip_city_hotels(city)
    if not rows:
        return None
    target = _normalize(hotel_name)
    if not target:
        return None
    best = None
    for row in rows:
        candidate = _normalize(row.get("name") or "")
        if not candidate:
            continue
        same = candidate == target
        partial = target in candidate or candidate in target
        ratio = min(len(target), len(candidate)) / max(len(target), len(candidate) or 1)
        if same:
            score = 100
        elif partial and ratio >= 0.5:
            score = 80 + ratio * 20
        else:
            continue
        if best is None or score > best[0]:
            best = (score, row)
    if not best:
        return None
    row = dict(best[1])
    row["match"] = "exact" if best[0] == 100 else "fuzzy"
    return row


def warm() -> None:
    """Background warm-up so the first hotel detail does not pay discovery cost."""
    try:
        _discover_major_ids()
        for city in ("北京", "上海", "广州", "成都", "西安", "重庆", "杭州"):
            ctrip_city_hotels(city)
    except Exception:
        pass


def status() -> List[Dict[str, Any]]:
    """平台可用性。中文说明一并返回，页面按当前语言取用。"""
    return [
        {"id": "qunar", "label": "Qunar", "rating": False, "price": True,
         "mode": "live via Baidu Maps aggregation",
         "note": "Channel price and source are returned by Baidu Maps when available.",
         "note_zh": "百度地图返回渠道房价与来源时会显示实时报价。"},
        {"id": "ctrip", "label": "Ctrip", "rating": True, "price": False,
         "mode": "public SEO content (names, stars, scores)",
         "note": "Room prices require an authenticated app/API session; no anonymous price API.",
         "note_zh": "房价需要登录态的应用接口，没有匿名价格接口；评分与星级来自公开页面。"},
        {"id": "trip", "label": "Trip.com (Ctrip Group)", "rating": False, "price": False,
         "mode": "public SEO content",
         "note": "Featured list exposes prices, but not a stable per-hotel anonymous feed.",
         "note_zh": "精选页有价格，但没有稳定的单店匿名报价。"},
        {"id": "tongcheng", "label": "Tongcheng", "rating": False, "price": False,
         "mode": "blocked", "note": "H5 API /tapi/* requires h5sign; anonymous requests are rejected.",
         "note_zh": "H5 接口需要 h5sign 签名，匿名请求被拒绝。"},
        {"id": "meituan", "label": "Meituan", "rating": False, "price": False,
         "mode": "blocked", "note": "Hotel search returns 403 without an mtgsig-signed session.",
         "note_zh": "酒店搜索需要 mtgsig 签名会话，否则返回 403。"},
        {"id": "amap_tongcheng", "label": "高德 / 同程票价", "rating": False, "price": False,
         "mode": "partnership only",
         "note": "Amap's open POI API exposes rating and average spend only; it has no ticket or "
                 "room-rate field, and the platform terms forbid scraping or caching client data. "
                 "Authorised access requires a Tongcheng distribution/API agreement.",
         "note_zh": "高德客户端里的同程门票/房价来自商业合作：开放平台 POI 接口只有评分与人均消费，"
                    "没有票价/房价字段，协议也禁止抓取或缓存客户端数据；合规路径是向同程联盟/分销平台"
                    "申请 API 授权。"},
    ]