# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""Build static/app.html as a single page with CSS and JS inlined.

Usage:
    python tools/build_single_page.py

The output has no external local references: only /api endpoints and the
optional Baidu Maps CDN. Source files stay in css/ and js/ for maintenance.
"""
from __future__ import annotations

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STATIC = BASE / "static"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    html = read(STATIC / "index.html")
    vendor_css = read(STATIC / "vendor" / "maplibre-gl.css")
    vendor_js = read(STATIC / "vendor" / "maplibre-gl.js")
    css = read(STATIC / "css" / "app.css")
    scripts = [
        read(STATIC / "js" / "api.js"),
        read(STATIC / "js" / "map.js"),
        read(STATIC / "js" / "i18n.js"),
        read(STATIC / "js" / "theme.js"),
        read(STATIC / "js" / "app.js"),
    ]
    for chunk in scripts:
        if "</script" in chunk.lower():
            raise SystemExit("A script contains </script> and cannot be inlined safely")

    nl = chr(10)
    style_block = ("<style>" + nl + vendor_css.strip() + nl + "</style>" + nl +
                   "<style>" + nl + css.strip() + nl + "</style>")
    for link in ('<link rel="stylesheet" href="/css/app.css">',
                 '<link rel="stylesheet" href="css/app.css">'):
        html = html.replace(link, style_block)
    html = html.replace('<link rel="stylesheet" href="vendor/maplibre-gl.css">', "", 1)

    if "</script" in vendor_js.lower():
        raise SystemExit("MapLibre bundle contains </script> and cannot be inlined safely")
    vendor_block = "\n<script>\n" + vendor_js.strip() + "\n</script>"
    html = html.replace('<script src="vendor/maplibre-gl.js"></script>', vendor_block, 1)
    bundle = "\n".join("(function () {\n" + chunk.strip() + "\n})();" for chunk in scripts)
    block = "\n<script>\n" + bundle + "\n</script>"
    pattern = re.compile(r'\s*<script src="(?:/)?js/api\.js"></script>\s*'
                         r'<script src="(?:/)?js/map\.js"></script>\s*'
                         r'<script src="(?:/)?js/i18n\.js"></script>\s*'
                         r'<script src="(?:/)?js/theme\.js"></script>\s*'
                         r'<script src="(?:/)?js/app\.js"></script>')

    def _insert(_match: re.Match) -> str:
        return block

    html = pattern.sub(_insert, html)
    html = html.replace("<!DOCTYPE html>",
                        "<!DOCTYPE html>\n<!-- TravelOne single-file build: CSS and JS inlined; "
                        "only local /api endpoints and the optional map CDN are referenced -->", 1)

    target = STATIC / "app.html"
    target.write_text(html, encoding="utf-8")
    remaining = re.findall(r'(?:src|href)="(/[^"]+)"', html)
    print("written", target, len(html), "chars")
    print("remaining refs:", remaining)
    bad = [ref for ref in remaining if not ref.startswith("/api/")]
    if bad:
        print("warning: non-API local references remain:", bad)


if __name__ == "__main__":
    main()