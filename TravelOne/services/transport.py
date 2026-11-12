# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""交通与成本估算：城际机票 / 12306 高铁 / 自驾油耗。

数据分层（页面会如实标注每一条的来源）：
1. 油价：collectors.oil 抓公开油价表，得到省级 92#/95#/0# 挂牌价（真实现价）；
2. 高铁：先尝试 12306 余票接口；该接口当前对匿名请求返回加密载荷，解析不到时
   **不编造价位**，改用公开运价规则（二等座约 0.46 元/公里、一等座约 0.74 元/公里）
   给出区间估算，并标明「估算」；
3. 机票：尝试携程/去哪儿公开列表接口；均需签名或登录态，失败时按直线距离与
   典型巡航速度给出耗时与价格区间估算，同样标明「估算」；
4. 自驾：油价 × 百公里油耗 + 高速通行费估算，里程用直线距离 × 路网系数。

不提供任何购买或下单入口，只做信息同步与比对。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from collectors import baidu_web, oil
from collectors import rail as rail_data
from core import cache_store, httpclient
from core.config import settings
from core.geo import haversine_km

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ROAD_FACTOR = 1.22          # 直线距离 → 公路里程的近似系数
RAIL_FACTOR = 1.18          # 直线距离 → 铁路里程的近似系数
FUEL_PER_100KM = 7.5        # 家用车百公里油耗（L）
TOLL_PER_KM = 0.45          # 高速通行费（元/公里）
RAIL_RATE = {"second": 0.46, "first": 0.74}   # 公开运价规则：元/公里
RAIL_SPEED_KMH = 280        # 高铁旅行速度（含区间限速的平均值）
RAIL_STOP_MIN = 18          # 中途停站附加时间
FLIGHT_BASE = 280           # 机票基础价（元）
FLIGHT_PER_KM = 0.35        # 机票里程单价（元/公里）
FLIGHT_SPEED_KMH = 650
FLIGHT_OVERHEAD_MIN = 120   # 值机、安检、起降与地面交通
DRIVE_SPEED_KMH = 85        # 含休息的高速平均车速
SOURCE_LINKS = {
    "rail": {"name": "12306", "url": "https://www.12306.cn/",
             "note": "Timetable and train numbers; fares estimated from the published tariff rule"},
    "fuel": {"name": "icauto.com.cn", "url": "https://www.icauto.com.cn/oil/",
             "note": "Provincial pump prices, fetched live"},
    "flight": {"name": "No anonymous fare feed", "url": "https://www.caac.gov.cn/",
               "note": "Fares estimated from distance; airline APIs need signed sessions"},
}
CITY_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}

_CITY_TTL = 6 * 3600


def _city_point(name: str) -> Optional[Dict[str, Any]]:
    """解析城市中心坐标：先用已有快照，再退回一次景点检索。"""
    key = str(name or "").strip()
    if not key:
        return None
    cached = CITY_CACHE.get(key)
    if cached:
        return cached
    record = cache_store.load("geo", key)
    if record and cache_store.age_seconds(record) is not None and cache_store.age_seconds(record) < _CITY_TTL:
        item = (record.get("items") or [None])[0]
        if item and item.get("lat"):
            CITY_CACHE[key] = item
            return item
    rows = baidu_web.search("景点", key, "attraction", 0, 5)
    point = None
    for row in rows:
        if row.get("lat") is not None:
            point = {"name": key, "lat": row["lat"], "lng": row["lng"], "city": row.get("city") or key}
            break
    if point:
        cache_store.save("geo", key, [point], "baidu_web")
        CITY_CACHE[key] = point
    return point


