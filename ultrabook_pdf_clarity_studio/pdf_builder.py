from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import fitz
from PIL import Image

try:
    import pikepdf
except Exception:  # pragma: no cover
    pikepdf = None


def save_page_image(image: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Always lossless. For text, PNG is preferred over JPEG.
    if image.mode not in ("1", "L", "RGB"):
        image = image.convert("RGB")
    image.save(path, format="PNG", optimize=True)
    return path


def build_pdf_from_images(image_paths: Sequence[Path], page_sizes_pt: Sequence[tuple[float, float]], output_pdf: Path) -> Path:
    """Create a PDF preserving original page sizes in points."""
    if len(image_paths) != len(page_sizes_pt):
        raise ValueError("image_paths and page_sizes_pt must have equal length")
    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()
    for img_path, (width_pt, height_pt) in zip(image_paths, page_sizes_pt):
        page = doc.new_page(width=float(width_pt), height=float(height_pt))
        rect = fitz.Rect(0, 0, float(width_pt), float(height_pt))
        page.insert_image(rect, filename=str(img_path), keep_proportion=False)
    doc.save(str(output_pdf), garbage=4, deflate=True, clean=True)
    doc.close()
    return output_pdf


def optimize_pdf_lossless(input_pdf: Path, output_pdf: Path | None = None, linearize: bool = False) -> Path:
    """Lossless metadata/object cleanup. Does not intentionally downsample images."""
    input_pdf = Path(input_pdf)
    output_pdf = Path(output_pdf) if output_pdf else input_pdf
    if pikepdf is None:
        return input_pdf
    tmp = output_pdf.with_suffix(".optimized.tmp.pdf")
    with pikepdf.open(str(input_pdf)) as pdf:
        pdf.save(str(tmp), linearize=linearize, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
    tmp.replace(output_pdf)
    return output_pdf
