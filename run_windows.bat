@echo off
setlocal
cd /d "%~dp0"
title UltraBook PDF Clarity Studio

echo ===============================================================
echo UltraBook PDF Clarity Studio - Windows Runner
echo ===============================================================
echo.

if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Make sure Python is installed.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Package install failed. Check your internet/Python setup.
    pause
    exit /b 1
)

echo.
echo Starting app...
python app.py
pause
