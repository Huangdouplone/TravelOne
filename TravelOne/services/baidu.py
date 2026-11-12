# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""百度地图服务端能力封装：路线规划、地理编码、地点检索。

坐标约定：对外统一 GCJ02，调用百度接口前转换为 BD09，响应再转回 GCJ02。
未配置 BAIDU_MAP_SERVER_AK 时所有方法返回 None，由上层切换到本地估算。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple


from core import httpclient
from core.config import settings
from core.geo import bd09_to_gcj02, gcj02_to_bd09

log = logging.getLogger("baidu")

MODE_PATH = {
    "driving": "driving",
    "walking": "walking",
    "riding": "riding",
    "transit": "transit",
}


def _get(path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = f"{settings.baidu_api_host}{path}"
    params = dict(params)
    params["ak"] = settings.baidu_server_ak
    if path.endswith("v1/transit"):
        params.setdefault("output", "json")
    try:
        resp = httpclient.get(url, params=params, timeout=max(6, settings.request_timeout))
        data = resp.json()
    except Exception as exc:
        log.warning("baidu api %s failed: %s", path, exc)
        return None
    if str(data.get("status")) not in ("0", "None"):
        log.warning("baidu api %s status=%s msg=%s", path, data.get("status"), data.get("message"))
        return None
    return data


def _parse_path(path: str) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    for chunk in (path or "").split(";"):
        if not chunk.strip():
            continue
        parts = chunk.split(",")
        if len(parts) != 2:
            continue
        try:
            bd_lng = float(parts[0])
            bd_lat = float(parts[1])
        except ValueError:
            continue
        lat, lng = bd09_to_gcj02(bd_lat, bd_lng)
        points.append((lat, lng))
    return points


def route(origin: Tuple[float, float], destination: Tuple[float, float], mode: str = "driving") -> Optional[Dict[str, Any]]:
    """调用百度路线规划。origin/destination 为 (lat, lng) GCJ02。"""
    if not settings.server_route_enabled:
        return None
    path_name = MODE_PATH.get(mode)
    if not path_name:
        return None
    o_lat, o_lng = gcj02_to_bd09(*origin)
    d_lat, d_lng = gcj02_to_bd09(*destination)
    params = {
        "origin": f"{o_lat},{o_lng}",
        "destination": f"{d_lat},{d_lng}",
        "steps_info": "1",
        "coord_type": "bd09ll",
    }
    data = _get(f"/directionlite/v1/{path_name}", params)
    if not data:
        return None
    routes = (data.get("result") or {}).get("routes") or []
    if not routes:
        return None
    best = routes[0]
    steps: List[Dict[str, Any]] = []
    polyline: List[Tuple[float, float]] = []
    for step in best.get("steps") or []:
        pts = _parse_path(step.get("path", ""))
        polyline.extend(pts)
        instruction = step.get("instruction") or step.get("road_name") or ""
        steps.append({
            "instruction": str(instruction)[:120],
            "distance_m": step.get("distance") or 0,
            "duration_s": step.get("duration") or 0,
            "road": step.get("road_name") or "",
        })
    return {
        "source": "baidu",
        "mode": mode,
        "distance_km": round((best.get("distance") or 0) / 1000.0, 2),
        "duration_min": int(round((best.get("duration") or 0) / 60.0)),
        "toll": best.get("toll"),
        "traffic_lights": best.get("traffic_light_num"),
        "polyline": polyline[::2] if len(polyline) > 400 else polyline,
        "steps": steps[:40],
    }


def geocode(address: str, city: str = "") -> Optional[Dict[str, Any]]:
    if not settings.server_route_enabled:
        return None
    params = {"address": address}
    if city:
        params["city"] = city
    data = _get("/geocoding/v3/", params)
    if not data:
        return None
    result = data.get("result") or {}
    location = result.get("location") or {}
    if location.get("lat") is None:
        return None
    lat, lng = bd09_to_gcj02(float(location["lat"]), float(location["lng"]))
    return {"lat": lat, "lng": lng, "confidence": result.get("confidence"), "level": result.get("level")}


def place_search(query: str, city: str = "") -> List[Dict[str, Any]]:
    if not settings.server_route_enabled:
        return []
    params = {"query": query, "scope": "2", "page_size": "10", "page_num": "0"}
    if city:
        params["region"] = city
        params["city_limit"] = "true"
    data = _get("/place/v2/search", params)
    if not data:
        return []
    out = []
    for poi in data.get("results", []):
        loc = poi.get("location") or {}
        lat, lng = bd09_to_gcj02(float(loc.get("lat", 0)), float(loc.get("lng", 0)))
        out.append({
            "name": poi.get("name"),
            "address": poi.get("address"),
            "lat": lat,
            "lng": lng,
            "uid": poi.get("uid"),
        })
    return out