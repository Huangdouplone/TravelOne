# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""国际版数据源之二：Wikidata（经 QLever 公共 SPARQL，CC0）。

OSM 的 Overpass/Nominatim 在本机网络经常不可达（502 与连接超时），
这里用 Wikidata 作为可用的国际源：按城市的 QID 取景点、酒店与地铁站，
带中英文标签与坐标。字段与百度链路对齐，价格/评分留空由前端标注“暂无”。
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional

import requests

ENDPOINT = "https://qlever.cs.uni-freiburg.de/api/wikidata"
UA = {"Accept": "application/json", "User-Agent": "TravelOne/1.0 (research)"}
_SESSION = requests.Session()
_SESSION.headers.update(UA)
TTL = 7 * 24 * 3600

CITIES: List[Dict[str, str]] = [
    {"city": "巴黎", "en": "Paris", "qid": "Q90", "country": "法国"},
    {"city": "伦敦", "en": "London", "qid": "Q84", "country": "英国"},
    {"city": "东京", "en": "Tokyo", "qid": "Q1490", "country": "日本"},
    {"city": "新加坡", "en": "Singapore", "qid": "Q334", "country": "新加坡"},
    {"city": "纽约", "en": "New York", "qid": "Q60", "country": "美国"},
    {"city": "洛杉矶", "en": "Los Angeles", "qid": "Q65", "country": "美国"},
    {"city": "旧金山", "en": "San Francisco", "qid": "Q62", "country": "美国"},
    {"city": "芝加哥", "en": "Chicago", "qid": "Q1297", "country": "美国"},
    {"city": "多伦多", "en": "Toronto", "qid": "Q172", "country": "加拿大"},
    {"city": "温哥华", "en": "Vancouver", "qid": "Q24639", "country": "加拿大"},
    {"city": "墨西哥城", "en": "Mexico City", "qid": "Q1489", "country": "墨西哥"},
    {"city": "里约热内卢", "en": "Rio de Janeiro", "qid": "Q8678", "country": "巴西"},
    {"city": "圣保罗", "en": "São Paulo", "qid": "Q174", "country": "巴西"},
    {"city": "布宜诺斯艾利斯", "en": "Buenos Aires", "qid": "Q1486", "country": "阿根廷"},
    {"city": "巴塞罗那", "en": "Barcelona", "qid": "Q1492", "country": "西班牙"},
    {"city": "马德里", "en": "Madrid", "qid": "Q2807", "country": "西班牙"},
    {"city": "罗马", "en": "Rome", "qid": "Q220", "country": "意大利"},
    {"city": "米兰", "en": "Milan", "qid": "Q490", "country": "意大利"},
    {"city": "柏林", "en": "Berlin", "qid": "Q64", "country": "德国"},
    {"city": "慕尼黑", "en": "Munich", "qid": "Q1726", "country": "德国"},
    {"city": "阿姆斯特丹", "en": "Amsterdam", "qid": "Q727", "country": "荷兰"},
    {"city": "布鲁塞尔", "en": "Brussels", "qid": "Q239", "country": "比利时"},
    {"city": "维也纳", "en": "Vienna", "qid": "Q1741", "country": "奥地利"},
    {"city": "苏黎世", "en": "Zurich", "qid": "Q72", "country": "瑞士"},
    {"city": "布拉格", "en": "Prague", "qid": "Q1085", "country": "捷克"},
    {"city": "布达佩斯", "en": "Budapest", "qid": "Q1781", "country": "匈牙利"},
    {"city": "雅典", "en": "Athens", "qid": "Q1524", "country": "希腊"},
    {"city": "伊斯坦布尔", "en": "Istanbul", "qid": "Q406", "country": "土耳其"},
    {"city": "迪拜", "en": "Dubai", "qid": "Q612", "country": "阿联酋"},
    {"city": "曼谷", "en": "Bangkok", "qid": "Q186", "country": "泰国"},
    {"city": "首尔", "en": "Seoul", "qid": "Q8684", "country": "韩国"},
    {"city": "悉尼", "en": "Sydney", "qid": "Q3130", "country": "澳大利亚"},
    {"city": "墨尔本", "en": "Melbourne", "qid": "Q3141", "country": "澳大利亚"},
    {"city": "奥克兰", "en": "Auckland", "qid": "Q37100", "country": "新西兰"},
    {"city": "开罗", "en": "Cairo", "qid": "Q85", "country": "埃及"},
    {"city": "开普敦", "en": "Cape Town", "qid": "Q5465", "country": "南非"},
    {"city": "莫斯科", "en": "Moscow", "qid": "Q649", "country": "俄罗斯"},
    {"city": "华沙", "en": "Warsaw", "qid": "Q270", "country": "波兰"},
    {"city": "哥本哈根", "en": "Copenhagen", "qid": "Q1748", "country": "丹麦"},
    {"city": "斯德哥尔摩", "en": "Stockholm", "qid": "Q1754", "country": "瑞典"},
    {"city": "奥斯陆", "en": "Oslo", "qid": "Q585", "country": "挪威"},
    {"city": "赫尔辛基", "en": "Helsinki", "qid": "Q1757", "country": "芬兰"},
    {"city": "里斯本", "en": "Lisbon", "qid": "Q597", "country": "葡萄牙"},
    {"city": "都柏林", "en": "Dublin", "qid": "Q1761", "country": "爱尔兰"},
    {"city": "吉隆坡", "en": "Kuala Lumpur", "qid": "Q1865", "country": "马来西亚"},
    {"city": "雅加达", "en": "Jakarta", "qid": "Q3630", "country": "印度尼西亚"},
    {"city": "马尼拉", "en": "Manila", "qid": "Q1461", "country": "菲律宾"},
    {"city": "河内", "en": "Hanoi", "qid": "Q1858", "country": "越南"},
    {"city": "孟买", "en": "Mumbai", "qid": "Q1156", "country": "印度"},
{"city": "新德里", "en": "New Delhi", "qid": "Q987", "country": "印度"},
]

