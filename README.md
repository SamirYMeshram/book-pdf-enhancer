# UltraBook PDF Clarity Studio

A local Python desktop app and CLI for restoring **text-heavy scanned book PDFs** into a clearer enhanced PDF. It is designed for quality-first processing, not speed.

## What it does

- Renders scanned PDF pages at high DPI: 300 / 400 / 500 / 600.
- Cleans yellow, grey, shadowed, and uneven book-page backgrounds.
- Sharpens text strokes without intentionally damaging page geometry.
- Deskews pages.
- Removes black borders and tiny speckles.
- Builds a new enhanced PDF output, not just images.
- Can optionally create a searchable OCR PDF using OCRmyPDF or Tesseract if installed.
- Includes a GUI and CLI.

## Use legally

Use this for PDFs, scans, notes, public-domain documents, or books/documents you are legally allowed to process.

## Quick start on Windows

1. Extract the ZIP.
2. Open the folder.
3. Double-click:

```bat
run_windows.bat
```

If you prefer VS Code terminal:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python app.py
```

## Best maximum-quality settings for text-heavy scanned books

Use these in the GUI:

```text
Profile: Supreme Text Clarity - 600 DPI
DPI: 600
Output mode: Auto mixed
Deskew: ON
Clean borders: ON
Background flattening: 1.00
Shadow removal: 1.00
CLAHE/local contrast: ON
Denoise: 0.60 to 0.80
Sharpen: 0.80 to 1.00
Binarize text pages: ON
Speckle removal: ON
OCR searchable output: optional
```

## Safer setting if small letters become too thin

```text
Profile: Safe Grayscale Book - 400 DPI
DPI: 400
Output mode: Grayscale
Binarize text pages: OFF
Denoise: 0.45
Sharpen: 0.65
Background flattening: 0.85
```

## CLI examples

Maximum clarity:

```powershell
python cli.py "input.pdf" "output_enhanced.pdf" --profile supreme --dpi 600 --ocr none
```

Enhanced and searchable if OCRmyPDF is installed:

```powershell
python cli.py "input.pdf" "output_searchable.pdf" --profile supreme --dpi 600 --ocr ocrmypdf --lang eng
```

Preview one page before full processing:

```powershell
python cli.py "input.pdf" "output.pdf" --profile supreme --dpi 400 --preview-page 5
```

## OCR setup notes

The enhancer works without OCR. For searchable PDF output, install one of these:

- Tesseract OCR
- OCRmyPDF
- Ghostscript, if OCRmyPDF requires it

On Windows, the easiest path is usually installing Tesseract first, then OCRmyPDF if needed.

## Output quality notes

For highest visual quality, the app uses lossless page images inside the PDF. This can create large output files. That is intentional. You said quality matters more than time or size.

## Project structure

```text
app.py                         GUI launcher
cli.py                         CLI launcher
run_windows.bat                Windows installer/runner
requirements.txt               Core packages
optional_requirements_ocr.txt  OCR extras
ultrabook_pdf_clarity_studio/
  models.py                    Settings and result dataclasses
  profiles.py                  Preset quality profiles
  renderer.py                  PDF rendering with PyMuPDF
  page_analyzer.py             Page classification and metrics
  image_pipeline.py            OpenCV/scikit-image restoration engine
  pdf_builder.py               Enhanced PDF builder
  ocr.py                       OCRmyPDF/Tesseract wrappers
  worker.py                    Full processing orchestration
  ui_main.py                   CustomTkinter GUI
  cli_impl.py                  CLI implementation
```
