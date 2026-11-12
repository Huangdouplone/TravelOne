# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""生成参赛演示页：复用项目页面（app.html）的结构、样式与脚本，内嵌全量快照数据。

与上一版“另写版式”的离线页不同，这里直接拿项目构建产物 app.html，
只在其中注入两段东西：
1. `window.__OFFLINE_DATA__`：来自 data/cache 的全部城市快照（景点/酒店/地铁计数）；
2. 一个 fetch 拦截层：把 /api/* 请求就地用内嵌数据回答（含列表、搜索、详情、比价、
   行程与城际交通），因此 file:// 打开也能完整走流程，且不发起任何外部请求。

同时把门户区块（#overview）隐藏：参赛页进入就是应用内部视图，不再展示门户数据面板。

用法：python tools/build_offline_app.py [输出路径]
"""
from __future__ import annotations

import base64
import collections
import gzip
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import cache_store, i18n  # noqa: E402
from services import transport  # noqa: E402
try:
    from collectors.wikidata_places import LANDMARK_INFO  # noqa: E402
    LANDMARK_NAMES = {info.get("zh") for info in LANDMARK_INFO.values() if info.get("zh")}
except Exception:
    LANDMARK_NAMES = set()

APP_HTML = ROOT / "static" / "app.html"
DEFAULT_OUT = ROOT / "TravelOne-参赛静态页.html"


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _price(value: Any, limit: float = 3000) -> Any:
    if value in (None, ""):
        return None
    number = _num(value)
    return round(number, 1) if 0 <= number <= limit else None


def _room(value: Any) -> Any:
    if value in (None, ""):
        return None
    number = _num(value)
    return round(number, 1) if 0 < number <= 20000 else None


def _label(name: str) -> str:
    text = str(name or "").strip()
    for suffix in ("市", "地区", "自治州", "盟"):
        if text.endswith(suffix) and len(text) > 2:
            return text[: -len(suffix)]
    return text


def _text(value: Any, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def pack_attraction(item: Dict[str, Any], img: str = "") -> Dict[str, Any]:
    city = _label(item.get("city") or "")
    offers = []
    for offer in (item.get("offers") or [])[:4]:
        if not isinstance(offer, dict) or offer.get("price") in (None, ""):
            continue
        offers.append({
            "platform": offer.get("platform") or "",
            "platform_zh": offer.get("platform_zh") or offer.get("platform") or "",
            "price": _price(offer.get("price")),
            "updated_at": offer.get("updated_at") or "",
            "is_reference": bool(offer.get("is_reference")),
        })
    return {
        "key": "%s::%s" % (city, item.get("name")),
        "name": item.get("name"),
        "city": city,
        "city_en": i18n.city(city),
        "lat": round(_num(item.get("lat")), 4),
        "lng": round(_num(item.get("lng")), 4),
        "price": _price(item.get("price")),
        "original_price": _price(item.get("original_price"), 20000),
        "rating": round(_num(item.get("rating")), 1) or None,
        "review_count": int(_num(item.get("review_count"))),
        "level": item.get("level") or "",
        "is_free": bool(item.get("is_free")),
        "tags": [t for t in (item.get("tags") or []) if isinstance(t, str)][:3],
        "tags_en": [t for t in (item.get("tags_en") or []) if isinstance(t, str)][:3],
        "price_source": item.get("price_source") or "Baidu Maps",
        "price_note": _text(item.get("price_note"), 40),
        "price_updated_at": item.get("price_updated_at") or item.get("fetched_at") or "",
        "open_time": _text(item.get("open_time"), 60),
        "address": _text(item.get("address"), 80),
        "intro": _text(item.get("intro") or item.get("intro_zh"), 200),
        "offers": offers,
        "nearest_metro": item.get("nearest_metro") or "",
        "popularity": int(_num(item.get("popularity"))),
        "is_heritage": bool(item.get("heritage")),
        "mode": item.get("_mode") or "cn",
        "im": img,
    }


def pack_hotel(item: Dict[str, Any], img: str = "") -> Dict[str, Any]:
    city = _label(item.get("city") or "")
    return {
        "id": item.get("id") or item.get("source_id") or ("%s::%s" % (city, item.get("name"))),
        "name": item.get("name"),
        "city": city,
        "city_en": i18n.city(city),
        "lat": round(_num(item.get("lat")), 4),
        "lng": round(_num(item.get("lng")), 4),
        "price": _room(item.get("price")),
        "original_price": _room(item.get("original_price")),
        "star": int(_num(item.get("star")) or 3),
        "rating": round(_num(item.get("rating")), 1) or None,
        "review_count": int(_num(item.get("review_count"))),
        "price_source": item.get("price_source") or "Baidu Maps",
        "price_note": _text(item.get("price_note"), 60),
        "price_updated_at": item.get("price_updated_at") or item.get("fetched_at") or "",
        "metro_station": item.get("metro_station") or "",
        "metro_distance_m": item.get("metro_distance_m"),
        "metro_line": item.get("metro_line") or "",
        "address": _text(item.get("address"), 80),
        "tags": [t for t in (item.get("tags") or []) if isinstance(t, str)][:3],
        "amenities": [t for t in (item.get("amenities") or []) if isinstance(t, str)][:6],
        "mode": item.get("_mode") or "cn",
        "im": img,
    }


SHIM = r"""
window.__OfflineBoot = function(D){
  const byKey = new Map(), hotelById = new Map();
  D.attractions.forEach((a) => byKey.set(a.key, a));
  D.hotels.forEach((h) => hotelById.set(h.id, h));
  const IMG = D.images || {};
  const imgByName = new Map();
  D.attractions.forEach((a) => { if (a.im) imgByName.set(a.city + '::' + a.name, a.im); });
  D.hotels.forEach((h) => { if (h.im) imgByName.set(h.city + '::' + h.name, h.im); });
  function imgFor(name, city){
    const hash = imgByName.get((city || '') + '::' + (name || ''));
    return hash && IMG[hash] ? IMG[hash] : '';
  }
  function modeOf(params){
    return params.get('mode') === 'global' ? 'global' : 'cn';
  }

  const DEC = (n) => (n == null || n === '') ? null : Number(n);
  const R = 6371;
  function hav(a, b){
    const rad = Math.PI / 180;
    const dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad;
    const h = Math.sin(dLat/2)**2 + Math.cos(a.lat*rad) * Math.cos(b.lat*rad) * Math.sin(dLng/2)**2;
    return 2 * R * Math.asin(Math.sqrt(Math.min(1, h)));
  }
  function priceStats(list, base){
    const prices = (list || []).map((o) => DEC(o.price)).filter((p) => p !== null && p >= 0);
    if (!prices.length && base != null) prices.push(Number(base));
    if (!prices.length) return { count: 0, min: null, max: null, spread: 0, avg: null, volatility_pct: 0, best_platform: '', updated_at: '' };
    const low = Math.min(...prices), high = Math.max(...prices);
    const best = (list || []).find((o) => DEC(o.price) === low) || {};
    return {
      count: prices.length, min: Math.round(low * 100) / 100, max: Math.round(high * 100) / 100,
      spread: Math.round((high - low) * 100) / 100,
      avg: Math.round((prices.reduce((s, p) => s + p, 0) / prices.length) * 100) / 100,
      volatility_pct: low ? Math.round((high - low) / low * 1000) / 10 : 0,
      best_platform: best.platform_zh || best.platform || '',
      updated_at: (list || []).map((o) => o.updated_at || '').sort().pop() || ''
    };
  }
  function attractionDetail(a){
    const offers = (a.offers || []).map((o) => Object.assign({}, o, {
      code: 'offline', note: 'Snapshot quote', note_zh: '快照报价',
      live: false, specs: [], spec_label: 'Ticket type', spec_label_zh: '票种'
    }));
    const stats = priceStats(offers, a.price);
    const gallery = a.im && IMG[a.im] ? [IMG[a.im]] : [];
    return Object.assign({}, a, {
      kind: 'attraction', gallery: gallery, photos: gallery, offers,
      tags: a.tags || [], tags_en: a.tags_en || [], city_en: a.city_en,
      intro_zh: a.intro || '', open_time_zh: a.open_time || '',
      price_stats: stats,
      policy: { free: '', discount: '', booking: '', refund: '' },
      policy_zh: { free: '以景区公示为准', discount: '以景区公示为准', booking: '以景区公示为准', refund: '以景区公示为准' },
      has: {
        gallery: gallery.length > 0, offers: offers.length > 0, tickets: false, policy: true,
        metro: !!a.nearest_metro, nearby_hotels: false, similar: false,
        rating: a.rating !== null, price: a.price !== null
      },
      template_version: 2, source: 'offline'
    });
  }
  function hotelDetail(h){
    const offers = [{ platform: h.price_source || 'Baidu Maps',
      platform_zh: h.price_source ? (h.price_source.indexOf('Qunar') >= 0 ? '去哪儿（经百度地图）' : h.price_source) : '百度地图',
      code: 'offline', price: h.price, original_price: h.original_price,
      note: 'Snapshot nightly rate', note_zh: '快照房价（每晚起价）',
      live: false, updated_at: h.price_updated_at, specs: [], is_reference: false }];
    const stats = priceStats(offers, h.price);
    const gallery = h.im && IMG[h.im] ? [IMG[h.im]] : [];
    return Object.assign({}, h, {
      kind: 'hotel', gallery: gallery, photos: gallery, offers,
      tags: h.tags || [], tags_en: [], city_en: h.city_en,
      price_stats: stats,
      policy: { free: '', discount: '', booking: '', refund: '' },
      policy_zh: { free: '以酒店公示为准', discount: '以酒店公示为准', booking: '以酒店公示为准', refund: '以酒店公示为准' },
      price_basis: {
        unit: 'per_night', unit_zh: '每晚', source: h.price_source, source_zh: '去哪儿经百度地图',
        fetched_at: h.price_updated_at, rooms: 1,
        tax_note: 'Platform starting rate; taxes follow the platform', tax_note_zh: '平台起价，税费以平台结算页为准',
        formula: 'Stay cost = nightly rate x nights', formula_zh: '住宿费用 = 每晚价 × 住宿晚数'
      },
      has: { gallery: gallery.length > 0, offers: h.price !== null, policy: true, metro: !!h.metro_station,
        nearby_attractions: false, rating: h.rating !== null },
      template_version: 2, source: 'offline'
    });
  }
  function paginate(items, page, size){
    const total = items.length, p = Math.max(1, page || 1), s = Math.max(1, size || 12);
    return { ok: true, total, page: p, page_size: s, items: items.slice((p-1)*s, p*s), source: 'offline' };
  }
  function nearbyHotels(list, anchor, radius){
    if (!anchor || anchor.lat == null) return list;
    return list.map((h) => Object.assign({}, h, { distance_km: Math.round(hav(anchor, h) * 10) / 10 }))
      .filter((h) => h.distance_km <= (radius || 50))
      .sort((a, b) => a.distance_km - b.distance_km);
  }
  function tagFilter(list, tags){
    if (!tags) return list;
    const want = String(tags).split(',').map((t) => t.trim()).filter(Boolean);
    if (!want.length) return list;
    return list.filter((i) => (i.tags || []).some((t) => want.indexOf(t) >= 0));
  }
  function sortList(list, sort){
    const arr = list.slice();
    if (sort === 'price_asc') arr.sort((a, b) => (a.price ?? 1e9) - (b.price ?? 1e9));
    else if (sort === 'price_desc') arr.sort((a, b) => (b.price ?? -1) - (a.price ?? -1));
    else if (sort === 'rating') arr.sort((a, b) => (b.rating || 0) - (a.rating || 0));
    else if (sort === 'reviews') arr.sort((a, b) => (b.review_count || 0) - (a.review_count || 0));
    else arr.sort((a, b) => ((b.rating || 0) * 20 + (b.review_count || 0) / 50) - ((a.rating || 0) * 20 + (a.review_count || 0) / 50));
    return arr;
  }
  function attractions(params){
    const q = params.get('keyword') || '';
    const city = params.get('city') || '';
    const mode = modeOf(params);
    let list = D.attractions.filter((a) => (a.mode || 'cn') === mode);
    if (city && city !== 'all') list = list.filter((a) => a.city === city || a.city_en === city);
    if (q) list = list.filter((a) => (a.name || '').indexOf(q) >= 0 || (a.city || '').indexOf(q) >= 0);
    const minRating = Number(params.get('min_rating') || 0);
    if (minRating) list = list.filter((a) => (a.rating || 0) >= minRating);
    const minPrice = params.get('min_price'), maxPrice = params.get('max_price');
    if (minPrice) list = list.filter((a) => a.price != null && a.price >= Number(minPrice));
    if (maxPrice) list = list.filter((a) => a.price != null && a.price <= Number(maxPrice));
    const level = params.get('level');
    if (level) list = list.filter((a) => a.level === level);
    if (params.get('free') === '1') list = list.filter((a) => a.is_free || a.price === 0);
    list = tagFilter(list, params.get('tags'));
    const lat = params.get('lat'), lng = params.get('lng'), radius = Number(params.get('max_distance') || 0);
    if (lat && lng && radius){
      const anchor = { lat: Number(lat), lng: Number(lng) };
      list = list.map((a) => Object.assign({}, a, { distance_km: Math.round(hav(anchor, a) * 10) / 10 }))
        .filter((a) => a.distance_km <= radius).sort((a, b) => a.distance_km - b.distance_km);
    } else {
      list = sortList(list, params.get('sort') || 'recommend');
    }
    return paginate(list, Number(params.get('page') || 1), Number(params.get('page_size') || 12));
  }
  function hotels(params){
    const q = params.get('keyword') || '', city = params.get('city') || '';
    const mode = modeOf(params);
    let list = D.hotels.filter((h) => (h.mode || 'cn') === mode);
    if (city && city !== 'all') list = list.filter((h) => h.city === city || h.city_en === city);
    if (q) list = list.filter((h) => (h.name || '').indexOf(q) >= 0);
    const minPrice = params.get('min_price'), maxPrice = params.get('max_price');
    if (minPrice) list = list.filter((h) => h.price != null && h.price >= Number(minPrice));
    if (maxPrice) list = list.filter((h) => h.price != null && h.price <= Number(maxPrice));
    const star = params.get('star');
    if (star) list = list.filter((h) => String(h.star) === String(star));
    const nearKey = params.get('near');
    if (nearKey){
      const anchor = byKey.get(nearKey) || hotelById.get(nearKey);
      list = nearbyHotels(list, anchor, Number(params.get('max_distance') || 50));
    } else {
      list = sortList(list, params.get('sort') || 'recommend');
    }
    return paginate(list, Number(params.get('page') || 1), Number(params.get('page_size') || 12));
  }
  function search(params){
    const q = (params.get('q') || '').trim();
    const kind = params.get('kind') || 'all';
    const mode = modeOf(params);
    const page = Number(params.get('page') || 1), size = Number(params.get('page_size') || 12);
    if (!q) return { ok: true, total: 0, items: [], page, page_size: size, source: 'offline' };
    const words = q.split(/\s+/).filter(Boolean);
    const match = (item) => words.every((w) => (item.name || '').indexOf(w) >= 0
      || (item.name_en || '').toLowerCase().indexOf(w.toLowerCase()) >= 0
      || (item.city || '').indexOf(w) >= 0);
    const poolA = D.attractions.filter((x) => (x.mode || 'cn') === mode);
    const poolH = D.hotels.filter((x) => (x.mode || 'cn') === mode);
    const a = kind === 'hotel' ? [] : poolA.filter(match).map((x) => Object.assign({ kind: 'attraction' }, x));
    const h = kind === 'attraction' ? [] : poolH.filter(match).map((x) => Object.assign({ kind: 'hotel' }, x));
    const merged = sortList(a.concat(h), 'rating');
    const cityCount = new Set(merged.map((x) => x.city)).size;
    return { ok: true, total: merged.length, items: merged.slice((page-1)*size, page*size),
      page, page_size: size, source: 'offline', cities: cityCount };
  }
  function compare(params){
    const keys = (params.get('attractions') || '').split(',').filter(Boolean);
    const ids = (params.get('hotels') || '').split(',').filter(Boolean);
    const attractionsList = keys.map((k) => byKey.get(k)).filter(Boolean).map((a) => {
      const d = attractionDetail(a);
      return { key: d.key, name: d.name, city: d.city, city_en: d.city_en, rating: d.rating,
        review_count: d.review_count, price: d.price, offers: d.offers, price_source: d.price_source, policy: d.policy };
    });
    const hotelsList = ids.map((k) => hotelById.get(k)).filter(Boolean).map((h) => {
      const d = hotelDetail(h);
      return { id: d.id, name: d.name, city: d.city, city_en: d.city_en, star: d.star, rating: d.rating,
        price: d.price, offers: d.offers, price_source: d.price_source, metro_station: d.metro_station,
        metro_distance_m: d.metro_distance_m, platform_ratings: [] };
    });
    const platforms = [];
    attractionsList.concat(hotelsList).forEach((x) => (x.offers || []).forEach((o) => {
      const name = o.platform_zh || o.platform;
      if (name && platforms.indexOf(name) < 0) platforms.push(name);
    }));
    return { attractions: attractionsList, hotels: hotelsList, platforms: platforms.length ? platforms : ['快照数据'] };
  }
  const P = D.params;
  function transportData(params){
    const fromName = params.get('from') || '', toName = params.get('to') || '';
    const a = D.cities.find((c) => c.city === fromName || c.city_en === fromName);
    const b = D.cities.find((c) => c.city === toName || c.city_en === toName);
    if (!a || !b) return { ok: false, message: '城市快照不存在' };
    if (a.city === b.city) return { ok: false, message: '同城不需要城际交通' };
    const km = hav(a, b);
    const railKm = km * P.rail_factor, roadKm = km * P.road_factor;
    const railMin = Math.round(railKm / P.rail_speed_kmh * 60 + P.rail_stop_min);
    const fuel = D.fuel || { p92: 8.5, province: '北京', at: D.generated_at };
    const liters = roadKm / 100 * P.fuel_per_100km;
    const fuelCost = liters * fuel.p92, toll = roadKm * P.toll_per_km;
    const flightBase = P.flight_base + km * P.flight_per_km;
    return {
      ok: true,
      from: { name: a.city, lat: a.lat, lng: a.lng }, to: { name: b.city, lat: b.lat, lng: b.lng },
      distance_km: Math.round(km * 10) / 10,
      fuel: { province: fuel.province, prices: { p92: fuel.p92 }, source: 'snapshot', fetched_at: fuel.at },
      options: [
        { mode: 'rail', label: 'High-speed rail', label_zh: '高铁', duration_min: railMin,
          price_from: Math.round(railKm * P.rail_rate.second), price_to: Math.round(railKm * P.rail_rate.first),
          seats: 'second / first', estimated: true, source: 'estimate',
          source_label: 'Fare = rail mileage x published tariff', source_label_zh: '票价 = 铁路里程 × 公开运价规则',
          breakdown_label: 'Rail mileage ' + Math.round(railKm) + ' km x CNY0.46-0.74/km',
          breakdown_label_zh: '铁路里程 ' + Math.round(railKm) + ' km × 0.46–0.74 元/公里；耗时按 ' + P.rail_speed_kmh + ' km/h + ' + P.rail_stop_min + ' 分钟停站',
          source_url: 'https://www.12306.cn/', train_count: null },
        { mode: 'flight', label: 'Flight', label_zh: '飞机',
          duration_min: Math.round(km / P.flight_speed_kmh * 60 + P.flight_overhead_min),
          price_from: Math.round(flightBase * 0.75), price_to: Math.round(flightBase * 1.35),
          seats: 'economy', estimated: true, source: 'estimate',
          source_label: 'Estimated from distance; airline APIs need signed sessions',
          source_label_zh: '按航距估算（机票接口需签名，无匿名报价源）',
          breakdown_label: 'Base CNY280 + ' + Math.round(km) + ' km x CNY0.35/km',
          breakdown_label_zh: '基础价 280 元 + ' + Math.round(km) + ' km × 0.35 元/km，区间 ×0.75–1.35' },
        { mode: 'drive', label: 'Self-drive', label_zh: '自驾',
          duration_min: Math.round(roadKm / P.drive_speed_kmh * 60),
          price_from: Math.round(fuelCost), price_to: Math.round(fuelCost + toll),
          seats: 'fuel / fuel + toll', distance_km: Math.round(roadKm * 10) / 10,
          liters: Math.round(liters * 10) / 10, fuel_price: fuel.p92, fuel_source: 'snapshot',
          estimated: true, source: 'fuel+estimate',
          source_label: 'Fuel price from snapshot; tolls and consumption are stated assumptions',
          source_label_zh: '油价来自快照；油耗与通行费按下述参数计算',
          breakdown_label_zh: '油费 ' + Math.round(roadKm) + ' km ÷ 100 × ' + P.fuel_per_100km + ' L × ' + fuel.p92 + ' 元 = ' + Math.round(fuelCost) + ' 元；通行费 ' + Math.round(roadKm) + ' km × ' + P.toll_per_km + ' 元 = ' + Math.round(toll) + ' 元' }
      ],
      params: P, sources: D.sources || [], as_of: D.generated_at
    };
  }
  // 行程：localStorage 持久化 + 简化的路线规划（最近邻 + 按天分配）
  const TRIP_KEY = 'travelone.offline.trips';
  function trips(){
    try { return JSON.parse(localStorage.getItem(TRIP_KEY) || '{}'); } catch (e) { return {}; }
  }
  function saveTrips(t){ try { localStorage.setItem(TRIP_KEY, JSON.stringify(t)); } catch (e) {} }
  function nextTripId(t){ return Math.max(0, ...Object.keys(t).map(Number)) + 1; }
  function itemOf(body){
    const key = body.key || body.id;
    const attr = byKey.get(key), hotel = hotelById.get(key);
    const src = attr || hotel;
    if (!src) return null;
    return { id: Date.now() + Math.floor(Math.random()*1000), key, key_type: attr ? 'attraction' : 'hotel',
      name: src.name, attraction_name: src.name, address: src.address || '',
      city: src.city, city_en: src.city_en, lat: src.lat, lng: src.lng,
      price: src.price, kind: attr ? 'attraction' : 'hotel', day: Number(body.day || 1),
      rating: src.rating, visit_minutes: attr ? 120 : 0, cover_image: '' };
  }
  function round1(v){ return Math.round(v * 10) / 10; }
  function fmtClock(min){
    const m = ((Math.round(min) % 1440) + 1440) % 1440;
    return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
  }
  function planTrip(items, opts){
    opts = opts || {};
    if (!items.length) return { ok: false, message: '还没有可规划的地点', warnings: [] };
    const mode = opts.mode || 'driving';
    const modeLabel = { driving: 'Self-drive', walking: 'Walking', cycling: 'Cycling', transit: 'Transit' }[mode] || 'Self-drive';
    const speed = mode === 'walking' ? 5 : (mode === 'cycling' ? 15 : 40);
    const startTime = opts.start_time || '09:00';
    const [sh, sm] = startTime.split(':').map((n) => Number(n) || 0);
    const daysList = [...new Set(items.map((i) => i.day || 1))].sort((a, b) => a - b);
    const hotels = items.filter((i) => i.kind === 'hotel');
    const nights = Math.max(0, daysList.length - 1) || (hotels.length ? 1 : 0);
    let totalDist = 0, totalTravel = 0, totalVisit = 0;
    const outDays = daysList.map((day) => {
      const group = items.filter((i) => (i.day || 1) === day);
      const left = group.slice(), ordered = [];
      let cur = { lat: group[0].lat, lng: group[0].lng };
      while (left.length){
        left.sort((a, b) => hav(cur, a) - hav(cur, b));
        const next = left.shift();
        ordered.push(next); cur = next;
      }
      let clock = sh * 60 + sm;
      let dayDist = 0;
      const stops = [], legs = [];
      let prev = null;
      ordered.forEach((stop, idx) => {
        const legKm = prev ? hav(prev, stop) : 0;
        const legMin = prev ? Math.round(legKm / speed * 60) + (legKm > 1 ? 8 : 0) : 0;
        clock += legMin;
        const arrive = clock;
        clock += (stop.visit_minutes || 60);
        dayDist += legKm;
        totalTravel += legMin;
        totalVisit += (stop.visit_minutes || 60);
        stops.push({
          key: stop.key, name: stop.name, lat: stop.lat, lng: stop.lng, kind: stop.kind,
          ticket: stop.price, price: stop.price, distance_km: round1(legKm),
          arrive: fmtClock(arrive), leave: fmtClock(clock), arrive_at: arrive, leave_at: clock,
          visit_minutes: stop.visit_minutes || 60, seq: idx + 1
        });
        legs.push({ from: prev ? prev.name : '起点', to: stop.name,
          distance_km: round1(legKm), duration_min: legMin, source: 'estimate' });
        prev = stop;
      });
      totalDist += dayDist;
      return {
        day, origin: { name: '起点（城市中心）', lat: group[0].lat, lng: group[0].lng },
        start_time: startTime, end_time: fmtClock(clock),
        total_distance_km: round1(dayDist), stops, legs
      };
    });
    const tickets = items.filter((i) => i.kind !== 'hotel').reduce((sum, i) => sum + (i.price || 0), 0);
    const stay = hotels.reduce((sum, h) => sum + (h.price || 0) * Math.max(1, nights), 0);
    return {
      ok: true, mode, mode_label: modeLabel, source: 'estimate',
      source_label: 'Local estimate (no live routing in offline snapshot)',
      coordinate_type: 'gcj02',
      days: outDays,
      summary: {
        days: daysList.length, nights, stops: items.length,
        distance_km: round1(totalDist), travel_min: totalTravel, visit_min: totalVisit,
        total_hours: Math.round((totalTravel + totalVisit) / 60 * 100) / 100,
        ticket_cost: Math.round(tickets), stay_cost: Math.round(stay),
        total_cost: Math.round(tickets + stay),
        cost_note: 'Tickets and stays are listed separately', cost_note_zh: '门票与住宿分列；住宿按晚数计'
      },
      warnings: []
    };
  }
  function json(data, status){
    return new Response(JSON.stringify(data), { status: status || 200, headers: { 'Content-Type': 'application/json' } });
  }
  const realFetch = window.fetch.bind(window);
  window.fetch = async function(input, init){
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.indexOf('/api/') !== 0 && url.indexOf('api/') !== 0) return realFetch(input, init);
    const u = new URL(url, location.href);
    const p = u.pathname.replace(/^.*?\/api\//, '/api/');
    const q = u.searchParams;
    const method = ((init && init.method) || 'GET').toUpperCase();
    const body = (() => { try { return init && init.body ? JSON.parse(init.body) : {}; } catch (e) { return {}; } })();

    if (p === '/api/health') return json({ ok: true, service: 'TravelOne', mode: 'offline-snapshot', database: false });
    if (p === '/api/meta') return json(D.meta[modeOf(q)] || D.meta.cn);
    if (p === '/api/config') return json({ map_enabled: false, server_route_enabled: false, offline: true });
    if (p === '/api/map/guide') return json({ title: '离线演示', links: [] });
    if (p === '/api/platforms') return json({ platforms: D.platforms || [] });
    if (p === '/api/sources') {
      const mode = modeOf(q);
      const meta = D.meta[mode] || D.meta.cn;
      const payload = JSON.parse(JSON.stringify(D.sourcesPayload));
      payload.builtin.cache = { snapshots: meta.cities.length, by_kind: meta.counts };
      payload.builtin.coverage.tracked = { attractions: meta.counts.attractions, hotels: meta.counts.hotels };
      payload.builtin.coverage.places_discovered = meta.cities.length;
      payload.builtin.coverage.places_scanned = meta.cities.length;
      payload.builtin.label = mode === 'global' ? '国际版 · Wikidata 离线快照' : '离线快照（参赛演示）';
      payload.builtin.note = mode === 'global'
        ? '地点与坐标来自 Wikidata 快照，已内嵌；不发起网络请求。价格与评分通常为空。'
        : payload.builtin.note;
      return json(payload);
    }
    if (p === '/api/coverage') return json({ ok: true, ...D.coverage });
    if (p === '/api/live/health') return json({ ok: true, live: false, note: 'offline snapshot' });
    if (p === '/api/live/cache') return json({ ok: true, removed: 0 });
    if (p === '/api/crypto/session') return json({ sid: 'offline', key: btoa('0'.repeat(32)) });
    if (p === '/api/collect/status') return json({ state: { running: false, interval_seconds: 0 }, runs: [], coverage: D.coverage });
    if (p === '/api/collect') return json({ ok: false, message: '这是离线演示页，不发起抓取' }, 400);
    if (p === '/api/fuel') return json({ ok: true, ...(D.fuelPayload || {}) });
    if (p === '/api/reference') return json({ ok: true, meta: {}, count: 0, items: [] });
    if (p === '/api/search') return json(search(q));
    if (p === '/api/attractions') return json(attractions(q));
    if (p.indexOf('/api/attractions/') === 0){
      const key = decodeURIComponent(p.substring('/api/attractions/'.length));
      const a = byKey.get(key);
      return a ? json(attractionDetail(a)) : json({ ok: false, message: '快照中没有这条景点' }, 404);
    }
    if (p === '/api/hotels') return json(hotels(q));
    if (p === '/api/hotels/simple') return json(hotels(q));
    if (p.indexOf('/api/hotels/') === 0){
      const id = decodeURIComponent(p.substring('/api/hotels/'.length));
      const h = hotelById.get(id);
      return h ? json(hotelDetail(h)) : json({ ok: false, message: '快照中没有这家酒店' }, 404);
    }
    if (p === '/api/compare') return json(compare(q));
    if (p === '/api/transport') return json(transportData(q));
    if (p === '/api/geocode') {
      const name = q.get('q') || '';
      const hit = D.cities.find((c) => c.city === name) || D.attractions.find((a) => (a.name || '').indexOf(name) >= 0);
      return json(hit ? { ok: true, name: hit.name || hit.city, lat: hit.lat, lng: hit.lng } : { ok: false });
    }
    if (p === '/api/trips' && method === 'POST'){
      const t = trips(); const id = nextTripId(t);
      t[id] = { id, title: body.title || '离线行程', items: [], created_at: new Date().toISOString() };
      saveTrips(t); return json({ ok: true, trip: t[id] }, 201);
    }
    let m = p.match(/^\/api\/trips\/(\d+)$/);
    if (m && method === 'GET'){
      const t = trips(); const trip = t[m[1]];
      return trip ? json({ ok: true, trip }) : json({ ok: false, message: 'not found' }, 404);
    }
    m = p.match(/^\/api\/trips\/(\d+)\/items$/);
    if (m && method === 'POST'){
      const t = trips(); const trip = t[m[1]];
      if (!trip) return json({ ok: false, message: 'not found' }, 404);
      const item = itemOf(body);
      if (!item) return json({ ok: false, message: '快照里没有这个地点' }, 404);
      if (trip.items.some((i) => i.key === item.key)) return json({ ok: false, message: '已在行程中' }, 400);
      trip.items.push(item); saveTrips(t); return json({ ok: true, item, trip });
    }
    if (m && method === 'PUT'){
      const t = trips(); const trip = t[m[1]];
      if (!trip) return json({ ok: false, message: 'not found' }, 404);
      (body.items || []).forEach((upd) => {
        const target = trip.items.find((i) => i.id === upd.id);
        if (target) Object.assign(target, upd);
      });
      saveTrips(t); return json({ ok: true, trip });
    }
    m = p.match(/^\/api\/trips\/(\d+)\/items\/(\d+)$/);
    if (m && method === 'DELETE'){
      const t = trips(); const trip = t[m[1]];
      if (trip) trip.items = trip.items.filter((i) => String(i.id) !== m[2]);
      saveTrips(t); return json({ ok: true, trip });
    }
    m = p.match(/^\/api\/trips\/(\d+)\/plan$/);
    if (m && method === 'POST'){
      const t = trips(); const trip = t[m[1]];
      if (!trip) return json({ ok: false, message: 'not found' }, 404);
      const plan = planTrip(trip.items, body);
      plan.trip = { id: trip.id, title: trip.title, city: trip.city };
      return json(plan);
    }
    return json({ ok: false, message: '离线演示页不支持这个接口：' + p }, 404);
  };

  // 图片占位：所有封面改成本地 SVG，避免任何外部请求
  const COVER = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
    '<stop offset="0" stop-color="#0d3b36"/><stop offset="1" stop-color="#1b7d66"/></linearGradient></defs>' +
    '<rect width="400" height="300" fill="url(%23g)"/><text x="200" y="158" font-size="20" fill="#d6ece4" text-anchor="middle" font-family="sans-serif">TravelOne 离线快照</text></svg>');
  window.offlineCover = function(name, city){
    const hit = imgFor(name, city);
    return hit || COVER;
  };

  document.addEventListener('DOMContentLoaded', function(){
    // 离线页不加载任何在线底图：统一走本地示意图
    if (window.TravelMap && window.TravelMap.create){
      const originalCreate = window.TravelMap.create;
      window.TravelMap.create = function(el, opts){
        return originalCreate(el, Object.assign({}, opts, { mode: 'cn', ak: '' })).then(function(result){
          const note = document.getElementById('mapNote');
          if (note) note.textContent = '离线示意图 · 不请求地图瓦片';
          return result;
        });
      };
    }
    if (window.API) {
      window.API.cover = function(name, city){ return window.offlineCover(name, city); };
      window.API.isFileMode = function(){ return false; };
      window.API.encryptPayload = async function(obj){ return { plain: obj }; };
    }
  });
  window.addEventListener('load', function(){
    if (window.API && window.offlineCover) {
      window.API.cover = function(name, city){ return window.offlineCover(name, city); };
    }
  });
};
"""


BOOT = r"""
(function(){
  // 数据以 gzip + base64 内嵌，先把应用初始化挂起，解压完成后再统一触发
  const pending = [];
  const add = document.addEventListener.bind(document);
  document.addEventListener = function(type, fn, opts){
    if (type === 'DOMContentLoaded' && typeof fn === 'function') { pending.push(fn); return; }
    return add(type, fn, opts);
  };
  function fire(){
    const list = pending.splice(0);
    list.forEach(function(fn){
      try { fn(new Event('DOMContentLoaded')); } catch (err) { console.error(err); }
    });
  }
  async function boot(){
    if (!('DecompressionStream' in window)) throw new Error('当前浏览器不支持 DecompressionStream，请使用新版 Edge/Chrome');
    const b64 = window.__OFFLINE_B64__ || '';
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const text = await new Response(stream).text();
    const data = JSON.parse(text);
    window.__OFFLINE_DATA__ = data;
    window.__OfflineBoot(data);
    if (window.API && window.offlineCover) {
      window.API.cover = function(name, city){ return window.offlineCover(name, city); };
    }
    document.addEventListener = add;
    if (document.readyState === 'loading') add('DOMContentLoaded', fire); else fire();
  }
  boot().catch(function(err){
    console.error(err);
    if (document.body) {
      document.body.innerHTML = '<pre style="padding:24px;white-space:pre-wrap">离线数据解压失败：' + (err && err.message ? err.message : err) + '</pre>';
    }
  });
})();
"""

OFFLINE_CSS = """
/* 参赛演示页：顶部固定展示声明 */
#offlineBanner { position: fixed; top: 0; left: 0; right: 0; height: 34px; z-index: 99999;
  display: flex; align-items: center; justify-content: center; gap: 10px;
  background: #0d3b36; color: #e7f4ee; font-size: 13px; letter-spacing: .3px;
  box-shadow: 0 2px 10px rgba(0,0,0,.18); }
