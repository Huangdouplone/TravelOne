# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""Wikidata 官方标签层（CC0，免密钥）。

只取「中国境内的世界文化遗产」这一层：Q9259 = World Heritage Site，
P17 = 国家，P625 = 坐标，P856 = 官方网站，skos:altLabel = 中文别名（如「明清故宫」）。

数据通过 QLever 的公共 SPARQL 端点查询（Wikidata 官方端点在本机网络下握手超时）。
查询失败返回 None，由 services.reference 用本地快照兜底，页面不会因此空白。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core import httpclient
from core.config import settings

ENDPOINT = "https://qlever.cs.uni-freiburg.de/api/wikidata"
# 备用端点：QLever 偶发超时/限流时改走 OpenLink 的 Wikidata 镜像（同一套 SPARQL）
FALLBACK_ENDPOINT = "https://wikidata.demo.openlinksw.com/sparql"
SOURCE = {
    "name": "wikidata",
    "label": "Wikidata (official labels)",
    "license": "CC0 1.0",
    "source_url": "https://www.wikidata.org/",
    "endpoint": ENDPOINT,
    "note": "China's World Heritage sites: Chinese/English names plus aliases and coordinates. Labels only, no prices or ratings.",
}

_PREFIX = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

_HERITAGE_QUERY = _PREFIX + """
SELECT ?i ?label ?en ?alt ?coord ?site WHERE {
  ?i wdt:P1435 wd:Q9259; wdt:P17 wd:Q148; wdt:P625 ?coord .
  OPTIONAL { ?i rdfs:label ?label FILTER(lang(?label) IN ("zh", "zh-hans", "zh-cn", "zh-sg")) }
  OPTIONAL { ?i rdfs:label ?en FILTER(lang(?en) = "en") }
  OPTIONAL { ?i skos:altLabel ?alt FILTER(lang(?alt) IN ("zh", "zh-hans", "zh-cn")) }
  OPTIONAL { ?i wdt:P856 ?site }
} LIMIT 600
"""

_COORD = re.compile(r"POINT\(\s*([-0-9.]+)\s+([-0-9.]+)\s*\)")


def _sparql(query: str) -> Optional[List[Dict[str, Any]]]:
    """按主端点 → 备用端点顺序取数；两个都不可用才返回 None。"""
    for endpoint in (ENDPOINT, FALLBACK_ENDPOINT):
        try:
            resp = httpclient.get(endpoint, params={"query": query},
                                  headers={"Accept": "application/json",
                                           "User-Agent": "TravelOne/1.0 (research)"},
                                  timeout=max(6, min(15, settings.request_timeout + 6)))
        except Exception:
            continue
        if resp.status_code >= 400:
            continue
        try:
            payload = resp.json()
        except Exception:
            continue
        rows = (payload.get("results") or {}).get("bindings") or []
        if isinstance(rows, list) and rows:
            return rows
    return None


def _value(row: Dict[str, Any], key: str) -> str:
    cell = row.get(key) or {}
    return str(cell.get("value") or "").strip()


def heritage() -> Optional[List[Dict[str, Any]]]:
    """返回中国世界遗产名录；网络或上游异常时返回 None。"""
    rows = _sparql(_HERITAGE_QUERY)
    if rows is None:
        return None

    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        qid = _value(row, "i").rsplit("/", 1)[-1]
        if not qid:
            continue
        entry = grouped.setdefault(qid, {"zh": set(), "alt": set(), "en": set(),
                                         "coord": _value(row, "coord"), "site": ""})
        label = _value(row, "label")
        alt = _value(row, "alt")
        en = _value(row, "en")
        site = _value(row, "site")
        if label:
            entry["zh"].add(label)
        if alt:
            entry["alt"].add(alt)
        if en:
            entry["en"].add(en)
        if site.startswith("http"):
            entry["site"] = site

    out: List[Dict[str, Any]] = []
    for qid, entry in grouped.items():
        match = _COORD.search(entry["coord"])
        zh_names = sorted(entry["zh"] or entry["alt"])
        en_names = sorted(entry["en"])
        if not match or not (zh_names or en_names):
            continue
        aliases = sorted((entry["zh"] | entry["alt"]) - set(zh_names[:1]))
        out.append({
            "qid": qid,
            "name_zh": zh_names[0] if zh_names else "",
            "name_en": en_names[0] if en_names else "",
            "aliases": [a for a in aliases if a][:6],
            "lat": float(match.group(2)),
            "lng": float(match.group(1)),
            "site": entry["site"],
            "kind": "heritage",
            "source": "wikidata",
            "license": SOURCE["license"],
        })
    out.sort(key=lambda x: (x["name_zh"] or x["name_en"]))
    return out or None