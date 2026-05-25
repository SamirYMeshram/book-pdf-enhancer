from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional

OutputMode = Literal["auto", "bilevel", "grayscale", "color"]
OcrMode = Literal["none", "ocrmypdf", "tesseract"]
PageKind = Literal["text", "text_diagram", "color", "cover", "unknown"]


@dataclass(slots=True)
class EnhancementSettings:
    profile_name: str = "Supreme Text Clarity"
    dpi: int = 600
    output_mode: OutputMode = "auto"

    # Geometry / structure
    auto_deskew: bool = True
    max_deskew_degrees: float = 7.0
    clean_borders: bool = True
    border_margin_px: int = 16

    # Restoration strengths, expected range 0..1.5
    background_strength: float = 1.0
    shadow_removal_strength: float = 1.0
    denoise_strength: float = 0.65
    sharpen_strength: float = 0.85
    contrast_strength: float = 0.85

    # Text mode
    binarize_text_pages: bool = True
    sauvola_window: int = 51
    sauvola_k: float = 0.22
    preserve_gray_for_diagrams: bool = True
    repair_broken_strokes: bool = True
    remove_speckles: bool = True
    speckle_area_px: int = 10

    # Color handling
    keep_color_pages: bool = True
    color_saturation_reduction: float = 0.25

    # PDF / OCR
    save_intermediate_pages: bool = False
    optimize_pdf: bool = True
    ocr_mode: OcrMode = "none"
    ocr_language: str = "eng"
    ocr_force: bool = True

    # Runtime
    page_limit: Optional[int] = None
    start_page: int = 1
    end_page: Optional[int] = None
    overwrite: bool = True

    def normalized(self) -> "EnhancementSettings":
        self.dpi = int(max(100, min(800, self.dpi)))
        self.background_strength = float(max(0.0, min(1.5, self.background_strength)))
        self.shadow_removal_strength = float(max(0.0, min(1.5, self.shadow_removal_strength)))
        self.denoise_strength = float(max(0.0, min(1.5, self.denoise_strength)))
        self.sharpen_strength = float(max(0.0, min(1.5, self.sharpen_strength)))
        self.contrast_strength = float(max(0.0, min(1.5, self.contrast_strength)))
        if self.sauvola_window % 2 == 0:
            self.sauvola_window += 1
        self.sauvola_window = int(max(15, min(151, self.sauvola_window)))
        self.speckle_area_px = int(max(0, min(200, self.speckle_area_px)))
        return self


@dataclass(slots=True)
class PageMetrics:
    page_number: int
    kind: PageKind = "unknown"
    colorfulness: float = 0.0
    dark_ratio: float = 0.0
    edge_density: float = 0.0
    estimated_skew_degrees: float = 0.0
    original_width_px: int = 0
    original_height_px: int = 0
    output_mode: str = "unknown"


@dataclass(slots=True)
class ProcessResult:
    input_pdf: Path
    output_pdf: Path
    searchable_pdf: Optional[Path] = None
    pages_processed: int = 0
    temp_dir: Optional[Path] = None
    page_metrics: list[PageMetrics] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


ProgressCallback = Callable[[float, str], None]
