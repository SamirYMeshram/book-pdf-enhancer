from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import fitz  # PyMuPDF
import numpy as np


@dataclass(slots=True)
class RenderedPage:
    page_number: int
    image_rgb: np.ndarray
    width_pt: float
    height_pt: float


class PdfRenderer:
    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(self.pdf_path)
        self.doc = fitz.open(str(self.pdf_path))

    def __enter__(self) -> "PdfRenderer":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @property
    def page_count(self) -> int:
        return len(self.doc)

    def close(self) -> None:
        if getattr(self, "doc", None) is not None:
            self.doc.close()

    def render_page(self, page_index: int, dpi: int) -> RenderedPage:
        page = self.doc[page_index]
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            arr = arr[:, :, :3]
        elif pix.n == 1:
            arr = np.repeat(arr[:, :, None], 3, axis=2)
        return RenderedPage(
            page_number=page_index + 1,
            image_rgb=arr.copy(),
            width_pt=float(page.rect.width),
            height_pt=float(page.rect.height),
        )

    def iter_pages(self, dpi: int, start_page: int = 1, end_page: int | None = None) -> Iterator[RenderedPage]:
        start = max(1, start_page)
        end = self.page_count if end_page is None else min(end_page, self.page_count)
        for page_num in range(start, end + 1):
            yield self.render_page(page_num - 1, dpi)
