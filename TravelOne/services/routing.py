# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""行程路线规划：直接消费行程中的条目快照，不查询任何数据库。

条目只需具备 name / lat / lng / visit_minutes，即可生成按天时间轴、
里程与耗时（配置百度服务端 AK 时使用百度实时路线，否则本地估算）。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.geo import estimate_minutes, optimize_path, road_factor_km
from services import baidu

MODES = {"driving": "Drive", "walking": "Walk", "riding": "Cycle", "transit": "Transit"}


def _fmt(dt: datetime, base: Optional[datetime] = None) -> str:
    if base is None:
        return dt.strftime("%H:%M")
    delta = (dt.date() - base.date()).days
    if delta <= 0:
        return dt.strftime("%H:%M")
    if delta == 1:
        return "Next day " + dt.strftime("%H:%M")
    return f"Day {delta + 1} " + dt.strftime("%H:%M")


def _parse_time(value: str) -> datetime:
    try:
        hour, minute = value.split(":")[:2]
        return datetime.now().replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    except Exception:
        return datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)


def _leg(a: Dict[str, Any], b: Dict[str, Any], mode: str, allow_remote: bool) -> Dict[str, Any]:
    if allow_remote and a.get("lat") and b.get("lat"):
        remote = baidu.route((a["lat"], a["lng"]), (b["lat"], b["lng"]), mode)
        if remote:
            remote["polyline"] = remote.get("polyline") or [[a["lat"], a["lng"]], [b["lat"], b["lng"]]]
            return remote
    distance = road_factor_km(a["lat"], a["lng"], b["lat"], b["lng"])
    minutes = estimate_minutes(distance, mode)
    mid_lat = (a["lat"] + b["lat"]) / 2 + (b["lng"] - a["lng"]) * 0.06
    mid_lng = (a["lng"] + b["lng"]) / 2 - (b["lat"] - a["lat"]) * 0.06
    return {
        "source": "estimate", "mode": mode, "distance_km": distance, "duration_min": minutes,
        "polyline": [[a["lat"], a["lng"]], [round(mid_lat, 6), round(mid_lng, 6)], [b["lat"], b["lng"]]],
        "steps": [{"instruction": f"{MODES.get(mode, mode)} ≈ {distance} km, about {minutes} min (local estimate)",
                   "distance_m": int(distance * 1000), "duration_s": minutes * 60, "road": ""}],
    }


