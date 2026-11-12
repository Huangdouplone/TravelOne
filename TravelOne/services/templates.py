# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""详情页固有模板与数据自适应规则。

解决的问题：新增 / 删除景点、酒店，价格波动、评分变化、图片或票种缺失时，
页面不需要改代码也不需要人工补齐条目——这里统一把「任意来源的记录」规整成
带默认值的标准结构，前端模板只依赖标准结构渲染。

约定：
- 缺失字段一律返回可判定的空值（None / [] / {}），并额外给出 `has_*` 标志，
  前端据此展示占位文案而不是报错或空白。
- 价格相关指标全部由数据实时计算（最低价、最高价、价差、波动比例、更新时间），
  不写死任何具体景点或酒店。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core import i18n


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def price_stats(offers: List[Dict[str, Any]], base_price: Optional[float] = None) -> Dict[str, Any]:
    """按平台报价计算最低 / 最高 / 价差 / 波动比例。

    只有一条报价或没有报价时也能给出稳定结构，前端无需分支判断。
    """
    # 免费景点（价格为 0）也要计入平台数量，否则会出现「1 个平台可订」的误判
    prices = [_as_float(o.get("price")) for o in offers]
    prices = [p for p in prices if p is not None and p >= 0]
    if not offers and base_price is not None and base_price > 0:
        prices = [float(base_price)]
    if not prices:
        return {
            "count": 0, "min": None, "max": None, "spread": 0.0,
            "avg": None, "volatility_pct": 0.0, "best_platform": "",
            "updated_at": "",
        }
    low, high = min(prices), max(prices)
    best = next((o for o in offers if _as_float(o.get("price")) == low), {})
    return {
        "count": len(prices),
        "min": round(low, 2),
        "max": round(high, 2),
        "spread": round(high - low, 2),
        "avg": round(sum(prices) / len(prices), 2),
        "volatility_pct": round((high - low) / low * 100, 1) if low else 0.0,
        "best_platform": best.get("platform", ""),
        "updated_at": max((str(o.get("updated_at") or "") for o in offers), default=""),
    }


def default_policy(raw: Optional[Dict[str, Any]], kind: str = "attraction") -> Dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    if kind == "hotel":
        return {
            "checkin": raw.get("checkin") or "Check-in after 14:00, check-out before 12:00 next day",
            "cancel": raw.get("cancel") or "Subject to the booking platform's refund policy",
            "child": raw.get("child") or "Child policy: please confirm with the hotel front desk",
            "summary": raw.get("summary") or "",
        }
    return {
        "free": raw.get("free") or "Subject to the venue's notice on the day of visit",
        "discount": raw.get("discount") or "Subject to the venue's notice on the day of visit",
        "booking": raw.get("booking") or "Advance real-name booking on official channels is recommended",
        "refund": raw.get("refund") or "Subject to the venue's refund and change policy",
        "summary": raw.get("summary") or "",
    }


POLICY_ZH = {
    "hotel": {
        "checkin": "14:00 后入住，次日 12:00 前退房",
        "cancel": "以预订平台退改规则为准",
        "child": "儿童政策请与酒店前台确认",
    },
    "attraction": {
        "free": "免票政策以景区当日公告为准",
        "discount": "优惠条件以景区当日公告为准",
        "booking": "建议通过官方渠道提前实名预约",
        "refund": "退改以景区规定为准",
    },
}


def policy_zh(raw: Optional[Dict[str, Any]], kind: str = "attraction") -> Dict[str, str]:
    """政策的中文版本：上游有中文原值就用原值，没有则给中文默认说明。"""
    raw = raw if isinstance(raw, dict) else {}
    defaults = POLICY_ZH["hotel" if kind == "hotel" else "attraction"]
    out = {}
    for key, fallback in defaults.items():
        value = str(raw.get(key) or "").strip()
        out[key] = value if value and any("一" <= ch <= "鿿" for ch in value) else fallback
    return out


