# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""内置实时采集源：百度地图网页检索（无需密钥、全国覆盖）。

只做「抓取 + 字段归一」，不保存任何数据；结果由 services.live 归档为 JSON 快照。

2026-11 实测可获得的真实字段：
- 名称、地址、城市、电话、营业时间、标签、A 级景区等级；
- 评分 overall_rating、点评数 comment_num、实景图 CDN 地址；
- 坐标 geo（BD09MC），经 MC→BD09LL→GCJ02 转换后与地图/路线一致；
- 景点票价：entrance_price（在线参考价）、ticket_info（门市原价说明）、refer_price；
- 酒店房价：pc_realtime_price（实时价）、pc_price_src（报价来源，如 qunar）、
  origin_price（门市价）、hotelprice.pc_price{日期: 价格}、hotel_ext.singleroom（房型明细）。
"""
from __future__ import annotations

import concurrent.futures
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from core import httpclient
from core.config import settings
from core import i18n
from core.geo import bd09_to_gcj02

API = "https://map.baidu.com/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# 百度墨卡托 → 经纬度（BD09LL）分段参数
MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]
MC2LL = [
    [1.410526172116255e-8, 8.98305509648872e-6, -1.9939833816331, 200.98243831099356,
     -187.2403703815547, 91.6087516669843, -23.38765649603339, 2.57121317296198,
     -0.03801003308653, 17337981.2],
    [-7.435856389565537e-9, 8.983055097726239e-6, -0.78625201886289, 96.32687599759846,
     -1.85204757529826, -59.36935905485877, 47.40033549296737, -16.50741931063887,
     2.28786674699375, 10260144.86],
    [-3.030883460898826e-8, 8.98305509983578e-6, 0.30071316287616, 59.74293618442277,
     7.357984074871, -25.38371002664745, 13.45380521110908, -3.29883767235584,
     0.32710905363475, 6856817.37],
    [-1.981981304930552e-8, 8.983055099779535e-6, 0.03278182852591, 40.31678527705744,
     0.65659298677277, -4.44255534477492, 0.85341911805263, 0.12923347998204,
     -0.04625736007561, 4482777.06],
    [3.09191371068437e-9, 8.983055096812155e-6, 0.00006995724062, 23.10934304144901,
     -0.00023663490511, -0.6321817810242, -0.00663494467273, 0.03430082397953,
     -0.00466043876332, 2555164.4],
    [2.890871144776878e-9, 8.983055095805407e-6, -3.068298e-8, 7.47137025468032,
     -0.00000353937994, -0.02145144861037, -0.00001234426596, 0.00010322952773,
     -0.00000323890364, 826088.5],
]


def mc_to_ll(x: float, y: float) -> Tuple[float, float]:
    """BD09MC（百度墨卡托米）→ BD09LL（百度经纬度）。"""
    coef = MC2LL[-1]
    for idx, band in enumerate(MCBAND):
        if abs(y) >= band:
            coef = MC2LL[idx]
            break
    t = abs(y) / coef[9]
    lng = coef[0] + coef[1] * abs(x)
    lat = (coef[2] + coef[3] * t + coef[4] * t ** 2 + coef[5] * t ** 3
           + coef[6] * t ** 4 + coef[7] * t ** 5 + coef[8] * t ** 6)
    if x < 0:
        lng = -lng
    if y < 0:
        lat = -lat
    return lng, lat


def parse_geo(value: str) -> Optional[Tuple[float, float]]:
    """解析 geo 字符串，返回 GCJ02 坐标。"""
    if not value or "|" not in value:
        return None
    try:
        body = value.split("|")[1]
        pair = body.split(";")[0]
        x_str, y_str = pair.split(",")[:2]
        x, y = float(x_str), float(y_str)
    except (ValueError, IndexError):
        return None
    lng, lat = mc_to_ll(x, y)
    lat_g, lng_g = bd09_to_gcj02(lat, lng)
    if not (18 <= lat_g <= 54 and 73 <= lng_g <= 135):
        return None
    return lat_g, lng_g


def parse_price(value: Any) -> Optional[float]:
    """把上游价格字段（数字 / "￥45元" / "¥免费" / "淡季10元"）归一为数值。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2) if float(value) >= 0 else None
    text = str(value)
    if "免费" in text:
        return 0.0
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    if not match:
        return None
    try:
        return round(float(match.group(1)), 2)
    except ValueError:
        return None