def plan_route(items: List[Dict[str, Any]], mode: str = "driving",
               origin: Optional[Dict[str, Any]] = None, start_time: str = "09:00",
               optimize: bool = True, daily_limit_hours: float = 10.0,
               allow_remote: bool = True) -> Dict[str, Any]:
    mode = mode if mode in MODES else "driving"
    warnings: List[str] = []
    stops: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        key = item.get("key") or item.get("name")
        if key in seen:
            warnings.append(f"\"{item.get('name')}\" appeared twice and was merged into one stop")
            continue
        if item.get("lat") is None or item.get("lng") is None:
            warnings.append(f"\"{item.get('name')}\" has no coordinates and was skipped")
            continue
        seen.add(key)
        stops.append({
            "item_id": item.get("id"), "key": key, "name": item.get("name"),
            "city": item.get("city"), "address": item.get("address"),
            "lat": item["lat"], "lng": item["lng"],
            "rating": item.get("rating"), "price": item.get("price"),
            "cover_image": item.get("cover_image"), "tags": item.get("tags") or [],
            "kind": item.get("kind") or "attraction",
            "visit_minutes": int(item.get("visit_minutes") or (0 if item.get("kind") == "hotel" else 120)),
            "day": int(item.get("day") or 1),
        })
    if not stops:
        return {"ok": False, "message": "No usable places to plan with (coordinates may be missing).", "warnings": warnings}

    cities = sorted({s.get("city") for s in stops if s.get("city")})
    if len(cities) > 1:
        warnings.append("Multi-city trip (" + ", ".join(cities) + "); intercity legs use an intercity average and take longer")

    if origin and origin.get("lat") is not None:
        start = {"name": origin.get("name") or "Origin", "lat": float(origin["lat"]),
                 "lng": float(origin["lng"]), "is_origin": True}
    else:
        lats = [s["lat"] for s in stops]
        lngs = [s["lng"] for s in stops]
        start = {"name": (stops[0].get("city") or "Trip") + " center (auto)",
                 "lat": round(sum(lats) / len(lats), 6), "lng": round(sum(lngs) / len(lngs), 6),
                 "is_origin": True}

    days_out: List[Dict[str, Any]] = []
    total_distance = 0.0
    total_travel = 0
    total_visit = 0
    remote_used = False

    for day in sorted({s["day"] for s in stops}):
        day_stops = [s for s in stops if s["day"] == day]
        if optimize and len(day_stops) > 1:
            points = [(s["lat"], s["lng"]) for s in day_stops]
            order = optimize_path((start["lat"], start["lng"]), points)
            day_stops = [day_stops[i] for i in order]
            warnings.append(f"Day {day} reordered by shortest travel (nearest neighbour + 2-opt)")

        clock = _parse_time(start_time)
        base_clock = clock
        prev = start
        legs: List[Dict[str, Any]] = []
        stops_out: List[Dict[str, Any]] = []
        day_distance = 0.0
        day_travel = 0
        day_visit = 0
        for idx, stop in enumerate(day_stops):
            leg = _leg(prev, stop, mode, allow_remote)
            if leg.get("source") == "baidu":
                remote_used = True
            clock += timedelta(minutes=int(leg.get("duration_min") or 0))
            arrival = clock
            clock += timedelta(minutes=stop["visit_minutes"])
            departure = clock
            leg.update({"from": prev["name"], "to": stop["name"],
                        "from_lat": prev["lat"], "from_lng": prev["lng"],
                        "to_lat": stop["lat"], "to_lng": stop["lng"]})
            legs.append(leg)
            day_distance += float(leg.get("distance_km") or 0)
            day_travel += int(leg.get("duration_min") or 0)
            day_visit += stop["visit_minutes"]
            stops_out.append({
                "seq": idx + 1, "item_id": stop["item_id"], "key": stop["key"], "name": stop["name"],
                "address": stop["address"], "lat": stop["lat"], "lng": stop["lng"],
                "rating": stop["rating"], "price": stop["price"], "cover_image": stop["cover_image"],
                "tags": stop["tags"], "kind": stop["kind"],
                "arrive": _fmt(arrival, base_clock), "leave": _fmt(departure, base_clock),
                "visit_minutes": stop["visit_minutes"], "ticket": stop["price"],
            })
            prev = stop

        total_hours = round((day_travel + day_visit) / 60.0, 2)
        if total_hours > daily_limit_hours:
            warnings.append(f"Day {day} plans about {total_hours} h, above the {daily_limit_hours} h budget")
        days_out.append({
            "day": day, "city": day_stops[0].get("city") or "", "origin": start,
            "stops": stops_out, "legs": legs,
            "total_distance_km": round(day_distance, 2),
            "total_travel_min": day_travel, "total_visit_min": day_visit,
            "total_hours": total_hours, "start_time": start_time, "end_time": _fmt(clock, base_clock),
        })
        total_distance += day_distance
        total_travel += day_travel
        total_visit += day_visit

    # 住宿按晚数计：N 天行程有 N-1 晚，多店住宿平均分摊；门票只算非住宿停靠点
    nights = max(0, len(days_out) - 1)
    hotel_stops = [st for day in days_out for st in day["stops"] if (st.get("kind") or "") == "hotel"]
    if hotel_stops and nights == 0:
        # 单天行程里明确加了住宿，就按 1 晚计；否则住宿费永远是 0，容易误读
        nights = 1
    stay_cost = 0.0
    if hotel_stops:
        share = nights // len(hotel_stops) if nights else 0
        extra = nights % len(hotel_stops) if nights else 0
        for idx, stop in enumerate(hotel_stops):
            used = share + (1 if idx < extra else 0)
            stop["nights"] = used
            stop["stay_cost"] = round(float(stop.get("price") or 0) * used, 2)
            stay_cost += stop["stay_cost"]
            if not stop.get("price"):
                warnings.append("\"" + str(stop.get("name")) + "\" has no nightly rate; its stay cost is not included")
    ticket_cost = round(sum(float(st.get("price") or 0) for day in days_out
                            for st in day["stops"] if (st.get("kind") or "") != "hotel"), 2)
    return {
        "ok": True, "mode": mode, "mode_label": MODES[mode], "coord_type": "gcj02",
        "source": "baidu" if remote_used else "estimate",
        "source_label": "Live Baidu Maps route" if remote_used else "Local estimate (no Baidu server AK)",
        "days": days_out,
        "summary": {
            "days": len(days_out), "nights": nights, "stops": len(stops),
            "distance_km": round(total_distance, 2),
            "travel_min": total_travel, "visit_min": total_visit,
            "total_hours": round((total_travel + total_visit) / 60.0, 2),
            "ticket_cost": ticket_cost,
            "stay_cost": round(stay_cost, 2),
            "total_cost": round(ticket_cost + stay_cost, 2),
            "cost_note": "Tickets and stays are listed separately; stays = nightly rate x nights",
            "cost_note_zh": "门票与住宿分列；住宿 = 每晚价 × 住宿晚数",
        },
        "warnings": warnings,
    }