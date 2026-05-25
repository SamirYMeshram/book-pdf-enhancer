from __future__ import annotations

from pathlib import Path
import tempfile
import time

from PIL import Image

from .models import EnhancementSettings, ProcessResult, ProgressCallback
from .renderer import PdfRenderer
from .image_pipeline import enhance_page, make_side_by_side_preview
from .pdf_builder import build_pdf_from_images, optimize_pdf_lossless, save_page_image
from .ocr import run_ocrmypdf, run_tesseract_page_pdfs


def _progress(callback: ProgressCallback | None, value: float, message: str) -> None:
    if callback:
        callback(max(0.0, min(1.0, value)), message)


def process_pdf(input_pdf: str | Path, output_pdf: str | Path, settings: EnhancementSettings, progress: ProgressCallback | None = None) -> ProcessResult:
    settings = settings.normalized()
    input_pdf = Path(input_pdf)
    output_pdf = Path(output_pdf)
    if not input_pdf.exists():
        raise FileNotFoundError(input_pdf)
    if output_pdf.exists() and not settings.overwrite:
        raise FileExistsError(output_pdf)

    start_time = time.time()
    warnings: list[str] = []
    page_metrics = []

    temp_parent = Path(tempfile.mkdtemp(prefix="ultrabook_pdf_"))
    pages_dir = temp_parent / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    image_paths: list[Path] = []
    page_sizes: list[tuple[float, float]] = []

    _progress(progress, 0.01, "Opening PDF...")
    with PdfRenderer(input_pdf) as renderer:
        total_all = renderer.page_count
        start_page = max(1, settings.start_page)
        end_page = settings.end_page or total_all
        end_page = min(end_page, total_all)
        if settings.page_limit:
            end_page = min(end_page, start_page + settings.page_limit - 1)
        total = max(0, end_page - start_page + 1)
        if total <= 0:
            raise ValueError("No pages selected for processing.")

        for i, rendered in enumerate(renderer.iter_pages(settings.dpi, start_page=start_page, end_page=end_page), start=1):
            base_progress = 0.02 + (i - 1) / total * 0.82
            _progress(progress, base_progress, f"Rendering/enhancing page {rendered.page_number}/{total_all} at {settings.dpi} DPI...")
            enhanced, metrics = enhance_page(rendered.image_rgb, settings, page_number=rendered.page_number)
            page_metrics.append(metrics)
            img_path = pages_dir / f"page_{i:05d}.png"
            save_page_image(enhanced, img_path)
            image_paths.append(img_path)
            page_sizes.append((rendered.width_pt, rendered.height_pt))

    _progress(progress, 0.86, "Building enhanced PDF...")
    build_pdf_from_images(image_paths, page_sizes, output_pdf)

    if settings.optimize_pdf:
        _progress(progress, 0.90, "Optimizing PDF structure losslessly...")
        try:
            optimize_pdf_lossless(output_pdf, output_pdf)
        except Exception as exc:
            warnings.append(f"Lossless pikepdf optimization skipped: {exc}")

    searchable_pdf = None
    if settings.ocr_mode == "ocrmypdf":
        searchable_pdf = output_pdf.with_name(output_pdf.stem + "_searchable.pdf")
        _progress(progress, 0.93, "Adding OCR text layer with OCRmyPDF...")
        run_ocrmypdf(output_pdf, searchable_pdf, language=settings.ocr_language, force=settings.ocr_force)
    elif settings.ocr_mode == "tesseract":
        searchable_pdf = output_pdf.with_name(output_pdf.stem + "_tesseract_searchable.pdf")
        _progress(progress, 0.93, "Adding OCR text layer with Tesseract...")
        run_tesseract_page_pdfs(image_paths, searchable_pdf, language=settings.ocr_language)

    elapsed = time.time() - start_time
    _progress(progress, 1.0, f"Done in {elapsed:.1f}s. Output: {output_pdf}")

    return ProcessResult(
        input_pdf=input_pdf,
        output_pdf=output_pdf,
        searchable_pdf=searchable_pdf,
        pages_processed=len(image_paths),
        temp_dir=temp_parent if settings.save_intermediate_pages else None,
        page_metrics=page_metrics,
        warnings=warnings,
    )


def create_preview(input_pdf: str | Path, page_number: int, settings: EnhancementSettings, output_dir: str | Path) -> tuple[Path, Path, Path]:
    settings = settings.normalized()
    # Preview renders lower DPI to keep UI responsive but still representative.
    preview_dpi = min(settings.dpi, 300)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with PdfRenderer(input_pdf) as renderer:
        page_number = max(1, min(page_number, renderer.page_count))
        rendered = renderer.render_page(page_number - 1, preview_dpi)
        enhanced, metrics = enhance_page(rendered.image_rgb, settings, page_number=page_number)
    before_path = output_dir / f"preview_page_{page_number:04d}_before.png"
    after_path = output_dir / f"preview_page_{page_number:04d}_after.png"
    side_path = output_dir / f"preview_page_{page_number:04d}_side_by_side.png"
    Image.fromarray(rendered.image_rgb).save(before_path)
    enhanced.save(after_path)
    make_side_by_side_preview(rendered.image_rgb, enhanced).save(side_path)
    return before_path, after_path, side_path
