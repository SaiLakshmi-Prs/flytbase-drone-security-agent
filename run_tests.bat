@echo off
title FlytBase Drone Security Analyst Agent - QA Tests
echo ======================================================================
echo Running QA Unit Test Suite (16 Tests)...
echo ======================================================================
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m unittest qa_tests.py -v
) else (
    python -m unittest qa_tests.py -v
)
echo.
echo ======================================================================
echo Test execution complete.
echo ======================================================================
pause
