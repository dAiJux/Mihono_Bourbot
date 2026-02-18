@echo off
echo ========================================
echo   Mihono Bourbot — Launcher
echo ========================================
echo.

cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.8+ and add it to PATH.
    pause
    exit /b 1
)

:: Create directories
if not exist "templates" mkdir templates
if not exist "logs" mkdir logs
if not exist "config" mkdir config

:: Centralize __pycache__ into .cache/
set "PYTHONPYCACHEPREFIX=%~dp0.cache"

:: Launch GUI
echo Starting GUI...
python -m scripts

pause