def _as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _level(tag: str) -> str:
    for token, label in (("AAAAA", "5A"), ("AAAA", "4A"), ("AAA", "3A"),
                         ("AA", "2A")):
        if token in tag:
            return label
    return ""


def _tags(tag: str) -> List[str]:
    parts = re.split(r"[,;，；、|/\s]+", tag or "")
    out: List[str] = []
    for part in parts:
        text = part.strip()
        if not text or set(text) <= {"A"}:
            continue
        if re.fullmatch(r"[A]+级?景区?", text):
            continue
        if text in ("景区", "景点", "旅游景点") and out:
            continue
        if text not in out:
            out.append(text)
    return out[:6]


_STAR_MAP = (
    ("豪华", 5), ("五星", 5), ("五钻", 5),
    ("高档", 4), ("四星", 4), ("四钻", 4),
    ("舒适", 3), ("三星", 3), ("三钻", 3), ("连锁", 3),
    ("经济", 2), ("二星", 2), ("客栈", 2), ("青旅", 1), ("青年旅舍", 1),
)


def _star(level: str, name: str) -> int:
    text = (level or "") + (name or "")
    for token, star in _STAR_MAP:
        if token in text:
            return star
    return 3


_SKIP_ATTR = ("停车场", "停车库", "入口", "出口", "售票处", "售票厅", "游客中心", "服务中心",
              "派出所", "公厕", "卫生间", "公交站", "地铁站", "充电站", "检票口", "取票")
_SKIP_HOTEL = ("停车场", "入口", "出口", "写字楼", "产业园", "小区", "公寓楼", "宿舍",
               "中介", "售楼", "便利店")


def _clean_image(url: Any) -> str:
    text = str(url or "")
    if not text.startswith("http"):
        return ""
    if "map.baidu.com" in text or "/icon/" in text or "default" in text or text.endswith(".gif"):
        return ""
    return text


def _city_of(row: Dict[str, Any], city: str) -> str:
    raw = str(row.get("city_name") or "").strip()
    if not raw:
        return city
    for suffix in ("市", "地区", "自治州", "盟"):
        if raw.endswith(suffix) and len(raw) > 2:
            raw = raw[: -len(suffix)]
    return raw


def _match_city(row_city: str, city: str) -> bool:
    if not city:
        return True
    if not row_city:
        return True
    a = row_city.replace("市", "").strip()
    b = city.replace("市", "").strip()
    return a.startswith(b) or b.startswith(a)


def _ticket_number(text: str) -> Optional[float]:
    """从「旺季（4月~10月）：门票10.00元…」这类长文本里取门票价。"""
    if not text:
        return None
    if "免费" in text:
        return 0.0
    match = re.search(r"门票[^0-9]{0,6}(\d+(?:\.\d+)?)", text)
    if match:
        return round(float(match.group(1)), 2)
    match = re.search(r"(\d+(?:\.\d+)?)\s*元", text)
    if match:
        return round(float(match.group(1)), 2)
    match = re.search(r"(?:成人|全价|普通票?)[^0-9]{0,4}(\d+(?:\.\d+)?)", text)
    if match:
        return round(float(match.group(1)), 2)
    return parse_price(text)


