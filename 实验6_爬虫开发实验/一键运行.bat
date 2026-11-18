@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

:menu
cls
echo ============================================================
echo                    爬虫实验 ^| 一键菜单
echo ============================================================
echo   1. 环境检查（依赖 / 浏览器内核）
echo   2. 一键演示（本地样例，不联网，约 30 秒）
echo   3. 抓静态列表页      -^> result.csv
echo   4. 抓接口 / 动态页   （自动嗅探，方案 A）
echo   5. 渲染动态页        （浏览器渲染，方案 B）
echo   6. 双方案对比        -^> compare.md
echo   7. 查看文档清单
echo   0. 退出
echo ============================================================
set /p "c=请输入序号后回车: "

if "%c%"=="1" (
    "%PY%" run.py 检查
    echo.
    pause
    goto menu
)

if "%c%"=="2" (
    "%PY%" run.py 演示 1
    echo.
    pause
    goto menu
)

if "%c%"=="3" (
    set /p "u=请输入列表页 URL: "
    "%PY%" run.py 基础 "!u!"
    echo.
    echo 输出文件：result.csv
    pause
    goto menu
)

if "%c%"=="4" (
    set /p "u=请输入页面 URL（会自动抓接口）: "
    "%PY%" run.py 接口 "!u!"
    echo.
    echo 输出文件：result_api.csv
    pause
    goto menu
)

if "%c%"=="5" (
    set /p "u=请输入页面 URL: "
    "%PY%" run.py 渲染 "!u!"
    echo.
    echo 输出文件：result_browser.csv
    pause
    goto menu
)

if "%c%"=="6" (
    set /p "p=页面 URL: "
    set /p "a=接口 URL: "
    "%PY%" run.py 对比 --page-url "!p!" --api "!a!" --rounds 3
    echo.
    echo 输出文件：compare.md / metrics_raw.json
    pause
    goto menu
)

if "%c%"=="7" (
    "%PY%" run.py 文档
    echo.
    pause
    goto menu
)

if "%c%"=="0" exit /b 0
goto menu
