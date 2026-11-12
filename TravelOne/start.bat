@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

set "PY="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys" >nul 2>nul
    if not errorlevel 1 set "PY=python"
  )
)

if not defined PY (
  echo.
  echo [错误] 未检测到可用的 Python 3.8+
  echo        请安装 Python 3.8 或更高版本，并在安装时勾选 "Add Python to PATH"
  echo        下载地址: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

echo ============================================
echo   旅图 TravelOne  ·  一站式旅行助手
echo ============================================
echo   解释器: %PY%
echo   访问地址: http://127.0.0.1:8848
echo   日志文件: logs\startup.log
echo   按 Ctrl+C 停止服务
echo ============================================
echo.

%PY% app.py

if errorlevel 1 (
  echo.
  echo [启动失败] 服务未能正常启动，最近的日志如下：
  echo --------------------------------------------
  if exist "logs\startup.log" (
    powershell -NoProfile -Command "Get-Content -Path 'logs\startup.log' -Tail 25"
  )
  echo --------------------------------------------
  echo 常见原因：端口 8848 被占用、Python 版本过低、或目录无写入权限。
  echo.
  pause
)
endlocal