def _attraction_price(detail: Dict[str, Any]) -> Dict[str, Any]:
    """景点票价：在线参考价 + 门市原价说明 + 票种明细。"""
    ticket = detail.get("ticket_info") if isinstance(detail.get("ticket_info"), list) else []
    note = ""
    ticket_price = None
    specs: List[Dict[str, Any]] = []
    for row in ticket:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        note = content if not note else note + "；" + content
        value = _ticket_number(content)
        if ticket_price is None:
            ticket_price = value
        note_text = "Free" if "免费" in content else i18n.room_text(content)
        specs.append({"name": i18n.source(str(row.get("name") or "List price")),
                      "price": value if value is not None else ticket_price,
                      "note": note_text})
    online = _ticket_number(str(detail.get("entrance_price") or ""))
    if online is None:
        online = parse_price(detail.get("refer_price"))
    if online is None:
        online = ticket_price
    free_hint = str(detail.get("entrance_price") or "")
    return {
        "price": online,
        "original_price": (ticket_price if (ticket_price not in (None, online)
                                            and online is not None and ticket_price > online) else None),
        "price_note": "Free" if note.strip() == "免费" else note,
        "price_free_hint": free_hint if "免费" in free_hint else "",
        "specs": specs,
    }


def _hotel_price(detail: Dict[str, Any]) -> Dict[str, Any]:
    """酒店房价：实时价 + 报价来源 + 门市价 + 日期报价 + 房型明细。"""
    source_code = str(detail.get("pc_price_src") or detail.get("wise_price_src") or "")
    source_label = {"qunar": "Qunar", "ctrip": "Ctrip", "meituan": "Meituan",
                    "elong": "Elong", "tongcheng": "Tongcheng"}.get(source_code, "")
    price = _as_float(detail.get("pc_realtime_price"))
    if price in (None, 0):
        price = _as_float(detail.get("origin_price"))
    if price == 0:
        price = None
    nested = detail.get("hotelprice") if isinstance(detail.get("hotelprice"), dict) else {}
    date_rows: List[Dict[str, Any]] = []
    for block_name in ("pc_price", "wise_price"):
        block = nested.get(block_name) if isinstance(nested.get(block_name), dict) else {}
        for day, info in block.items():
            if not isinstance(info, dict):
                continue
            value = _as_float(info.get("price") or info.get("origin_price"))
            if value in (None, 0):
                continue
            label = str(day)
            if re.fullmatch(r"\d{8}", label):
                label = f"{label[4:6]}-{label[6:8]}"
            if not any(row["name"] == label for row in date_rows):
                date_rows.append({"name": label, "price": value,
                                  "note": "Bookable" if info.get("bookable") else "Sold out",
                                  "note_zh": "可预订" if info.get("bookable") else "已售完"})
    date_rows.sort(key=lambda row: row["name"])
    room: Dict[str, Any] = {}
    ext = detail.get("hotel_ext") if isinstance(detail.get("hotel_ext"), dict) else {}
    if isinstance(ext.get("singleroom"), dict):
        room = ext["singleroom"]
    specs: List[Dict[str, Any]] = []
    room_price = None
    if room:
        room_price = _as_float(room.get("realprice") or room.get("ota_price"))
    if price is None and room_price:
        price = room_price
        source_label = source_label or "Baidu Maps"
    if room:
        room_price = room_price or price
        pieces = [str(room.get("bed_type_name") or ""), str(room.get("area") or ""),
                  str(room.get("breakfast") or ""), str(room.get("cancel_policy") or "")]
        note_zh = " · ".join([p for p in pieces if p])
        specs.append({
            "name": str(room.get("new_ota_room_name") or room.get("ota_room_name") or "房型"),
            "price": room_price if room_price is not None else price,
            "note": i18n.room_text(note_zh),
            "note_zh": note_zh,
        })
    specs.extend(date_rows[:4])
    if not specs and price is not None:
        specs.append({"name": "Standard room", "name_zh": "标准房", "price": price,
                      "note": "Live from", "note_zh": "实时报价"})
    return {
        "price": price,
        "original_price": (_as_float(detail.get("origin_price")) or None),
        "price_source": (source_label + " (via Baidu Maps)") if source_label else "Baidu Maps",
        "price_from_room": bool(price and room_price == price),
        "price_note": i18n.room_text(str(room.get("cancel_policy") or "")),
        "specs": specs,
        "room_image": _clean_image(room.get("image")),
    }