# 城市中心坐标：城际交通与地图取景先用这份常量，避免为了算距离再去抓一遍景点。
# 精度到小数点后 4 位（约 10 m 量级），对城际距离估算足够。
POINTS: Dict[str, tuple] = {
    "Paris": (48.8566, 2.3522), "London": (51.5074, -0.1278),
    "Tokyo": (35.6762, 139.6503), "Singapore": (1.3521, 103.8198),
    "New York": (40.7128, -74.0060), "Los Angeles": (34.0522, -118.2437),
    "San Francisco": (37.7749, -122.4194), "Chicago": (41.8781, -87.6298),
    "Toronto": (43.6532, -79.3832), "Vancouver": (49.2827, -123.1207),
    "Mexico City": (19.4326, -99.1332), "Rio de Janeiro": (-22.9068, -43.1729),
    "São Paulo": (-23.5505, -46.6333), "Buenos Aires": (-34.6037, -58.3816),
    "Barcelona": (41.3874, 2.1686), "Madrid": (40.4168, -3.7038),
    "Rome": (41.9028, 12.4964), "Milan": (45.4642, 9.1900),
    "Berlin": (52.5200, 13.4050), "Munich": (48.1351, 11.5820),
    "Amsterdam": (52.3676, 4.9041), "Brussels": (50.8503, 4.3517),
    "Vienna": (48.2082, 16.3738), "Zurich": (47.3769, 8.5417),
    "Prague": (50.0755, 14.4378), "Budapest": (47.4979, 19.0402),
    "Athens": (37.9838, 23.7275), "Istanbul": (41.0082, 28.9784),
    "Dubai": (25.2048, 55.2708), "Bangkok": (13.7563, 100.5018),
    "Seoul": (37.5665, 126.9780), "Sydney": (-33.8688, 151.2093),
    "Melbourne": (-37.8136, 144.9631), "Auckland": (-36.8485, 174.7633),
    "Cairo": (30.0444, 31.2357), "Cape Town": (-33.9249, 18.4241),
    "Moscow": (55.7558, 37.6173), "Warsaw": (52.2297, 21.0122),
    "Copenhagen": (55.6761, 12.5683), "Stockholm": (59.3293, 18.0686),
    "Oslo": (59.9139, 10.7522), "Helsinki": (60.1699, 24.9384),
    "Lisbon": (38.7223, -9.1393), "Dublin": (53.3498, -6.2603),
    "Kuala Lumpur": (3.1390, 101.6869), "Jakarta": (-6.2088, 106.8456),
    "Manila": (14.5995, 120.9842), "Hanoi": (21.0278, 105.8342),
    "Mumbai": (19.0760, 72.8777), "New Delhi": (28.6139, 77.2090),
}

