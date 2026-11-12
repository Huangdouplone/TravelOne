#!/usr/bin/env bash
# Copyright (c) 2026 黄豆666/huangdouplone
# SPDX-License-Identifier: MIT
# 旅图 TravelOne 启动脚本（macOS / Linux）
set -u
cd "$(dirname "$0")" || exit 1
mkdir -p logs

PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys; assert sys.version_info >= (3, 8)" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done

if [ -z "$PY" ]; then
  echo "[错误] 未找到 Python 3.8+，请先安装后再运行。" >&2
  echo "        macOS: brew install python3    Linux: sudo apt install python3" >&2
  exit 1
fi

echo "============================================"
echo "  旅图 TravelOne · 一站式旅行助手"
echo "============================================"
echo "  解释器: $PY"
echo "  访问地址: http://127.0.0.1:8848"
echo "  日志文件: logs/startup.log"
echo "  按 Ctrl+C 停止服务"
echo "============================================"
echo

exec "$PY" app.py