#offlineBanner b { font-weight: 600; color: #fff; }
#offlineBanner span { color: #b9d8cb; }
body { padding-top: 34px !important; }
@media (max-width: 620px) { #offlineBanner { height: 30px; font-size: 12px; } body { padding-top: 30px !important; } }
/* 参赛演示页：门户区块不展示数据，直接进入应用内部视图 */
#overview { display: none !important; }
.nav-item[data-target="overview"] { display: none !important; }
/* 离线快照同时含国内与国际数据，保留国内/国际切换 */
"""


def load_images() -> Dict[str, Any]:
    """读取抓好的实景图：返回 key->hash 映射与 hash->dataURI 表。"""
    map_file = ROOT / "logs" / "image_map.json"
    img_dir = ROOT / "data" / "images"
    mapping: Dict[str, str] = {}
    images: Dict[str, str] = {}
    try:
        mapping = json.loads(map_file.read_text(encoding="utf-8"))
    except Exception:
        return {"map": {}, "images": {}}
    filenames = set(str(v) for v in mapping.values())
    try:
        scenes = json.loads((ROOT / "logs" / "city_scenes.json").read_text(encoding="utf-8"))
        for values in scenes.values():
            if isinstance(values, list):
                filenames.update(str(v) for v in values if v)
    except Exception:
        pass
    for filename in filenames:
        path = img_dir / str(filename)
        if not path.exists():
            continue
        digest = path.stem
        if digest in images:
            continue
        try:
            payload = base64.b64encode(path.read_bytes()).decode("ascii")
            images[digest] = "data:image/webp;base64," + payload
        except Exception:
            continue
    return {"map": mapping, "images": images}


def scoped_items(kind: str) -> List[Dict[str, Any]]:
    """按 scope 读取，给条目标注 cn / global，供离线页按模式过滤。"""
    out: List[Dict[str, Any]] = []
    for scope in cache_store.scopes(kind):
        mode = "global" if str(scope).startswith("intl::") else "cn"
        for item in cache_store.items(kind, scope):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            row["_mode"] = mode
            out.append(row)
    return out


def build_payload() -> Dict[str, Any]:
    attractions_raw = [a for a in scoped_items("attraction") if a.get("name") and a.get("lat")]
    hotels_raw = [h for h in scoped_items("hotel") if h.get("name")]
    metro_raw = [m for m in scoped_items("metro") if m.get("name")]

    media = load_images()
    img_map = media["map"]
    images = media["images"]

    def _norm_city(value: str) -> str:
        text = str(value or "").strip()
        for suffix in ("自治州", "自治县", "地区", "特别行政区", "市", "县", "区", "州", "盟", "旗"):
            if text.endswith(suffix) and len(text) > len(suffix) + 1:
                text = text[: -len(suffix)]
                break
        return text

    cover_lookup = {}
    for key, value in img_map.items():
        if key.endswith("::"):
            cover_lookup.setdefault(_norm_city(key[:-2]), value)
    cover_keys = sorted(cover_lookup, key=len, reverse=True)

    def _find_cover(city: str) -> str:
        norm = _norm_city(city)
        if norm in cover_lookup:
            return cover_lookup[norm]
        for key in cover_keys:
            if len(key) >= 2 and (norm.startswith(key) or key.startswith(norm)):
                return cover_lookup[key]
        return ""

    scenes_file = ROOT / "logs" / "city_scenes.json"
    try:
        scenes_raw = json.loads(scenes_file.read_text(encoding="utf-8"))
    except Exception:
        scenes_raw = {}
    scene_lookup: Dict[str, List[str]] = {}
    for key, values in scenes_raw.items():
        if isinstance(values, list) and values:
            scene_lookup.setdefault(_norm_city(key), [str(v) for v in values if v])

    def _pool(city: str) -> List[str]:
        norm = _norm_city(city)
        if scene_lookup.get(norm):
            return scene_lookup[norm]
        for key in sorted(scene_lookup, key=len, reverse=True):
            if len(key) >= 2 and (norm.startswith(key) or key.startswith(norm)):
                return scene_lookup[key]
        cover = _find_cover(city)
        return [cover] if cover else []

    exact_counts = collections.Counter(v for k, v in img_map.items() if not k.endswith("::"))
    counters: Dict[tuple, int] = {}

    def _img_for(city: str, name: str, exact_ok: bool, kind: str) -> str:
        # 同城按条目顺序轮转组图，保证首屏 12 张里每张图最多出现 1–2 次
        counter_key = (kind, city)
        index = counters.get(counter_key, 0)
        counters[counter_key] = index + 1
        if exact_ok:
            value = img_map.get("%s::%s" % (city, name), "")
            # 同一文件被多个条目复用，多半是平台默认图，改用城市组图
            if value and exact_counts.get(value, 0) == 1:
                return Path(value).stem
        pool = _pool(city)
        if not pool:
            return ""
        return Path(pool[index % len(pool)]).stem

    def _exact_ok(item: Dict[str, Any]) -> bool:
        if item.get("_mode") == "global":
            return str(item.get("name") or "") in LANDMARK_NAMES
        return bool(item.get("cover_image") or item.get("photos"))

    attractions = [pack_attraction(a, _img_for(_label(a.get("city") or ""), a.get("name"), _exact_ok(a), "a"))
                   for a in attractions_raw]
    hotels = [pack_hotel(h, _img_for(_label(h.get("city") or ""), h.get("name"), _exact_ok(h), "h"))
              for h in hotels_raw]

    # 只把实际引用到的图片内嵌，避免历史映射里的废图占用体积
    used_images = {row.get("im") for row in attractions + hotels if row.get("im")}
    images = {key: value for key, value in images.items() if key in used_images}

    def build_meta(kind_attractions, kind_hotels, priority, metro_count):
        city_counts: Dict[str, Dict[str, Any]] = {}
        for a in kind_attractions:
            row = city_counts.setdefault(a["city"], {"city": a["city"], "city_en": a["city_en"],
                                                     "count": 0, "hotels": 0, "lat": 0.0, "lng": 0.0, "_n": 0})
            row["count"] += 1
            row["lat"] += a["lat"]; row["lng"] += a["lng"]; row["_n"] += 1
        for h in kind_hotels:
            row = city_counts.setdefault(h["city"], {"city": h["city"], "city_en": h["city_en"],
                                                     "count": 0, "hotels": 0, "lat": 0.0, "lng": 0.0, "_n": 0})
            row["hotels"] += 1
            if not row["_n"]:
                row["lat"] += h["lat"]; row["lng"] += h["lng"]; row["_n"] += 1
        cities = []
        for row in city_counts.values():
            n = max(1, row.pop("_n"))
            row["lat"] = round(row["lat"] / n, 3)
            row["lng"] = round(row["lng"] / n, 3)
            cities.append(row)

        def _rank(row):
            name = row["city"]
            return (priority.index(name) if name in priority else len(priority),
                    -(row["count"] + row["hotels"]))
        cities.sort(key=_rank)

        tags_count: Dict[str, int] = {}
        tag_en: Dict[str, str] = {}
        for a in kind_attractions:
            for i, tag in enumerate(a.get("tags") or []):
                tags_count[tag] = tags_count.get(tag, 0) + 1
                tag_en.setdefault(tag, (a.get("tags_en") or [""])[i] if i < len(a.get("tags_en") or []) else tag)
        tags = [t for t, _ in sorted(tags_count.items(), key=lambda kv: -kv[1])[:28]]
        levels = sorted({a.get("level") for a in kind_attractions if a.get("level")})
        return {
            "cities": cities, "tags": tags, "tag_en": tag_en, "levels": levels,
            "counts": {"attractions": len(kind_attractions), "hotels": len(kind_hotels),
                       "metro": metro_count},
            "offline": True,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    attractions_cn = [a for a in attractions if (a.get("mode") or "cn") == "cn"]
    hotels_cn = [h for h in hotels if (h.get("mode") or "cn") == "cn"]
    attractions_global = [a for a in attractions if a.get("mode") == "global"]
    hotels_global = [h for h in hotels if h.get("mode") == "global"]
    metro_cn = [m for m in metro_raw if (m.get("_mode") or "cn") == "cn"]
    metro_global = [m for m in metro_raw if m.get("_mode") == "global"]
    meta_cn = build_meta(attractions_cn, hotels_cn,
                         ["北京", "上海", "广州", "深圳", "成都", "重庆", "杭州", "西安",
                          "南京", "武汉", "天津", "长沙", "苏州", "青岛", "厦门"], len(metro_cn))
    meta_global = build_meta(attractions_global, hotels_global,
                             ["巴黎", "伦敦", "东京", "纽约", "罗马", "巴塞罗那", "新加坡",
                              "迪拜", "首尔", "悉尼", "曼谷", "阿姆斯特丹"], len(metro_global))
    meta = {"cn": meta_cn, "global": meta_global}

    cities = []
    seen_city = set()
    for row in meta_cn["cities"] + meta_global["cities"]:
        mark = row["city"]
        if mark in seen_city:
            continue
        seen_city.add(mark)
        cities.append(row)

    fuel = transport.fuel_prices("北京")
    prices = fuel.get("prices") or {}
    fuel_info = {"p92": prices.get("p92") or 8.5, "province": fuel.get("province") or "北京",
                 "source": fuel.get("source"), "at": fuel.get("fetched_at") or time.strftime("%Y-%m-%d %H:%M")}

    platform_counts: Dict[str, int] = {}
    for a in attractions:
        for offer in a.get("offers") or []:
            name = offer.get("platform_zh") or offer.get("platform")
            if name:
                platform_counts[name] = platform_counts.get(name, 0) + 1
    platforms = [{"name": name, "count": count, "note_zh": "快照内报价渠道"}
                 for name, count in sorted(platform_counts.items(), key=lambda kv: -kv[1])]
    platforms.append({
        "id": "amap_tongcheng", "label": "高德 / 同程票价", "rating": False, "price": False,
        "mode": "partnership only",
        "note": "Amap's open POI API exposes rating and average spend only; no ticket or room rate. "
                "Client data may not be scraped; authorised access needs a Tongcheng API agreement.",
        "note_zh": "高德客户端里的同程门票/房价来自商业合作；开放平台 POI 接口只有评分与人均消费，"
                   "没有票价/房价字段，协议禁止抓取客户端数据。合规路径是向同程联盟/分销平台申请授权。",
    })

    coverage = {
        "tracked": {"attractions": len(attractions), "hotels": len(hotels)},
        "places_discovered": len(cities), "places_scanned": len(cities),
        "sweeps": 0, "last_scan_at": "", "discovery_rounds": 0,
        "city_level": len(cities), "county_level": 0,
    }
    sources_payload = {
        "builtin": {"name": "offline_snapshot", "label": "离线快照（参赛演示）",
                    "kind": "attraction+hotel+metro", "needs_key": False,
                    "status": "ok", "note": "数据来自一次真实抓取的快照，内嵌在页面里，不发起任何网络请求",
                    "cache": {"snapshots": len(cities), "by_kind": {"attraction": len(attractions),
                                                                    "hotel": len(hotels),
                                                                    "metro": len(metro_raw)}},
                    "coverage": coverage},
        "warmup": {"running": False, "total": 0, "index": 0, "added": 0, "round": 0},
        "platforms": platforms,
        "transport": {"fuel": {"name": "icauto.com.cn", "status": "snapshot"},
                      "rail": {"name": "12306", "status": "timetable"}},
        "storage": {"type": "embedded-json", "database": False, "path": "inline"},
    }
    fuel_payload = {"province": fuel_info["province"], "prices": prices,
                    "source": "snapshot", "fetched_at": fuel_info["at"]}
    params = {
        "road_factor": transport.ROAD_FACTOR, "rail_factor": transport.RAIL_FACTOR,
        "fuel_per_100km": transport.FUEL_PER_100KM, "toll_per_km": transport.TOLL_PER_KM,
        "rail_rate": transport.RAIL_RATE, "rail_speed_kmh": transport.RAIL_SPEED_KMH,
        "rail_stop_min": transport.RAIL_STOP_MIN,
        "flight_base": transport.FLIGHT_BASE, "flight_per_km": transport.FLIGHT_PER_KM,
        "flight_speed_kmh": transport.FLIGHT_SPEED_KMH, "flight_overhead_min": transport.FLIGHT_OVERHEAD_MIN,
        "drive_speed_kmh": transport.DRIVE_SPEED_KMH,
    }
    sources_list = [
        {"key": "snapshot", "name": "TravelOne snapshot", "status": "embedded",
         "detail": "%d cities" % len(cities)},
        {"key": "rail", "name": "12306", "status": "timetable", "detail": "公开时刻表车次"},
        {"key": "fuel", "name": "icauto.com.cn", "status": "snapshot", "detail": "92# %.2f 元/L" % fuel_info["p92"]},
    ]
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "counts": {"attractions": len(attractions), "hotels": len(hotels), "metro": len(metro_raw)},
        "cities": cities, "attractions": attractions, "hotels": hotels, "images": images,
        "meta": meta, "coverage": coverage, "sourcesPayload": sources_payload,
        "platforms": platforms, "fuel": fuel_info, "fuelPayload": fuel_payload,
        "params": params, "sources": sources_list,
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    if not APP_HTML.exists():
        raise SystemExit("缺少 static/app.html，请先运行 tools/build_single_page.py")

    print("读取快照并打包数据…")
    data = build_payload()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    packed = base64.b64encode(gzip.compress(payload, compresslevel=9)).decode("ascii")
    html = APP_HTML.read_text(encoding="utf-8")

    if "window.__OFFLINE_DATA__" in html or "window.__OFFLINE_B64__" in html:
        raise SystemExit("app.html 已包含离线数据，请先重建项目页面")

    inject = ('<head>\n<meta name="travelone-mode" content="offline-snapshot">\n'
              '<style>' + OFFLINE_CSS + '</style>\n'
              '<script>window.__OFFLINE_B64__="' + packed + '";</script>\n'
              '<script>' + SHIM + '</script>\n'
              '<script>' + BOOT + '</script>')
    html = html.replace("<head>", inject, 1)
    html = html.replace("<body>", '<body><div id="offlineBanner"><b>本页面仅做展示</b><span>Demo only · 不提供预订与购买</span></div>', 1)
    # file:// 下不要拦截：数据已内嵌，直接进入应用
    html = html.replace("isFileMode: () => location.protocol === 'file:',", "isFileMode: () => false,")
    size = len(html.encode("utf-8"))
    if size > 20 * 1024 * 1024:
        raise SystemExit("页面 %.2f MB 超出 20MB 发布限制，请减少图片或数据" % (size / 1048576))
    out.write_text(html, encoding="utf-8")
    print("已生成 %s（%.1f MB，城市 %d，景点 %d，酒店 %d）" % (
        out, len(html.encode("utf-8")) / 1048576, len(data["cities"]),
        data["counts"]["attractions"], data["counts"]["hotels"]))


if __name__ == "__main__":
    main()