def attraction_detail(item: Dict[str, Any]) -> Dict[str, Any]:
    """把任意景点记录规整为详情模板可消费的结构。"""
    gallery = [g for g in _as_list(item.get("gallery")) if isinstance(g, str) and g]
    if not gallery:
        gallery = [g for g in _as_list(item.get("photos")) if isinstance(g, str) and g]
    if not gallery and item.get("cover_image"):
        gallery = [item["cover_image"]]

    offers = [o for o in _as_list(item.get("offers")) if isinstance(o, dict)]
    tickets = [t for t in _as_list(item.get("ticket_types")) if isinstance(t, dict)]
    policy = default_policy(item.get("policy"), "attraction")
    stats = price_stats(offers, _as_float(item.get("price")))

    presents = {
        "gallery": len(gallery) > 0,
        "offers": len(offers) > 0,
        "tickets": len(tickets) > 0,
        "policy": any(policy.get(k) for k in ("free", "discount", "booking", "refund")),
        "metro": bool(item.get("nearest_metro")),
        "nearby_hotels": len(_as_list(item.get("nearby_hotels"))) > 0,
        "similar": len(_as_list(item.get("similar"))) > 0,
        "rating": _as_float(item.get("rating")) is not None,
        "price": _as_float(item.get("price")) is not None,
    }

    detail = dict(item)
    detail.update({
        "kind": "attraction",
        "gallery": gallery,
        "offers": offers,
        "ticket_types": [dict(t, name=t.get("name") or "",
                              name_zh=t.get("name") or "",
                              note_zh=t.get("note") or "",
                              note=i18n.note_en(t.get("note") or "")) for t in tickets],
        "policy": policy,
        "policy_zh": policy_zh(item.get("policy"), "attraction"),
        "intro_zh": item.get("intro_zh") or item.get("intro") or "",
        "open_time_zh": item.get("open_time_zh") or item.get("open_time") or "",
        "city_en": item.get("city_en") or i18n.city(item.get("city") or ""),
        "tags_en": item.get("tags_en") or i18n.tags(item.get("tags") or []),
        "price_stats": stats,
        "rating": _as_float(item.get("rating")),
        "review_count": _as_int(item.get("review_count")),
        "price": _as_float(item.get("price")),
        "original_price": _as_float(item.get("original_price")),
        "lat": _as_float(item.get("lat")),
        "lng": _as_float(item.get("lng")),
        "tags": [t for t in _as_list(item.get("tags")) if isinstance(t, str)],
        "nearby_hotels": [h for h in _as_list(item.get("nearby_hotels")) if isinstance(h, dict)],
        "similar": [s for s in _as_list(item.get("similar")) if isinstance(s, dict)],
        "has": presents,
        "template_version": 2,
    })
    return detail


def hotel_detail(item: Dict[str, Any]) -> Dict[str, Any]:
    """把任意酒店记录规整为详情模板可消费的结构。"""
    gallery = [g for g in _as_list(item.get("gallery")) if isinstance(g, str) and g]
    if not gallery:
        gallery = [g for g in _as_list(item.get("photos")) if isinstance(g, str) and g]
    if not gallery:
        gallery = [g for g in _as_list(item.get("images")) if isinstance(g, str) and g]
    if not gallery and item.get("cover_image"):
        gallery = [item["cover_image"]]
    offers = [o for o in _as_list(item.get("offers")) if isinstance(o, dict)]
    policy = default_policy(item.get("policy"), "hotel")
    stats = price_stats(offers, _as_float(item.get("price")))
    metro_distance = item.get("metro_distance_m")
    presents = {
        "gallery": len(gallery) > 0,
        "offers": len(offers) > 0,
        "policy": True,
        "metro": metro_distance is not None,
        "nearby_attractions": len(_as_list(item.get("nearby_attractions"))) > 0,
        "rating": _as_float(item.get("rating")) is not None,
    }
    detail = dict(item)
    detail.update({
        "kind": "hotel",
        "gallery": gallery,
        "offers": offers,
        "policy": policy,
        "policy_zh": policy_zh(item.get("policy"), "hotel"),
        "city_en": item.get("city_en") or i18n.city(item.get("city") or ""),
        "tags_en": item.get("tags_en") or i18n.tags(item.get("tags") or []),
        "price_stats": stats,
        "rating": _as_float(item.get("rating")),
        "review_count": _as_int(item.get("review_count")),
        "price": _as_float(item.get("price")),
        "original_price": _as_float(item.get("original_price")),
        "star": _as_int(item.get("star")) or 3,
        "metro_distance_m": _as_int(metro_distance) if metro_distance is not None else None,
        "tags": [t for t in _as_list(item.get("tags")) if isinstance(t, str)],
        "amenities": [t for t in _as_list(item.get("amenities")) if isinstance(t, str)],
        "nearby_attractions": [a for a in _as_list(item.get("nearby_attractions")) if isinstance(a, dict)],
        "price_basis": {
            "unit": "per_night",
            "unit_zh": "每晚",
            "source": item.get("price_source") or "",
            "source_zh": i18n.source_zh(item.get("price_source") or ""),
            "fetched_at": item.get("price_updated_at") or "",
            "rooms": len(offers),
            "tax_note": "Platform starting rate; taxes and service fees follow the platform checkout page",
            "tax_note_zh": "平台起价，税费与服务费以平台结算页为准",
            "formula": "Stay cost = nightly rate x nights",
            "formula_zh": "住宿费用 = 每晚价 × 住宿晚数",
        },
        "has": presents,
        "template_version": 2,
    })
    return detail


