@echo off
title FlytBase Drone Security Analyst Agent - Demo
echo ======================================================================
echo Launching Drone Security Analyst Agent Demo...
echo ======================================================================
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py --demo
) else (
    python main.py --demo
)
echo.
echo ======================================================================
echo Execution complete.
echo ======================================================================
pause
