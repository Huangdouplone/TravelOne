# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""成品油价格抓取：车主手册（icauto.com.cn）全国油价表 + 汽油价格网兜底。

解析的是公开页面上的省级挂牌价（元/升），保留抓取时间与来源链接；
站点不可达或版面变化导致解析不到时返回 None，由上层如实标注「油价不可用」。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core import httpclient
from core.config import settings

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

NATIONAL_URL = "https://www.icauto.com.cn/oil/"
SLUG_PROVINCE = {
    "beijing": "北京", "shanghai": "上海", "tianjin": "天津", "chongqing": "重庆",
    "hebei": "河北", "shanxi": "山西", "neimenggu": "内蒙古", "liaoning": "辽宁",
    "jilin": "吉林", "heilongjiang": "黑龙江", "jiangsu": "江苏", "zhejiang": "浙江",
    "anhui": "安徽", "fujian": "福建", "jiangxi": "江西", "shandong": "山东",
    "henan": "河南", "hubei": "湖北", "hunan": "湖南", "guangdong": "广东",
    "guangxi": "广西", "hainan": "海南", "sichuan": "四川", "guizhou": "贵州",
    "yunnan": "云南", "xizang": "西藏", "shanxi-3": "陕西", "gansu": "甘肃",
    "qinghai": "青海", "ningxia": "宁夏", "xinjiang": "新疆", "shenzhen": "深圳",
}

_ROW = re.compile(
    r"<tr>\s*<td>\s*<a[^>]*title=\"(?P<title>[^\"]+)最新油价\"[^>]*>(?P<name>[^<]+)</a>\s*</td>"
    r"(?P<cells>(?:\s*<td[^>]*>.*?</td>){5,7})\s*</tr>",
    re.S,
)
_CELL = re.compile(r"<td[^>]*>(?:<a[^>]*>)?\s*([\d.]+)\s*(?:</a>)?\s*</td>", re.S)

# 表格列顺序：90 号、92 号、93 号、95 号、97 号、0 号柴油（部分地区少列）
COLUMNS = ("p90", "p92", "p93", "p95", "p97", "p0")


def _clean(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def fetch_national() -> Optional[Dict[str, Any]]:
    """一次请求拿到全国各省的汽油/柴油挂牌价。"""
    try:
        resp = httpclient.get(NATIONAL_URL, headers={"User-Agent": UA, "Referer": NATIONAL_URL},
                              timeout=max(10, settings.request_timeout + 6))
        text = resp.text if resp.status_code < 400 else ""
    except Exception:
        text = ""
    if not text:
        return None
    provinces: Dict[str, Dict[str, Any]] = {}
    for match in _ROW.finditer(text):
        name = _clean(match.group("name"))
        if not name or len(name) > 8:
            continue
        values = [float(v) for v in _CELL.findall(match.group("cells")) if 2 < float(v) < 20]
        # 列数不足说明该省表格结构不同，宁可不采用也不要错位标价
        if len(values) < len(COLUMNS):
            continue
        row: Dict[str, float] = {}
        for key, value in zip(COLUMNS, values):
            row[key] = value
        provinces[name] = row
    if not provinces:
        return None
    adjusted = ""
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        adjusted = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return {"provinces": provinces, "adjusted_at": adjusted,
            "source": "icauto.com.cn", "source_url": NATIONAL_URL}


def fetch_oil(province: str = "北京") -> Optional[Dict[str, Any]]:
    """抓取指定省级区域的油价；全国表缺失时回落到单省页面。"""
    national = fetch_national()
    wanted = _clean(province)
    if national:
        rows = national["provinces"]
        key = next((k for k in rows if k and (k == wanted or k in wanted or wanted in k)), None)
        if key:
            return {"province": key, "prices": rows[key], "adjusted_at": national["adjusted_at"],
                    "source": national["source"], "source_url": national["source_url"]}
    return _fetch_single(wanted)


def _fetch_single(province: str) -> Optional[Dict[str, Any]]:
    slug = next((s for s, name in SLUG_PROVINCE.items() if name == province or name in province), "beijing")
    url = f"http://www.qiyoujiage.com/{slug}.shtml"
    try:
        resp = httpclient.get(url, headers={"User-Agent": UA, "Referer": "http://www.qiyoujiage.com/"},
                              timeout=max(10, settings.request_timeout + 6))
        text = resp.text if resp.status_code < 400 else ""
    except Exception:
        text = ""
    if not text:
        return None
    prices: Dict[str, float] = {}
    for label, value in re.findall(r"<dl>\s*<dt>(.*?)</dt>\s*<dd>\s*([\d.]+)\s*</dd>\s*</dl>", text, re.S):
        label = _clean(label)
        price = float(value)
        if not (2 < price < 20):
            continue
        if "98" in label and "汽油" in label:
            prices.setdefault("p98", price)
        elif "95" in label and "汽油" in label:
            prices.setdefault("p95", price)
        elif "92" in label and "汽油" in label:
            prices.setdefault("p92", price)
        elif "90" in label and "汽油" in label:
            prices.setdefault("p90", price)
        elif "柴油" in label:
            prices.setdefault("p0", price)
    if not prices:
        return None
    return {"province": province, "prices": prices, "adjusted_at": "",
            "source": "qiyoujiage.com", "source_url": url}


def all_provinces() -> List[str]:
    national = fetch_national()
    return sorted((national or {}).get("provinces", {}).keys())