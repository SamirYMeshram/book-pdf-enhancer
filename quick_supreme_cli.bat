@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Drag and drop a PDF file onto this BAT file.
    pause
    exit /b 1
)
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
set INPUT=%~1
set OUTPUT=%~dpn1_ultrabook_supreme.pdf
python cli.py "%INPUT%" "%OUTPUT%" --profile supreme --dpi 600 --ocr none
pause