def _offer(item: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    price = item.get("price")
    if price is None:
        return []
    stamp = item.get("price_updated_at") or time.strftime("%Y-%m-%d %H:%M:%S")
    note = "Live data" + (" · per night from" if kind == "hotel" else " · online reference")
    note_zh = "实时数据" + (" · 每晚起" if kind == "hotel" else " · 在线参考价")
    if item.get("price_note"):
        note += " · " + str(item["price_note"])
    offers = [{
        "platform": item.get("price_source") or "Baidu Maps",
        "platform_zh": i18n.source_zh(item.get("price_source") or "Baidu Maps"),
        "code": "live",
        "price": float(price),
        "original_price": item.get("original_price"),
        "note": note,
        "note_zh": note_zh,
        "is_reference": False,
        "live": True,
        "updated_at": stamp,
        "specs": item.get("specs") or [],
        "spec_label": "Room / date" if kind == "hotel" else "Ticket type",
        "spec_label_zh": "房型 / 日期" if kind == "hotel" else "票种",
    }]
    original = item.get("original_price")
    if original not in (None, 0, price) and float(original) > float(price):
        offers.append({
            "platform": "List price", "platform_zh": "门市原价",
            "code": "list", "price": float(original),
            "note": "Venue list price" if kind == "attraction" else "Hotel list price",
            "note_zh": "景区门市价" if kind == "attraction" else "酒店门市价",
            "is_reference": True, "live": False, "updated_at": stamp,
            "specs": [], "spec_label": "Ticket type" if kind == "attraction" else "Room type",
            "spec_label_zh": "票种" if kind == "attraction" else "房型",
        })
    return offers


SU_API = "https://map.baidu.com/su"
_CITY_SUFFIX = ("市", "盟", "地区", "自治州", "县", "区", "旗")


def suggest(term: str, limit: int = 10) -> List[Dict[str, Any]]:
    """联想检索：返回 {name, code, province, city, kind}。

    返回串格式形如：河北省$石家庄市$$石家庄市$150$河北省$石家庄市$
    其中第 4 段是行政区编码（如 150），可用来做「按编码限定范围」的 POI 检索。
    """
    url = (SU_API + "?wd=" + quote(term) +
           "&cid=1&type=0&newmap=1&ie=utf-8&oue=1&fromproduct=jsapi")
    try:
        resp = httpclient.get(url, headers={"User-Agent": UA, "Referer": "https://map.baidu.com/"},
                              timeout=max(5, settings.request_timeout))
        payload = resp.json()
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    seen = set()
    for raw in payload.get("s") or []:
        parts = str(raw).split("$")
        if len(parts) < 7:
            continue
        province, city, _, name, code = parts[0], parts[1], parts[2], parts[3], parts[4]
        if not name or not str(code).isdigit():
            continue
        if not name.endswith(_CITY_SUFFIX) or len(name) > 14:
            continue
        if any(word in name for word in ("景区", "公园", "学校", "大学", "公司", "医院",
                                         "车站", "机场", "酒店", "广场", "大厦", "小区",
                                         "市场", "基地", "厂", "站", "超市", "商城",
                                         "银行", "营业厅", "门店", "旅游区", "风景区",
                                         "名胜区", "开发区", "教会", "寺庙", "度假区")):
            continue
        key = (name, code)
        if key in seen:
            continue
        seen.add(key)
        level = "city" if name.endswith(("市", "盟", "地区", "自治州")) else "county"
        out.append({"name": name, "code": str(code), "province": province,
                    "city": city or name, "level": level})
        if len(out) >= limit:
            break
    return out


# 用于「发现全国点位」的拼音音节（配置：音节表，不是地点数据）
PINYIN_SYLLABLES = [
    "a", "ai", "an", "ang", "ao", "ba", "bai", "ban", "bang", "bao", "bei", "ben",
    "beng", "bi", "bian", "biao", "bie", "bin", "bing", "bo", "bu", "ca", "cai",
    "can", "cang", "cao", "ce", "ceng", "cha", "chai", "chan", "chang", "chao",
    "che", "chen", "cheng", "chi", "chong", "chou", "chu", "chuai", "chuan",
    "chuang", "chui", "chun", "chuo", "ci", "cong", "cou", "cu", "cuan", "cui",
    "cun", "cuo", "da", "dai", "dan", "dang", "dao", "de", "deng", "di", "dian",
    "diao", "die", "ding", "diu", "dong", "dou", "du", "duan", "dui", "dun", "duo",
    "e", "en", "er", "fa", "fan", "fang", "fei", "fen", "feng", "fo", "fou", "fu",
    "ga", "gai", "gan", "gang", "gao", "ge", "gei", "gen", "geng", "gong", "gou",
    "gu", "gua", "guai", "guan", "guang", "gui", "gun", "guo", "ha", "hai", "han",
    "hang", "hao", "he", "hei", "hen", "heng", "hong", "hou", "hu", "hua", "huai",
    "huan", "huang", "hui", "hun", "huo", "ji", "jia", "jian", "jiang", "jiao",
    "jie", "jin", "jing", "jiong", "jiu", "ju", "juan", "jue", "jun", "ka", "kai",
    "kan", "kang", "kao", "ke", "ken", "keng", "kong", "kou", "ku", "kua", "kuai",
    "kuan", "kuang", "kui", "kun", "kuo", "la", "lai", "lan", "lang", "lao", "le",
    "lei", "leng", "li", "lia", "lian", "liang", "liao", "lie", "lin", "ling",
    "liu", "long", "lou", "lu", "luan", "lue", "lun", "luo", "ma", "mai", "man",
    "mang", "mao", "me", "mei", "men", "meng", "mi", "mian", "miao", "mie", "min",
    "ming", "miu", "mo", "mou", "mu", "na", "nai", "nan", "nang", "nao", "ne", "nei",
    "nen", "neng", "ni", "nian", "niang", "niao", "nie", "nin", "ning", "niu",
    "nong", "nu", "nuan", "nuo", "ou", "pa", "pai", "pan", "pang", "pao", "pei",
    "pen", "peng", "pi", "pian", "piao", "pie", "pin", "ping", "po", "pu", "qi",
    "qia", "qian", "qiang", "qiao", "qie", "qin", "qing", "qiong", "qiu", "qu",
    "quan", "que", "qun", "ran", "rang", "rao", "re", "ren", "reng", "ri", "rong",
    "rou", "ru", "ruan", "rui", "run", "ruo", "sa", "sai", "san", "sang", "sao",
    "se", "sen", "seng", "sha", "shai", "shan", "shang", "shao", "she", "shen",
    "sheng", "shi", "shou", "shu", "shua", "shuai", "shuan", "shuang", "shui",
    "shun", "shuo", "si", "song", "sou", "su", "suan", "sui", "sun", "suo", "ta",
    "tai", "tan", "tang", "tao", "te", "teng", "ti", "tian", "tiao", "tie", "ting",
    "tong", "tou", "tu", "tuan", "tui", "tun", "tuo", "wa", "wai", "wan", "wang",
    "wei", "wen", "weng", "wo", "wu", "xi", "xia", "xian", "xiang", "xiao", "xie",
    "xin", "xing", "xiong", "xiu", "xu", "xuan", "xue", "xun", "ya", "yan", "yang",
    "yao", "ye", "yi", "yin", "ying", "yong", "you", "yu", "yuan", "yue", "yun",
    "za", "zai", "zan", "zang", "zao", "ze", "zei", "zen", "zeng", "zha", "zhai",
    "zhan", "zhang", "zhao", "zhe", "zhen", "zheng", "zhi", "zhong", "zhou", "zhu",
    "zhua", "zhuai", "zhuan", "zhuang", "zhui", "zhun", "zhuo", "zi", "zong", "zou",
    "zu", "zuan", "zui", "zun", "zuo",
]


def discover_places(terms: List[str], workers: int = 6) -> List[Dict[str, Any]]:
    """按一批拼音音节/省名发现全国点位（带行政区编码）。"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda term: suggest(term), terms))
    merged, seen = [], set()
    for part in results:
        for row in part:
            key = (row["name"], row["code"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    return merged


def search(keyword: str, city: str = "", kind: str = "attraction",
           page: int = 0, size: int = 10, code: str = "") -> List[Dict[str, Any]]:
    """按关键词检索全国 POI；city 为空表示不限城市。"""
    wd = f"{city} {keyword}".strip() if city else keyword
    if kind == "hotel" and not any(w in wd for w in ("酒店", "宾馆", "民宿", "旅舍", "公寓")):
        wd = wd + " 酒店"
    url = (API + "?qt=s&wd=" + quote(wd) + f"&pn={max(0, page) * size}&rn={size}"
           + "&ie=utf-8&oue=1&fromproduct=jsapi")
    if code:
        url += "&c=" + quote(str(code))
    try:
        resp = httpclient.get(url, headers={"User-Agent": UA, "Referer": "https://map.baidu.com/"},
                              timeout=max(6, settings.request_timeout))
        payload = resp.json()
    except Exception:
        return []

    rows = payload.get("content") or []
    skip_words = _SKIP_HOTEL if kind == "hotel" else _SKIP_ATTR
    items: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name or any(word in name for word in skip_words):
            continue
        if city and name in (city, city + "市", city + "地区", city + "县"):
            continue
        if "行政区" in str(row.get("std_tag") or ""):
            continue
        coord = parse_geo(str(row.get("geo") or ""))
        if not coord:
            continue
        city_name = _city_of(row, city)
        if not _match_city(city_name, city):
            continue
        detail = ((row.get("ext") or {}).get("detail_info") or {}) if isinstance(row.get("ext"), dict) else {}
        tag = re.sub(r"<[^>]+>", "", str(detail.get("tag") or row.get("tag") or ""))
        if kind == "metro":
            std_tag = str(row.get("std_tag") or "")
            if "地铁站" not in std_tag and "地铁站" not in tag:
                continue
            if any(word in name for word in ("公司", "学校", "小吃", "酒店", "停车场",
                                             "进站口", "出口", "入口", "售票")):
                continue
        if "房地产" in tag or "住宅" in tag or "写字楼" in tag:
            continue
        image = _clean_image(detail.get("image")) or _clean_image(row.get("default_image"))
        addr = str(row.get("addr") or "").strip()
        price_info = _hotel_price(detail) if kind == "hotel" else _attraction_price(detail)
        item: Dict[str, Any] = {
            "source": "baidu_web",
            "source_id": str(row.get("uid") or row.get("id") or name),
            "uid": str(row.get("uid") or ""),
            "name": name,
            "city": city_name,
            "address": addr,
            "phone": str(detail.get("phone") or row.get("tel") or ""),
            "lat": round(coord[0], 6),
            "lng": round(coord[1], 6),
            "rating": _as_float(detail.get("overall_rating")),
            "review_count": _as_int(detail.get("comment_num")),
            "tags": _tags(tag),
            "level": _level(tag),
            "cover_image": image,
            "images": [image] if image else [],
            "photos": [image] if image else [],
            "source_url": "https://map.baidu.com/",
            "kind": kind,
            "price": price_info.get("price"),
            "original_price": price_info.get("original_price"),
            "price_source": price_info.get("price_source") or (
                "Baidu Maps · ticket" if price_info.get("price") is not None else ""),
            "price_note": price_info.get("price_note") or "",
            "price_free_hint": price_info.get("price_free_hint") or "",
            "price_updated_at": time.strftime("%Y-%m-%d %H:%M:%S") if price_info.get("price") is not None else "",
            "specs": price_info.get("specs") or [],
            "open_time": i18n.open_time(str(detail.get("shop_hours") or "")),
            "open_time_zh": str(detail.get("shop_hours") or "").strip(),
        }
        if kind == "hotel":
            item["star"] = _star(str(detail.get("level") or detail.get("category") or ""), name)
            item["star_label"] = str(detail.get("level") or detail.get("category") or "")
            room_image = price_info.get("room_image") or ""
            if room_image:
                item["images"] = [image, room_image] if image else [room_image]
                item["photos"] = item["images"]
            item["hygiene"] = _as_float(detail.get("hygiene_rating"))
            item["facility"] = _as_float(detail.get("facility_rating"))
            item["service"] = _as_float(detail.get("service_rating"))
            ext = detail.get("hotel_ext") if isinstance(detail.get("hotel_ext"), dict) else {}
            item["landmark"] = str(ext.get("landmark_eta") or "")
        else:
            intro = str(detail.get("description") or detail.get("brief") or "").strip()
            if not intro:
                pieces = [i18n.city(city_name), ", ".join(i18n.tags(_tags(tag)[:2])), addr]
                intro = " · ".join([p for p in pieces if p])
            item["intro"] = intro[:200]
            # 中文简介单独保存：城市/标签用原中文，避免语言切换时只剩英文
            raw_tags = _tags(tag)[:2]
            intro_zh = str(detail.get("description") or detail.get("brief") or "").strip()
            if not intro_zh:
                pieces_zh = [city_name, "、".join(raw_tags), addr]
                intro_zh = " · ".join([p for p in pieces_zh if p])
            item["intro_zh"] = intro_zh[:200]
            item["free"] = price_info.get("price") == 0
            specs = price_info.get("specs") or []
            item["ticket_types"] = [{"name": row.get("name"), "price": row.get("price"),
                                     "note": row.get("note")} for row in specs]
        item["offers"] = _offer(item, kind)
        item.setdefault("ticket_types", [])
        item["policy"] = {}
        items.append(item)
    return items


def search_many(city: str, keywords: List[str], kind: str, pages: int = 2,
                workers: int = 6, code: str = "") -> List[Dict[str, Any]]:
    """同一城市并发跑多关键词 + 多页，合并去重。"""
    tasks = [(word, page) for word in keywords for page in range(max(1, pages))]

    def run(task: Tuple[str, int]) -> List[Dict[str, Any]]:
        word, page = task
        try:
            return search(word, city, kind, page, 10, code=code)
        except Exception:
            return []

    merged: List[Dict[str, Any]] = []
    seen = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for part in pool.map(run, tasks):
            for item in part:
                ident = item.get("uid") or (item.get("name"), round(item.get("lat") or 0, 3))
                if ident in seen:
                    continue
                seen.add(ident)
                merged.append(item)
    return merged


def detail(key: str, city: str = "", kind: str = "attraction") -> Optional[Dict[str, Any]]:
    """按名称反查单条 POI（用于详情页实时补全）。"""
    name = key.split("::")[-1]
    for item in search(name, city, kind, 0, 8):
        if item["name"] == name or name in item["name"]:
            return item
    return None


def health() -> Dict[str, Any]:
    """内置源连通性自检（无需密钥）。"""
    started = time.time()
    rows = search("景点", "北京", "attraction", 0, 3)
    return {
        "ok": bool(rows),
        "latency_ms": int((time.time() - started) * 1000),
        "sample": rows[0]["name"] if rows else None,
        "count": len(rows),
        "priced": sum(1 for row in rows if row.get("price") is not None),
    }