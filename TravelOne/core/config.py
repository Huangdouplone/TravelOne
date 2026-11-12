# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""运行时配置。

配置来源优先级：环境变量 > 项目根目录 .env 文件 > 代码内默认值。
密钥类配置只在内存中保留明文，落盘时用 core.secure 加密。
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"

_ENV_LOADED = False


def _load_dotenv() -> None:
    """读取项目根目录的 .env（存在才读），不覆盖已存在的环境变量。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            raw = env_file.read_text(encoding="utf-8-sig")
        except Exception:
            raw = env_file.read_text(encoding="gbk", errors="ignore")
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    _ENV_LOADED = True


def get(key: str, default: str = "") -> str:
    _load_dotenv()
    return os.environ.get(key, default) or default


def get_int(key: str, default: int) -> int:
    try:
        return int(get(key, str(default)))
    except (TypeError, ValueError):
        return default


def get_bool(key: str, default: bool = False) -> bool:
    value = get(key, "1" if default else "0").lower()
    return value in ("1", "true", "yes", "on")


class Settings:
    """集中暴露运行参数，方便 API 与采集器读取。"""

    def __init__(self) -> None:
        self.host = get("TRAVEL_HOST", "127.0.0.1")
        self.port = get_int("TRAVEL_PORT", 8848)
        self.google_maps_key = get("GOOGLE_MAPS_JS_KEY", "")
        # 采集节奏：默认 5 分钟（300 秒），用户可在 .env 中覆盖
        self.collect_interval_seconds = get_int("COLLECT_INTERVAL_SECONDS", 300)
        self.collect_on_startup = get_bool("COLLECT_ON_STARTUP", True)
        # 采集目标城市，逗号分隔；页面可随时查询任意其他城市
        self.collect_cities = [
            c.strip() for c in get("COLLECT_CITIES", "北京,上海,杭州,成都,西安,广州,重庆").split(",") if c.strip()
        ]
        self.request_timeout = get_int("HTTP_TIMEOUT", 8)
        self.enable_live_crawl = get_bool("ENABLE_LIVE_CRAWL", True)
        # 百度地图 JS API 浏览器端 AK（地图渲染）
        self.baidu_js_ak = get("BAIDU_MAP_JS_AK", "")
        # 百度地图 Web 服务 AK（服务端路线规划 / 地理编码）
        self.baidu_server_ak = get("BAIDU_MAP_SERVER_AK", "") or self.baidu_js_ak
        self.baidu_api_host = get("BAIDU_MAP_API_HOST", "https://api.map.baidu.com")
        # 内置实时源开关（LIVE_CRAWL=0 时只用上一次快照，用于故障演练）
        self.live_enabled = get("LIVE_CRAWL", "1") != "0"
        # 运行时配置（页面上填写的 AK），保存在 data/runtime_config.json
        self.runtime_config_path = Path(get("RUNTIME_CONFIG", str(DATA_DIR / "runtime_config.json")))

    @property
    def map_enabled(self) -> bool:
        return bool(self.baidu_js_ak)

    @property
    def server_route_enabled(self) -> bool:
        return bool(self.baidu_server_ak)


# 运行时可配置项：密钥类加密落盘
SECRET_FIELDS = {
    "baidu_js_ak": "baidu_js_ak_enc",
    "baidu_server_ak": "baidu_server_ak_enc",
}
PLAIN_FIELDS: tuple = ()

SETTING_ATTR = {
    "baidu_js_ak": "baidu_js_ak",
    "baidu_server_ak": "baidu_server_ak",
}


def _read_runtime_file() -> dict:
    import json
    path = settings.runtime_config_path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def apply_runtime_overrides() -> dict:
    """读取页面上保存的运行时配置，密钥解密后只保留在内存中。"""
    from core import secure
    data = _read_runtime_file()
    resolved: dict = {}
    for field, enc_key in SECRET_FIELDS.items():
        value = secure.decrypt(data.get(enc_key, "")) or data.get(field, "")
        if value:
            setattr(settings, SETTING_ATTR[field], value)
            resolved[field] = value
    return resolved


def save_runtime_config(payload: dict) -> dict:
    """保存运行时配置：密钥以密文落盘，明文只留在内存。"""
    import json
    from core import secure
    path = settings.runtime_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    stored = _read_runtime_file()
    for field in list(SECRET_FIELDS) + list(PLAIN_FIELDS):
        stored.pop(field, None)
    masked = {}
    for field, value in payload.items():
        if value is None or field not in SECRET_FIELDS:
            continue
        text = str(value).strip()
        if not text:
            continue
        stored[SECRET_FIELDS[field]] = secure.encrypt(text)
        setattr(settings, SETTING_ATTR[field], text)
        masked[field] = secure.mask(text)
    path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "masked": masked,
        "baidu_js_ak": settings.baidu_js_ak,
        "map_enabled": settings.map_enabled,
        "server_ak_configured": settings.server_route_enabled,
    }


settings = Settings()
apply_runtime_overrides()