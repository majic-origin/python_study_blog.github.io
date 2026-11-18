@echo off
rem ============================================================
rem  Launcher only. All menu text lives in run.py (UTF-8),
rem  so this file stays pure ASCII to avoid cmd codepage issues.
rem ============================================================
cd /d "%~dp0"

set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" run.py menu
echo.
pause
