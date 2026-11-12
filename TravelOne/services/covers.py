# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""景点封面生成器。

平台通常不提供可长期引用的图片直链，且离线环境无法加载外链图片，
因此按景点名生成确定性的矢量封面（渐变 + 山峦/水面/建筑剪影），
真实图源存在时优先使用外链，加载失败自动回落到本生成器。
"""
from __future__ import annotations

import hashlib
from typing import Tuple

PALETTES = [
    ("#1d3f6e", "#3f7fb5", "#d9e8f5"),
    ("#2f4858", "#5c8a72", "#e8efe4"),
    ("#5b2c3b", "#b5615c", "#f6e3d7"),
    ("#213b4d", "#4f7c8c", "#dcecef"),
    ("#4a3a2a", "#a4834f", "#f3e8d3"),
    ("#33365c", "#6d6fa8", "#e6e4f4"),
    ("#1f4b41", "#4b9b83", "#e0f1ea"),
    ("#5a3a1e", "#c07a3c", "#fbead6"),
]


def _palette(seed: str) -> Tuple[str, str, str]:
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return PALETTES[int(digest[:8], 16) % len(PALETTES)]


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _font_escape(name: str) -> str:
    return "".join(ch for ch in name if ch.isprintable())


def make_cover(name: str, variant: int = 0, subtitle: str = "", width: int = 960, height: int = 600) -> str:
    seed = f"{name}-{variant}"
    c1, c2, c3 = _palette(seed)
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    hills = []
    for i in range(3):
        offset = int(digest[i * 2:i * 2 + 2], 16) % 90
        base = height - 120 - i * 46 - offset
        hills.append(
            f'<path d="M0 {base} C {width*0.18:.0f} {base-70} {width*0.32:.0f} {base+40} {width*0.5:.0f} {base-10}'
            f' C {width*0.68:.0f} {base-60} {width*0.82:.0f} {base+30} {width} {base-30} L {width} {height} L 0 {height} Z"'
            f' fill="rgba(255,255,255,{0.06 + i * 0.05:.2f})"/>'
        )
    sun_x = 120 + int(digest[8:10], 16) % 620
    sun_y = 110 + int(digest[10:12], 16) % 90
    title = _esc(_font_escape(name))[:18]
    sub = _esc(_font_escape(subtitle))[:24]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="58%" stop-color="{c2}"/>
      <stop offset="100%" stop-color="{c3}"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="20%" r="60%">
      <stop offset="0%" stop-color="rgba(255,255,255,0.45)"/>
      <stop offset="100%" stop-color="rgba(255,255,255,0)"/>
    </radialGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <rect width="{width}" height="{height}" fill="url(#glow)"/>
  <circle cx="{sun_x}" cy="{sun_y}" r="58" fill="rgba(255,246,214,0.85)"/>
  <circle cx="{sun_x}" cy="{sun_y}" r="86" fill="rgba(255,246,214,0.16)"/>
  {''.join(hills)}
  <g opacity="0.92">
    <text x="48" y="{height-96}" font-family="'Microsoft YaHei','PingFang SC',system-ui,sans-serif" font-size="52" font-weight="700" fill="#ffffff">{title}</text>
    <text x="50" y="{height-52}" font-family="'Microsoft YaHei','PingFang SC',system-ui,sans-serif" font-size="24" fill="rgba(255,255,255,0.86)">{sub}</text>
  </g>
</svg>"""