@echo off
title Lazy Boy - PC Server
echo.
echo ========================================
echo        LAZY BOY - Remote Control
echo ========================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

echo [*] Installing dependencies...
pip install -r server\requirements.txt --quiet 2>nul

echo [*] Starting Lazy Boy Server...
echo.
cd server
python main.py

pause
