@echo off
title FlytBase Drone Security Analyst Agent - Interactive Q&A
echo ======================================================================
echo Launching Interactive Q&A Console...
echo ======================================================================
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py --interactive
) else (
    python main.py --interactive
)
echo.
pause
