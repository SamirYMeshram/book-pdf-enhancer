@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
pip install -r optional_requirements_ocr.txt
echo.
echo OCR Python packages installed. You may still need external Tesseract/Ghostscript executables.
pause