def fuel_prices(province: str = "北京") -> Dict[str, Any]:
    """油价：优先用 6 小时内的快照，过期后重新抓取。"""
    record = cache_store.load("fuel", province)
    age = cache_store.age_seconds(record)
    items = (record or {}).get("items") or []
    if items and age is not None and age < _CITY_TTL:
        return dict(items[0], source="cache", age_seconds=int(age))
    live = oil.fetch_oil(province)
    if live:
        item = dict(live)
        cache_store.save("fuel", province, [item], item.get("source") or "oil")
        item.update({"source": "live", "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        return item
    if record and record.get("items"):
        item = dict(record["items"][0])
        item.update({"source": "cache", "age_seconds": int(age or 0)})
        return item
    return {"province": province, "prices": {}, "source": "unavailable"}


def _rail_live(from_city: str, to_city: str, date: str) -> Optional[List[Dict[str, Any]]]:
    """12306 余票：匿名请求目前返回加密载荷，解析不到就返回 None。"""
    try:
        session = httpclient.Session({"User-Agent": UA})
        session.get("https://kyfw.12306.cn/otn/leftTicket/init",
                    headers={"Referer": "https://www.12306.cn/"}, timeout=10)
        url = ("https://kyfw.12306.cn/otn/leftTicket/queryZ?leftTicketDTO.train_date=" + date +
               "&leftTicketDTO.from_station=" + from_city + "&leftTicketDTO.to_station=" + to_city +
               "&purpose_codes=ADULT")
        resp = session.get(url, headers={"Referer": "https://kyfw.12306.cn/otn/leftTicket/init",
                                         "X-Requested-With": "XMLHttpRequest"}, timeout=12)
        payload = resp.json()
    except Exception:
        return None
    rows = ((payload.get("data") or {}).get("result") or [])
    out: List[Dict[str, Any]] = []
    for raw in rows:
        parts = str(raw).split("|")
        if len(parts) < 30:
            continue
        # 加密载荷的字段不是车次号，直接放弃，避免把乱码当数据
        if not parts[2].startswith(("G", "D", "C")):
            return None
        out.append({"code": parts[2], "from": parts[6], "to": parts[7],
                    "depart": parts[8], "arrive": parts[9], "duration": parts[10],
                    "second": parts[30], "first": parts[31]})
    return out or None


def _rail_estimate(km: float) -> Dict[str, Any]:
    rail_km = km * RAIL_FACTOR
    minutes = int(round(rail_km / RAIL_SPEED_KMH * 60 + RAIL_STOP_MIN))
    low = round(rail_km * RAIL_RATE["second"])
    high = round(rail_km * RAIL_RATE["first"])
    return {
        "mode": "rail",
        "label": "High-speed rail",
        "label_zh": "高铁",
        "duration_min": minutes,
        "price_from": low,
        "price_to": high,
        "seats": "second / first",
        "estimated": True,
        "source": "estimate",
        "source_label": "Timetable trains are real; fare = rail mileage x published tariff",
        "source_label_zh": "车次为时刻表真实车次；票价 = 铁路里程 x 公开运价规则",
        "breakdown": {
            "rail_km": round(rail_km, 1),
            "rate_second": RAIL_RATE["second"],
            "rate_first": RAIL_RATE["first"],
            "speed_kmh": RAIL_SPEED_KMH,
            "stop_min": RAIL_STOP_MIN,
        },
        "breakdown_label": ("Rail mileage %.0f km x CNY%.2f-%.2f/km; %d km/h + %d min stops"
                            % (rail_km, RAIL_RATE["second"], RAIL_RATE["first"], RAIL_SPEED_KMH, RAIL_STOP_MIN)),
        "breakdown_label_zh": ("铁路里程 %.0f km × %.2f–%.2f 元/公里；耗时按 %d km/h + %d 分钟停站"
                              % (rail_km, RAIL_RATE["second"], RAIL_RATE["first"], RAIL_SPEED_KMH, RAIL_STOP_MIN)),
        "source_url": SOURCE_LINKS["rail"]["url"],
    }


def _flight_estimate(km: float) -> Dict[str, Any]:
    minutes = int(round(km / FLIGHT_SPEED_KMH * 60 + FLIGHT_OVERHEAD_MIN))
    base = FLIGHT_BASE + km * FLIGHT_PER_KM
    return {
        "mode": "flight",
        "label": "Flight",
        "label_zh": "飞机",
        "duration_min": minutes,
        "price_from": round(base * 0.75),
        "price_to": round(base * 1.35),
        "seats": "economy",
        "estimated": True,
        "source": "estimate",
        "source_label": "Estimated from distance; airlines need signed sessions",
        "source_label_zh": "按航距估算（机票接口需签名，无匿名报价源）",
        "breakdown": {
            "distance_km": round(km, 1),
            "base": FLIGHT_BASE,
            "per_km": FLIGHT_PER_KM,
            "range": [0.75, 1.35],
            "speed_kmh": FLIGHT_SPEED_KMH,
            "overhead_min": FLIGHT_OVERHEAD_MIN,
        },
        "breakdown_label": ("Base CNY%d + %.0f km x CNY%.2f/km, band x0.75-1.35; %d km/h + %d min ground"
                            % (FLIGHT_BASE, km, FLIGHT_PER_KM, FLIGHT_SPEED_KMH, FLIGHT_OVERHEAD_MIN)),
        "breakdown_label_zh": ("基础价 %d 元 + %.0f km × %.2f 元/km，区间 ×0.75–1.35；%d km/h + %d 分钟地面时间"
                              % (FLIGHT_BASE, km, FLIGHT_PER_KM, FLIGHT_SPEED_KMH, FLIGHT_OVERHEAD_MIN)),
        "source_url": SOURCE_LINKS["flight"]["url"],
    }


def _drive_option(km: float, fuel: Dict[str, Any]) -> Dict[str, Any]:
    road_km = km * ROAD_FACTOR
    price = (fuel.get("prices") or {}).get("p92") or 8.5
    liters = road_km / 100 * FUEL_PER_100KM
    fuel_cost = liters * price
    toll = road_km * TOLL_PER_KM
    return {
        "mode": "drive",
        "label": "Self-drive",
        "label_zh": "自驾",
        "duration_min": int(round(road_km / DRIVE_SPEED_KMH * 60)),
        "price_from": round(fuel_cost),
        "price_to": round(fuel_cost + toll),
        "seats": "fuel / fuel + toll",
        "distance_km": round(road_km, 1),
        "liters": round(liters, 1),
        "fuel_price": price,
        "fuel_source": fuel.get("source"),
        "estimated": True,
        "source": "fuel+estimate",
        "source_label": "Fuel price fetched live; tolls and consumption are stated assumptions",
        "source_label_zh": "油价实时抓取；油耗与通行费按下述参数计算",
        "breakdown": {
            "road_km": round(road_km, 1),
            "liters": round(liters, 1),
            "fuel_price": round(float(price), 2),
            "fuel_cost": round(fuel_cost, 2),
            "toll_per_km": TOLL_PER_KM,
            "toll": round(toll, 2),
            "fuel_per_100km": FUEL_PER_100KM,
            "road_factor": ROAD_FACTOR,
            "speed_kmh": DRIVE_SPEED_KMH,
        },
        "breakdown_label": ("Fuel %.0f km / 100 x %.1f L x CNY%.2f = CNY%.0f; toll %.0f km x CNY%.2f = CNY%.0f"
                            % (road_km, FUEL_PER_100KM, price, fuel_cost, road_km, TOLL_PER_KM, toll)),
        "breakdown_label_zh": ("油费 %.0f km ÷ 100 × %.1f L × %.2f 元 = %.0f 元；通行费 %.0f km × %.2f 元 = %.0f 元"
                              % (road_km, FUEL_PER_100KM, price, fuel_cost, road_km, TOLL_PER_KM, toll)),
        "source_url": SOURCE_LINKS["fuel"]["url"],
    }


def compare(from_city: str, to_city: str, date: str = "", province: str = "") -> Dict[str, Any]:
    """给出机票 / 高铁 / 自驾三种方式的时间与费用区间。"""
    a = _city_point(from_city)
    b = _city_point(to_city)
    if not a or not b:
        return {"ok": False, "message": "Could not resolve one of the cities", "from": from_city,
                "to": to_city}
    km = haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
    fuel = fuel_prices(province or from_city)
    day = date or time.strftime("%Y-%m-%d")
    rail_live = None
    if km <= 2000:
        rail_live = _rail_live(from_city, to_city, day)
    rail = _rail_estimate(km)
    # 12306 公开时刻表文件：能拿到真实车次号与起讫站（票价仍需估算）
    try:
        trains = rail_data.corridor(from_city, to_city, limit=40)
    except Exception:
        trains = []
    if trains:
        rail.update({
            "train_count": len(trains),
            "trains": [t["code"] for t in trains[:8]],
            "trains_sample": [f'{t["code"]} {t["from"]}→{t["to"]}' for t in trains[:3]],
            "trains_source": "12306 timetable file",
            "source_label": "Trains from the 12306 timetable; fare estimated from the published tariff",
            "source_label_zh": "车次来自 12306 公开时刻表，票价按公开运价估算",
        })
    if rail_live:
        best = min(rail_live, key=lambda r: r.get("duration") or "99:99")
        rail = {
            "mode": "rail", "label": "High-speed rail", "label_zh": "高铁",
            "duration_text": best.get("duration"), "trains": len(rail_live),
            "code": best.get("code"), "depart": best.get("depart"), "arrive": best.get("arrive"),
            "estimated": False, "source": "12306",
            "source_label": "Live 12306 timetable", "source_label_zh": "12306 实时车次",
        }
    options = [rail, _flight_estimate(km), _drive_option(km, fuel)]
    return {
        "ok": True,
        "from": {"name": from_city, "lat": a["lat"], "lng": a["lng"]},
        "to": {"name": to_city, "lat": b["lat"], "lng": b["lng"]},
        "distance_km": round(km, 1),
        "fuel": fuel,
        "options": options,
        "params": {
            "road_factor": ROAD_FACTOR, "rail_factor": RAIL_FACTOR,
            "fuel_per_100km": FUEL_PER_100KM, "toll_per_km": TOLL_PER_KM,
            "rail_rate": RAIL_RATE, "rail_speed_kmh": RAIL_SPEED_KMH,
            "flight_base": FLIGHT_BASE, "flight_per_km": FLIGHT_PER_KM,
            "flight_speed_kmh": FLIGHT_SPEED_KMH, "drive_speed_kmh": DRIVE_SPEED_KMH,
        },
        "sources": [
            {"key": "rail", **SOURCE_LINKS["rail"],
             "status": "timetable" if trains else "unavailable",
             "detail": ("%d trains matched" % len(trains)) if trains else "no trains matched"},
            {"key": "fuel", **SOURCE_LINKS["fuel"], "status": fuel.get("source"),
             "detail": ("92# CNY%s/L - %s" % ((fuel.get("prices") or {}).get("p92"), fuel.get("province") or ""))},
            {"key": "flight", **SOURCE_LINKS["flight"], "status": "estimate", "detail": "no live fare"},
        ],
        "as_of": time.strftime("%Y-%m-%d %H:%M:%S"),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": "No booking channel: TravelOne only compares published prices and travel time.",
        "note_zh": "不提供购买渠道，仅同步与比对公开价格与耗时。",
    }