CLASSES = {
    "attraction": ("wd:Q570116 wd:Q33506 wd:Q1030034 wd:Q839954 wd:Q22698 "
                   "wd:Q174782 wd:Q16970 wd:Q12518 wd:Q23413 wd:Q2319498 "
                   "wd:Q1440300 wd:Q1440476 wd:Q4989906 wd:Q2977 wd:Q44613 "
                   "wd:Q43501 wd:Q483110 wd:Q12280 wd:Q167385"),
    "landmark": ("wd:Q2319498 wd:Q1440300 wd:Q12518 wd:Q570116 wd:Q4989906"),
    "hotel": "wd:Q27686 wd:Q1030044 wd:Q781905",
    "metro": "wd:Q928830",
}
LIMITS = {"attraction": 600, "hotel": 400, "metro": 300}

_PREFIX = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""
_COORD = re.compile(r"POINT\(\s*([-0-9.]+)\s+([-0-9.]+)\s*\)")
_lock = threading.Lock()
_cache: Dict[str, Any] = {}


def pointed(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """给城市记录补上中心坐标；没有常量坐标时原样返回。"""
    if not row:
        return row
    out = dict(row)
    if out.get("lat") is None:
        lat, lng = POINTS.get(out.get("en") or "", (None, None))
        if lat is not None:
            out["lat"], out["lng"] = lat, lng
    return out


def city_by_name(name: str) -> Optional[Dict[str, Any]]:
    key = str(name or "").strip().lower()
    for row in CITIES:
        if key in (row["city"].lower(), row["en"].lower(), row["qid"].lower()):
            return pointed(row)
    return None


_QUERY_LOCK = threading.Lock()
_LAST_QUERY = 0.0
QUERY_GAP_SECONDS = 1.0      # 公共端点限流：两次查询之间至少间隔 1 秒


def _sparql(query: str, timeout: int = 30) -> Optional[List[Dict[str, Any]]]:
    global _LAST_QUERY
    resp = None
    for attempt in (1, 2):
        with _QUERY_LOCK:
            wait = QUERY_GAP_SECONDS - (time.time() - _LAST_QUERY)
            if wait > 0:
                time.sleep(wait)
            try:
                resp = _SESSION.get(ENDPOINT, params={"query": query}, timeout=timeout)
            except Exception:
                resp = None
            _LAST_QUERY = time.time()
        if resp is not None and resp.status_code == 429 and attempt < 2:
            time.sleep(2 * attempt)
            continue
        break
    if resp is None or resp.status_code >= 400:
        return None
    try:
        resp.encoding = "utf-8"     # QLever 返回 UTF-8，缺 charset 时避免被按 latin-1 解码
        payload = resp.json()
    except Exception:
        return None
    rows = (payload.get("results") or {}).get("bindings")
    return rows if isinstance(rows, list) else None


def _value(row: Dict[str, Any], key: str) -> str:
    cell = row.get(key) or {}
    return str(cell.get("value") or "").strip()


def _rows_by_qid(kind: str, qid: str, limit: int) -> List[Dict[str, Any]]:
    classes = CLASSES.get(kind)
    if not classes:
        return []
    query = _PREFIX + """
SELECT ?item ?labelZh ?labelEn ?coord WHERE {
  VALUES ?cls { %s }
  { ?item wdt:P131+ wd:%s . } UNION { ?item wdt:P276 wd:%s . }
  ?item wdt:P31/wdt:P279* ?cls .
  ?item wdt:P625 ?coord .
  OPTIONAL { ?item rdfs:label ?labelZh FILTER(lang(?labelZh) = "zh") }
  OPTIONAL { ?item rdfs:label ?labelEn FILTER(lang(?labelEn) = "en") }
} LIMIT %d""" % (classes, qid, qid, limit)
    rows = _sparql(query)
    if rows is None:
        return []
    out, seen = [], set()
    for row in rows:
        match = _COORD.search(_value(row, "coord"))
        name_en = _value(row, "labelEn")
        name_zh = _value(row, "labelZh")
        name = name_zh or name_en
        if not match or not name or name in seen:
            continue
        seen.add(name)
        out.append({
            "name": name, "name_en": name_en or name, "lat": float(match.group(2)),
            "lng": float(match.group(1)), "qid": _value(row, "item").rsplit("/", 1)[-1],
            "address": "", "tags": [], "source": "Wikidata",
        })
    return out


# 标志性景点白名单：按 QID 直取，绕开“按行政区检索 + LIMIT”导致的漏项。
# 名称与别名同时给中文常用名和英文名，供搜索做译名适配。
LANDMARK_INFO: Dict[str, Dict[str, Any]] = {
    "Q243": {"city": "巴黎", "country": "法国", "zh": "埃菲尔铁塔", "en": "Eiffel Tower",
             "aliases": ["铁塔", "巴黎铁塔", "tour eiffel", "eiffel"]},
    "Q19675": {"city": "巴黎", "country": "法国", "zh": "卢浮宫博物馆", "en": "Louvre Museum",
               "aliases": ["卢浮宫", "louvre"]},
    "Q2981": {"city": "巴黎", "country": "法国", "zh": "巴黎圣母院", "en": "Notre-Dame de Paris",
              "aliases": ["圣母院", "notre dame"]},
    "Q64436": {"city": "巴黎", "country": "法国", "zh": "巴黎凯旋门", "en": "Arc de Triomphe",
               "aliases": ["凯旋门", "arc de triomphe"]},
    "Q9202": {"city": "纽约", "country": "美国", "zh": "自由女神像", "en": "Statue of Liberty",
              "aliases": ["自由女神", "liberty"]},
    "Q160409": {"city": "纽约", "country": "美国", "zh": "中央公园", "en": "Central Park",
                "aliases": ["central park"]},
    "Q9188": {"city": "纽约", "country": "美国", "zh": "帝国大厦", "en": "Empire State Building",
              "aliases": ["empire state"]},
    "Q6373": {"city": "伦敦", "country": "英国", "zh": "大英博物馆", "en": "British Museum",
              "aliases": ["british museum"]},
    "Q62408": {"city": "伦敦", "country": "英国", "zh": "威斯敏斯特宫", "en": "Palace of Westminster",
               "aliases": ["大本钟", "big ben", "国会大厦"]},
    "Q83125": {"city": "伦敦", "country": "英国", "zh": "伦敦塔桥", "en": "Tower Bridge",
               "aliases": ["塔桥", "tower bridge"]},
    "Q185382": {"city": "罗马", "country": "意大利", "zh": "特雷维喷泉", "en": "Trevi Fountain",
                "aliases": ["许愿池", "trevi"]},
    "Q48435": {"city": "巴塞罗那", "country": "西班牙", "zh": "圣家堂", "en": "Sagrada Família",
               "aliases": ["圣家族大教堂", "sagrada familia"]},
    "Q183536": {"city": "东京", "country": "日本", "zh": "东京塔", "en": "Tokyo Tower",
                "aliases": ["东京铁塔", "tokyo tower"]},
    "Q57965": {"city": "东京", "country": "日本", "zh": "东京晴空塔", "en": "Tokyo Skytree",
               "aliases": ["晴空塔", "skytree"]},
    "Q39231": {"city": "东京", "country": "日本", "zh": "富士山", "en": "Mount Fuji",
               "aliases": ["fuji"]},
    "Q548679": {"city": "新加坡", "country": "新加坡", "zh": "滨海湾金沙酒店", "en": "Marina Bay Sands",
                "aliases": ["金沙酒店", "marina bay sands"]},
    "Q630135": {"city": "新加坡", "country": "新加坡", "zh": "滨海湾花园", "en": "Gardens by the Bay",
                "aliases": ["gardens by the bay"]},
    "Q12495": {"city": "迪拜", "country": "阿联酋", "zh": "哈利法塔", "en": "Burj Khalifa",
               "aliases": ["迪拜塔", "burj khalifa"]},
    "Q45178": {"city": "悉尼", "country": "澳大利亚", "zh": "悉尼歌剧院", "en": "Sydney Opera House",
               "aliases": ["歌剧院", "opera house"]},
    "Q54495": {"city": "悉尼", "country": "澳大利亚", "zh": "悉尼海港大桥", "en": "Sydney Harbour Bridge",
               "aliases": ["海港大桥", "harbour bridge"]},
    "Q82425": {"city": "柏林", "country": "德国", "zh": "勃兰登堡门", "en": "Brandenburg Gate",
               "aliases": ["brandenburg gate"]},
    "Q190804": {"city": "阿姆斯特丹", "country": "荷兰", "zh": "阿姆斯特丹国家博物馆", "en": "Rijksmuseum",
                "aliases": ["荷兰国立博物馆", "rijksmuseum"]},
    "Q224124": {"city": "阿姆斯特丹", "country": "荷兰", "zh": "梵高博物馆", "en": "Van Gogh Museum",
                "aliases": ["凡高博物馆", "van gogh"]},
    "Q873769": {"city": "曼谷", "country": "泰国", "zh": "曼谷大皇宫", "en": "Grand Palace",
                "aliases": ["大皇宫", "grand palace"]},
    "Q724970": {"city": "曼谷", "country": "泰国", "zh": "黎明寺", "en": "Wat Arun",
                "aliases": ["郑王庙", "wat arun"]},
    "Q482485": {"city": "首尔", "country": "韩国", "zh": "景福宫", "en": "Gyeongbokgung",
                "aliases": ["gyeongbokgung"]},
    "Q79961": {"city": "里约热内卢", "country": "巴西", "zh": "里约热内卢基督像", "en": "Christ the Redeemer",
               "aliases": ["基督像", "救世基督像", "christ the redeemer"]},
    "Q180376": {"city": "洛杉矶", "country": "美国", "zh": "好莱坞标志", "en": "Hollywood Sign",
                "aliases": ["hollywood sign"]},
    "Q134883": {"city": "多伦多", "country": "加拿大", "zh": "加拿大国家电视塔", "en": "CN Tower",
                "aliases": ["cn tower"]},
    "Q41116": {"city": "莫斯科", "country": "俄罗斯", "zh": "红场", "en": "Red Square",
               "aliases": ["red square"]},
    "Q18068": {"city": "米兰", "country": "意大利", "zh": "米兰主教座堂", "en": "Milan Cathedral",
               "aliases": ["米兰大教堂", "duomo"]},
    "Q204871": {"city": "布拉格", "country": "捷克", "zh": "查理大桥", "en": "Charles Bridge",
                "aliases": ["charles bridge"]},
    "Q131330": {"city": "维也纳", "country": "奥地利", "zh": "美泉宫", "en": "Schönbrunn Palace",
                "aliases": ["schonbrunn", "schönbrunn"]},
    "Q83063": {"city": "吉隆坡", "country": "马来西亚", "zh": "双峰塔", "en": "Petronas Towers",
               "aliases": ["双子塔", "petronas"]},
}

LANDMARKS: Dict[str, List[str]] = {}
for _qid, _info in LANDMARK_INFO.items():
    LANDMARKS.setdefault(_info["city"], []).append(_qid)

# 常见繁体字 → 简体字，用于中文标签与用户输入的归一化匹配
_T2S = str.maketrans(
    "爾鐵羅馬宮廣場聖紐約倫敦博物館美術館國家東亞洲區縣鎮灣港島嶼園車站機場酒店"
    "萬與為國學醫書畫藝術劇院樂園動物植物海濱湖邊橋樑門塔樓閣廟寺觀教堂宮殿城堡"
    "爾薩貝爾維也納捷克奧地利義大利西班牙葡萄牙荷蘭比利時瑞士瑞典挪威丹麥芬蘭"
    "俄羅斯烏克蘭埃及南非印度尼西亞菲律賓越南泰國馬來西亞新加坡澳大利亞紐西蘭",
    "尔铁罗马宫广场圣纽约伦敦博物馆美术馆国家东亚洲区县镇湾港岛屿园车站机场酒店"
    "万与为国学医书画艺术剧院乐园动物植物海滨湖边桥梁门塔楼阁庙寺观教堂宫殿城堡"
    "尔萨贝尔维也纳捷克奥地利意大利西班牙葡萄牙荷兰比利时瑞士瑞典挪威丹麦芬兰"
    "俄罗斯乌克兰埃及南非印度尼西亚菲律宾越南泰国马来西亚新加坡澳大利亚新西兰",
)

# 补充常见但上表未覆盖的繁体字
_T2S_EXTRA = str.maketrans(
    "鐘臺灘嶺陽陰濟華濱蘭園區車馬爾薩貝爾廣場宮聖紐約倫敦",
    "钟台滩岭阳阴济华滨兰园区车马尔萨贝尔广场宫圣纽约伦敦",
)
_T2S = str.maketrans(
    "".join(chr(a) for a in range(0x4e00)), "".join(chr(a) for a in range(0x4e00))
) if False else _T2S


def normalize_text(text: str) -> str:
    raw = str(text or "").strip().lower().translate(_T2S).translate(_T2S_EXTRA)
    return re.sub(r"[\s·•,，.。'\"“”‘’()（）\-_/]+", "", raw)


def _landmark_rows(qids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not qids:
        return {}
    query = _PREFIX + """
SELECT ?item ?zh ?zhHans ?en ?coord WHERE {
  VALUES ?item { %s }
  ?item wdt:P625 ?coord .
  OPTIONAL { ?item rdfs:label ?zh FILTER(lang(?zh) = "zh") }
  OPTIONAL { ?item rdfs:label ?zhHans FILTER(lang(?zhHans) = "zh-hans") }
  OPTIONAL { ?item rdfs:label ?en FILTER(lang(?en) = "en") }
}""" % " ".join("wd:" + q for q in qids)
    rows = _sparql(query)
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows or []:
        qid = _value(row, "item").rsplit("/", 1)[-1]
        match = _COORD.search(_value(row, "coord"))
        if not match or qid in out:
            continue
        info = LANDMARK_INFO.get(qid, {})
        zh = info.get("zh") or _value(row, "zhHans") or _value(row, "zh")
        en = info.get("en") or _value(row, "en") or zh
        city = city_by_name(info.get("city") or "")
        out[qid] = {
            "name": zh, "name_en": en,
            "lat": float(match.group(2)), "lng": float(match.group(1)),
            "address": "", "tags": ["landmark"], "source": "Wikidata",
            "city": info.get("city") or "", "city_en": (city or {}).get("en") or "Global",
            "country": info.get("country") or "",
        }
    return out


def fetch_landmarks(city_name: str) -> List[Dict[str, Any]]:
    """按白名单 QID 取某座城市的标志性景点；没有白名单的城市返回空列表。"""
    city = city_by_name(city_name) or resolve_city(city_name)
    if not city:
        return []
    qids = LANDMARKS.get(city["city"])
    if not qids:
        return []
    cache_key = "landmarks|%s" % city["city"]
    with _lock:
        hit = _cache.get(cache_key)
        if hit and time.time() - hit[0] < TTL:
            return list(hit[1])
    rows = list(_landmark_rows(qids).values())
    with _lock:
        _cache[cache_key] = (time.time(), rows)
    return list(rows)


def search_landmarks(term: str, limit: int = 8, known: Optional[set] = None) -> List[Dict[str, Any]]:
    """按中文常用名 / 英文名 / 别名匹配白名单地标，返回可直接入库的条目。"""
    needle = normalize_text(term)
    if len(needle) < 2:
        return []
    cache_key = "search|%s" % needle
    with _lock:
        hit = _cache.get(cache_key)
        if hit and time.time() - hit[0] < TTL:
            return list(hit[1])
    scored = []
    for qid, info in LANDMARK_INFO.items():
        pool = [info.get("zh"), info.get("en")] + list(info.get("aliases") or [])
        best = 0
        for candidate in pool:
            text = normalize_text(candidate)
            if not text:
                continue
            if text == needle:
                best = max(best, 4)
            elif text.startswith(needle):
                best = max(best, 3)
            elif needle in text:
                best = max(best, 2)
            elif len(text) >= 3 and text in needle:
                best = max(best, 1)
        if best:
            scored.append((best, qid))
    scored.sort(reverse=True)
    known_names = {str(n) for n in (known or set())}
    qids = [qid for _, qid in scored[:limit]
            if LANDMARK_INFO[qid]["zh"] not in known_names]
    if not qids:
        return []
    rows = _landmark_rows(qids)
    out = [rows[qid] for qid in qids if qid in rows]
    with _lock:
        _cache[cache_key] = (time.time(), out)
    return list(out)

def fetch(kind: str, city_name: str, limit: int = 0) -> List[Dict[str, Any]]:
    """按城市取一类地点；网络失败返回空列表。"""
    city = city_by_name(city_name)
    if city is None:
        city = resolve_city(city_name)
    if not city or kind not in CLASSES:
        return []
    cache_key = "%s|%s" % (kind, city["qid"])
    with _lock:
        hit = _cache.get(cache_key)
        if hit and time.time() - hit[0] < TTL:
            return list(hit[1])
    rows = _rows_by_qid(kind, city["qid"], limit or LIMITS.get(kind, 200))
    with _lock:
        _cache[cache_key] = (time.time(), rows)
    return list(rows)



CITY_CACHE_FILE = None
_CITY_QUERY = _PREFIX + """
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?c ?zh ?en ?coord ?pop ?countryZh ?countryEn WHERE {
  VALUES ?cls { wd:Q515 wd:Q1549591 wd:Q3957 }
  ?c wdt:P31/wdt:P279* ?cls .
  ?c rdfs:label "%s"@%s .
  ?c wdt:P625 ?coord .
  OPTIONAL { ?c wdt:P1082 ?pop }
  OPTIONAL { ?c rdfs:label ?zh FILTER(lang(?zh) = "zh") }
  OPTIONAL { ?c rdfs:label ?en FILTER(lang(?en) = "en") }
  OPTIONAL { ?c wdt:P17 ?country . ?country rdfs:label ?countryZh FILTER(lang(?countryZh) = "zh") }
  OPTIONAL { ?c wdt:P17 ?country . ?country rdfs:label ?countryEn FILTER(lang(?countryEn) = "en") }
} ORDER BY DESC(xsd:integer(?pop)) LIMIT 5
"""


def _city_cache_path():
    global CITY_CACHE_FILE
    if CITY_CACHE_FILE is None:
        from core import cache_store
        CITY_CACHE_FILE = cache_store.CACHE_DIR / "intl_cities.json"
    return CITY_CACHE_FILE


def _load_custom() -> Dict[str, Any]:
    try:
        import json as _json
        return _json.loads(_city_cache_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_custom(data: Dict[str, Any]) -> None:
    try:
        import json as _json
        path = _city_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def resolve_city(name: str) -> Optional[Dict[str, Any]]:
    """按城市名反查 QID 与坐标：先查已收录清单与本地缓存，再用 SPARQL 名称检索。"""
    key = str(name or "").strip()
    if not key:
        return None
    hit = city_by_name(key)
    if hit:
        return dict(hit)
    custom = _load_custom()
    if key in custom and custom[key].get("country"):
        return custom[key]
    candidates = [(key, "zh"), (key + "市", "zh"), (key, "en")]
    for label, lang in candidates:
        rows = _sparql(_CITY_QUERY % (label.replace('"', ""), lang))
        if not rows:
            continue
        row = rows[0]
        match = _COORD.search(_value(row, "coord"))
        if not match:
            continue
        record = {
            "city": _value(row, "zh") or key,
            "en": _value(row, "en") or key,
            "qid": _value(row, "c").rsplit("/", 1)[-1],
            "country": _value(row, "countryZh") or _value(row, "countryEn") or "",
            "lat": float(match.group(2)),
            "lng": float(match.group(1)),
        }
        if len(_rows_by_qid("attraction", record["qid"], 5)) < 3:
            continue
        custom[key] = record
        custom.setdefault(record["city"], record)
        _save_custom(custom)
        return record
    return None

def city_center(city_name: str) -> Optional[Dict[str, float]]:
    """城市中心：取该城景点坐标均值，查不到则返回 None。"""
    rows = fetch("attraction", city_name)
    if not rows:
        return None
    lat = sum(r["lat"] for r in rows) / len(rows)
    lng = sum(r["lng"] for r in rows) / len(rows)
    return {"lat": round(lat, 4), "lng": round(lng, 4)}