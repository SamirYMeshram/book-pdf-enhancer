from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Sequence

import fitz


def executable_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_ocrmypdf(input_pdf: Path, output_pdf: Path, language: str = "eng", force: bool = True) -> Path:
    if not executable_exists("ocrmypdf"):
        raise RuntimeError("ocrmypdf executable not found. Install OCRmyPDF or choose OCR mode: none.")
    cmd = [
        "ocrmypdf",
        "--output-type", "pdf",
        "--optimize", "0",
        "--language", language,
        "--jobs", "1",
    ]
    if force:
        cmd.append("--force-ocr")
    else:
        cmd.append("--skip-text")
    # We already clean/deskew visually; let OCRmyPDF only add OCR layer.
    cmd += [str(input_pdf), str(output_pdf)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode not in (0, 6):  # 6 can mean already has text in some workflows
        raise RuntimeError("OCRmyPDF failed:\n" + result.stdout[-4000:])
    return output_pdf


def run_tesseract_page_pdfs(image_paths: Sequence[Path], output_pdf: Path, language: str = "eng") -> Path:
    if not executable_exists("tesseract"):
        raise RuntimeError("tesseract executable not found. Install Tesseract or choose OCR mode: none.")
    output_pdf = Path(output_pdf)
    temp_dir = output_pdf.parent / (output_pdf.stem + "_tesseract_pages")
    temp_dir.mkdir(parents=True, exist_ok=True)
    page_pdfs: list[Path] = []

    for idx, img in enumerate(image_paths, start=1):
        base = temp_dir / f"page_{idx:05d}"
        cmd = ["tesseract", str(img), str(base), "-l", language, "pdf"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Tesseract failed on page {idx}:\n{result.stdout[-2000:]}")
        page_pdfs.append(base.with_suffix(".pdf"))

    merged = fitz.open()
    for pdf_path in page_pdfs:
        src = fitz.open(str(pdf_path))
        merged.insert_pdf(src)
        src.close()
    merged.save(str(output_pdf), garbage=4, deflate=True)
    merged.close()
    return output_pdf