def dataset_bounds(items: List[Dict[str, Any]], price_key: str = "price",
                   rating_key: str = "rating") -> Dict[str, Any]:
    """返回当前数据集的评分 / 价格边界，供筛选器自适应（新增或删除记录后无需改前端）。"""
    prices = [_as_float(i.get(price_key)) for i in items]
    prices = [p for p in prices if p is not None]
    ratings = [_as_float(i.get(rating_key)) for i in items]
    ratings = [r for r in ratings if r is not None]
    return {
        "count": len(items),
        "price_min": round(min(prices), 2) if prices else 0,
        "price_max": round(max(prices), 2) if prices else 0,
        "rating_min": round(min(ratings), 2) if ratings else 0,
        "rating_max": round(max(ratings), 2) if ratings else 0,
        "free_count": sum(1 for p in prices if p == 0),
    }


def normalize_record(raw: Dict[str, Any], source: str = "thirdparty") -> Optional[Dict[str, Any]]:
    """把第三方接口返回的任意记录规整为景点入库结构；缺必填字段则丢弃。"""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or raw.get("title") or raw.get("scenicName") or "").strip()
    city = str(raw.get("city") or raw.get("cityName") or raw.get("region") or "").strip()
    if not name or not city:
        return None
    lat = _as_float(raw.get("lat") or raw.get("latitude"))
    lng = _as_float(raw.get("lng") or raw.get("longitude") or raw.get("lon"))
    if lat is not None and not (18 <= lat <= 54):
        lat = None
    if lng is not None and not (73 <= lng <= 135):
        lng = None
    price = _as_float(raw.get("price") or raw.get("lowPrice"))
    return {
        "source": source,
        "source_id": str(raw.get("source_id") or raw.get("id") or f"{source}-{city}-{name}"),
        "name": name,
        "city": city,
        "province": str(raw.get("province") or ""),
        "address": str(raw.get("address") or ""),
        "lat": lat,
        "lng": lng,
        "rating": _as_float(raw.get("rating") or raw.get("score")),
        "review_count": _as_int(raw.get("review_count") or raw.get("commentCount")),
        "price": price,
        "original_price": _as_float(raw.get("original_price")),
        "currency": "CNY",
        "price_note": "Free" if price == 0 else "From",
        "tags": [t for t in _as_list(raw.get("tags")) if isinstance(t, str)],
        "intro": str(raw.get("intro") or raw.get("description") or ""),
        "open_time": str(raw.get("open_time") or ""),
        "cover_image": str(raw.get("cover_image") or ""),
        "images": [i for i in _as_list(raw.get("images")) if isinstance(i, str)],
        "photos": [i for i in _as_list(raw.get("photos")) if isinstance(i, str)],
        "policy": raw.get("policy") if isinstance(raw.get("policy"), dict) else {},
        "offers": raw.get("offers") if isinstance(raw.get("offers"), list) else [],
        "ticket_types": raw.get("ticket_types") if isinstance(raw.get("ticket_types"), list) else [],
        "level": str(raw.get("level") or ""),
        "is_free": price == 0,
        "night_open": bool(raw.get("night_open")),
        "indoor": bool(raw.get("indoor")),
        "nature": bool(raw.get("nature")),
        "visit_minutes": _as_int(raw.get("visit_minutes")) or 120,
        "popularity": _as_int(raw.get("popularity")),
        "source_url": str(raw.get("source_url") or ""),
    }