# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""TravelOne 一站式旅行应用 —— 服务入口。

启动：
    python app.py
默认监听 127.0.0.1:8848，可通过 .env / 环境变量调整。

本项目不使用数据库：所有景点、酒店、地铁与价格都来自运行时实时抓取，
抓取结果以 JSON 快照保存在 data/cache/，只用于上游不可达时回放。
"""
from __future__ import annotations

import mimetypes
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import cache_store  # noqa: E402
from core.config import BASE_DIR, STATIC_DIR, settings  # noqa: E402
from services import (coverage, harvest, intl_warmup, live, platforms, reference,  # noqa: E402
                      warmup)
import web_api  # noqa: E402

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("image/webp", ".webp")

BANNER = """
  ____________________________________________
  TravelOne  ·  一站式旅行助手
  实时抓取景点/酒店 · 门票房价比价 · 地图定位 · 行程路线
  无数据库 · 无预置数据 · 单页应用
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "TravelOne/4.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # 精简日志
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _handle(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""

        if path.startswith("/api/"):
            status, headers, payload = web_api.dispatch(method, path, query, body)
            self._respond(status, headers, payload)
            return
        self._serve_static(path)

    def do_GET(self) -> None:
        self._handle("GET")

    def do_HEAD(self) -> None:
        self._handle("GET")

    def do_POST(self) -> None:
        self._handle("POST")

    def do_PUT(self) -> None:
        self._handle("PUT")

    def do_DELETE(self) -> None:
        self._handle("DELETE")

    def _respond(self, status: int, headers: dict, payload: bytes) -> None:
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/") or "app.html"
        target = (STATIC_DIR / rel).resolve()
        try:
            target.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._respond(403, {"Content-Type": "text/plain; charset=utf-8"}, "403 Forbidden".encode())
            return
        if target.is_dir():
            target = target / "app.html"
        if not target.exists() and rel == "app.html":
            target = STATIC_DIR / "index.html"
        if not target.exists():
            self._respond(404, {"Content-Type": "text/html; charset=utf-8"},
                          ("<!doctype html><meta charset='utf-8'><h1>404</h1><p>页面不存在，"
                           "<a href='/'>返回首页</a></p>").encode("utf-8"))
            return
        mime, _ = mimetypes.guess_type(str(target))
        payload = target.read_bytes()
        headers = {
            "Content-Type": (mime or "application/octet-stream") + (
                "; charset=utf-8" if (mime or "").startswith("text") or mime == "application/javascript" else ""),
            "Cache-Control": "no-cache" if target.suffix in (".html", ".js", ".css") else "public, max-age=3600",
        }
        self._respond(200, headers, payload)


LOG_DIR = Path(BASE_DIR) / "logs"
LOG_FILE = LOG_DIR / "startup.log"


def log(message: str = "") -> None:
    """同时输出到控制台与 logs/startup.log，便于双击启动失败后排查。"""
    print(message, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fh.write("[" + stamp + "] " + str(message) + chr(10))
    except Exception:
        pass


def main() -> None:
    log(BANNER)
    log(f"  工作目录: {BASE_DIR}")
    log(f"  Python: {sys.version.split()[0]} ({sys.executable})")
    try:
        (Path(BASE_DIR) / "data" / "cache").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log(f"  [错误] 无法创建缓存目录：{type(exc).__name__}: {exc}")
        log("  常见原因：目录无写入权限，请把项目放到用户目录下再试")
        sys.exit(1)

    stats = live.stats()
    log("  存储: JSON 快照（data/cache），不使用数据库")
    log("  已有存档：景点 %d / 酒店 %d / 地铁 %d" % (
        stats["by_kind"].get("attraction", 0), stats["by_kind"].get("hotel", 0),
        stats["by_kind"].get("metro", 0)))
    log("  覆盖模式: 动态全网覆盖（运行时发现行政区 → 按编码持续轮扫）")
    log("  内置实时源: 百度地图网页检索（免配置）")
    log("  百度地图 AK: JS %s; 服务端路线 %s" % (
        "已配置" if settings.map_enabled else "未配置（使用离线示意地图）",
        "已配置" if settings.server_route_enabled else "未配置（使用本地路径估算）"))

    # 缓存单份策略：启动先清掉同城的旧快照与不再被引用的图片
    try:
        pruned = cache_store.prune(force=True)
        images = live.prune_images()
        if pruned.get("removed") or images.get("removed"):
            log("  缓存清理：删除 %d 份旧快照、%d 张未引用图片，释放 %.1f MB" % (
                pruned.get("removed", 0), images.get("removed", 0),
                (pruned.get("freed_bytes", 0) + images.get("freed_bytes", 0)) / 1048576))
    except Exception as exc:
        log("  缓存清理失败：%s: %s" % (type(exc).__name__, exc))

    coverage.start_worker()
    # 启动预热：服务一开就按城市队列不间断抓取，首屏不再只有零星数据
    boot = warmup.start_worker()
    log("  启动预热: 后台常驻抓取中（队列 %d 座城市，首轮先强刷 %d 座）" % (
        boot.get("total") or 0, warmup.FORCE_REFRESH_FIRST))
    log("  预热进度: /api/warmup（页面「数据源」面板同样可见）")
    iboot = intl_warmup.start_worker()
    log("  国际版预热: 后台常驻抓取中（队列 %d 座城市）" % (iboot.get("total") or 0))
    threading.Thread(target=platforms.warm, name="platform-warm", daemon=True).start()
    # 官方标签层（Wikidata）后台预热，避免首次打开详情页等待联网
    threading.Thread(target=reference.heritage, name="reference-warm", daemon=True).start()

    httpd = None
    port = settings.port
    for offset in range(0, 8):
        candidate = settings.port + offset
        try:
            httpd = ThreadingHTTPServer((settings.host, candidate), Handler)
            port = candidate
            break
        except OSError:
            log(f"  端口 {candidate} 不可用（被占用或无权限），继续尝试下一个")
    if httpd is None:
        log("  [错误] 8848-8855 端口均被占用，请关闭占用程序或修改 .env 中的 TRAVEL_PORT")
        sys.exit(1)
    if port != settings.port:
        log(f"  提示：端口 {settings.port} 被占用，已自动改用 {port}")

    httpd.daemon_threads = True
    url = f"http://{settings.host}:{port}"
    log("")
    log(f"  访问地址: {url}")
    log("  按 Ctrl+C 停止服务")
    log("")
    if os.environ.get("AUTO_OPEN_BROWSER", "1") != "0":
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("正在停止服务...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()