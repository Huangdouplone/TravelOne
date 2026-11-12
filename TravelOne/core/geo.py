# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""地理计算工具：距离、投影、行程排序。

全部为纯 Python 实现，无第三方依赖，保证离线可用。
"""
from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

EARTH_RADIUS_KM = 6371.0088


def _rad(deg: float) -> float:
    return deg * math.pi / 180.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两点球面距离（公里）。坐标为 gcj02 或 wgs84 均可，仅用于相对估算。"""
    dlat = _rad(lat2 - lat1)
    dlng = _rad(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(_rad(lat1)) * math.cos(_rad(lat2)) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


def road_factor_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """把直线距离换算为更接近实际道路里程的估算距离。

    城内出行道路系数约 1.35，短距离受路口影响更大，长距离趋于平缓。
    """
    straight = haversine_km(lat1, lng1, lat2, lng2)
    if straight <= 0.4:
        factor = 1.55
    elif straight <= 2:
        factor = 1.42
    elif straight <= 8:
        factor = 1.34
    else:
        factor = 1.26
    return round(straight * factor, 2)


# 平均通行速度（km/h），用于无地图服务时的耗时估算。按里程分档，兼顾市区拥堵与跨城高速
SPEED_TIERS = {
    "driving": [(5, 22.0), (30, 30.0), (80, 45.0), (10 ** 9, 75.0)],
    "walking": [(10 ** 9, 4.6)],
    "riding": [(5, 12.0), (30, 15.0), (10 ** 9, 18.0)],
    "transit": [(5, 12.0), (30, 18.0), (80, 30.0), (10 ** 9, 55.0)],
}


def speed_for(distance_km: float, mode: str) -> float:
    for limit, speed in SPEED_TIERS.get(mode, SPEED_TIERS["driving"]):
        if distance_km <= limit:
            return speed
    return SPEED_TIERS.get(mode, SPEED_TIERS["driving"])[-1][1]


def estimate_minutes(distance_km: float, mode: str) -> int:
    speed = speed_for(distance_km, mode)
    minutes = distance_km / speed * 60.0
    # 起终点与换乘的固定开销
    overhead = {"driving": 6, "walking": 2, "riding": 3, "transit": 12}.get(mode, 6)
    return int(round(minutes + overhead))


def order_by_nearest(start: Tuple[float, float], points: Sequence[Tuple[float, float]]) -> List[int]:
    """最近邻路径排序，返回 points 的访问顺序索引。"""
    remaining = list(range(len(points)))
    ordered: List[int] = []
    cur = start
    while remaining:
        best_i = min(
            remaining,
            key=lambda i: haversine_km(cur[0], cur[1], points[i][0], points[i][1]),
        )
        ordered.append(best_i)
        cur = points[best_i]
        remaining.remove(best_i)
    return ordered


def two_opt(order: List[int], points: Sequence[Tuple[float, float]]) -> List[int]:
    """2-opt 局部优化，改善最近邻结果。"""
    if len(order) < 4:
        return order
    improved = True
    best = order[:]
    guard = 0
    while improved and guard < 50:
        improved = False
        guard += 1
        for i in range(1, len(best) - 2):
            for j in range(i + 2, len(best)):
                if j - i == 1:
                    continue
                new_order = best[:i] + best[i:j][::-1] + best[j:]
                if _path_length(new_order, points) + 1e-9 < _path_length(best, points):
                    best = new_order
                    improved = True
        order = best
    return best


def optimize_path(origin: Tuple[float, float], points: Sequence[Tuple[float, float]]) -> List[int]:
    """以 origin 为固定起点，对景点访问顺序做最近邻 + 2-opt 优化，返回景点索引序列。"""
    n = len(points)
    if n <= 1:
        return list(range(n))
    remaining = list(range(n))
    order: List[int] = []
    cur = origin
    while remaining:
        best_i = min(remaining, key=lambda i: haversine_km(cur[0], cur[1], points[i][0], points[i][1]))
        order.append(best_i)
        cur = points[best_i]
        remaining.remove(best_i)

    path = [origin] + [points[i] for i in order]
    improved = True
    guard = 0
    while improved and guard < 40:
        improved = False
        guard += 1
        for i in range(1, len(path) - 1):
            for j in range(i + 1, len(path)):
                candidate = path[:i] + path[i:j + 1][::-1] + path[j + 1:]
                if _path_length_seq(candidate) + 1e-9 < _path_length_seq(path):
                    path = candidate
                    improved = True
    # 还原为景点索引：path[0] 是起点
    lookup = {pt: idx for idx, pt in enumerate(points)}
    return [lookup[pt] for pt in path[1:]]


def _path_length_seq(seq: Sequence[Tuple[float, float]]) -> float:
    total = 0.0
    for a, b in zip(seq, seq[1:]):
        total += haversine_km(a[0], a[1], b[0], b[1])
    return total


def _path_length(order: Iterable[int], points: Sequence[Tuple[float, float]]) -> float:
    seq = list(order)
    total = 0.0
    for a, b in zip(seq, seq[1:]):
        total += haversine_km(points[a][0], points[a][1], points[b][0], points[b][1])
    return total


def mercator_xy(lat: float, lng: float) -> Tuple[float, float]:
    """Web 墨卡托投影，用于无地图底图时的离线示意图。"""
    x = _rad(lng)
    y = math.log(math.tan(math.pi / 4 + _rad(lat) / 2))
    return x, y


# ------------------------- 坐标系转换 -------------------------
_X_PI = math.pi * 3000.0 / 180.0
_EE = 0.00669342162296594323
_AXIS = 6378245.0


def _out_of_china(lat: float, lng: float) -> bool:
    return not (73.0 < lng < 135.0 and 18.0 < lat < 54.0)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_bd09(lat: float, lng: float) -> Tuple[float, float]:
    """火星坐标（多数公开 POI / 高德）转百度坐标。"""
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * _X_PI)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * _X_PI)
    bd_lng = z * math.cos(theta) + 0.0065
    bd_lat = z * math.sin(theta) + 0.006
    return round(bd_lat, 6), round(bd_lng, 6)


def bd09_to_gcj02(bd_lat: float, bd_lng: float) -> Tuple[float, float]:
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    return round(z * math.sin(theta), 6), round(z * math.cos(theta), 6)


def wgs84_to_gcj02(lat: float, lng: float) -> Tuple[float, float]:
    if _out_of_china(lat, lng):
        return lat, lng
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_AXIS * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (_AXIS / sqrtmagic * math.cos(radlat) * math.pi)
    return round(lat + dlat, 6), round(lng + dlng, 6)


def bounds(points: Sequence[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    return min(lats), min(lngs), max(lats), max(lngs)