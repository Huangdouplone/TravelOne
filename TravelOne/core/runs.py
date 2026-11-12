# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""采集/抓取记录：内存 + JSON 文件，不使用数据库。"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
FILE = BASE_DIR / "data" / "runs.json"
_lock = threading.Lock()
_MAX = 40


def _load() -> List[Dict[str, Any]]:
    if not FILE.exists():
        return []
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def add(entry: Dict[str, Any]) -> None:
    with _lock:
        data = _load()
        entry.setdefault("at", time.strftime("%Y-%m-%dT%H:%M:%S"))
        data.insert(0, entry)
        data = data[:_MAX]
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def latest(limit: int = 10) -> List[Dict[str, Any]]:
    return _load()[:limit]
