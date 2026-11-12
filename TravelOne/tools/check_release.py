# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
"""发布前自检：版权头、README/LICENSE、离线页体积与关键文件。

用法：
    python tools/check_release.py
退出码 0 表示通过，1 表示存在需要修复的问题。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parent if (PROJECT_ROOT.parent / "README.md").exists() else PROJECT_ROOT
MARK = "黄豆666/huangdouplone"
SOURCE_SUFFIXES = (".py", ".js", ".css", ".html", ".sh")
EXCLUDE_DIRS = {"vendor", "__pycache__", "data", "logs", "docs", ".git", "shots"}
EXCLUDE_FILES = {"static/app.html", "TravelOne.html"}
MAX_PAGE_BYTES = 20 * 1024 * 1024


def source_files() -> List[Path]:
    out = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if any(part in EXCLUDE_DIRS for part in path.relative_to(PROJECT_ROOT).parts):
            continue
        if rel in EXCLUDE_FILES or rel.startswith("static/vendor/"):
            continue
        out.append(path)
    return out


def main() -> int:
    errors: List[str] = []
    missing = []
    for path in source_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if MARK not in text:
            missing.append(path.relative_to(PROJECT_ROOT).as_posix())
    if missing:
        errors.append("缺少版权头的源码：%s" % ", ".join(missing[:8]))

    readme = REPO_ROOT / "README.md"
    if not readme.exists() or len(readme.read_text(encoding="utf-8")) < 800:
        errors.append("README.md 缺失或内容过短")

    license_file = REPO_ROOT / "LICENSE"
    if not license_file.exists():
        errors.append("LICENSE 缺失")
    else:
        text = license_file.read_text(encoding="utf-8")
        if "MIT License" not in text or MARK not in text:
            errors.append("LICENSE 不是带版权人的 MIT 文本")

    page = PROJECT_ROOT / "TravelOne.html"
    if page.exists():
        size = page.stat().st_size
        if size > MAX_PAGE_BYTES:
            errors.append("TravelOne.html %.2f MB 超过 20MB" % (size / 1048576))
        else:
            print("页面体积：%.2f MB（限制 20MB）" % (size / 1048576))
    else:
        errors.append("TravelOne.html 缺失")

    if errors:
        print("自检未通过：")
        for item in errors:
            print(" -", item)
        return 1
    print("自检通过：版权头 %d 个文件，README/LICENSE 齐全，页面体积达标" % len(source_files()))
    return 0


if __name__ == "__main__":
    sys.exit(main())