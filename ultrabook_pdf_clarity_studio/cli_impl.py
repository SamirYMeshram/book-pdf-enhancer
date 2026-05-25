from __future__ import annotations

import argparse
from pathlib import Path

from tqdm import tqdm

from .profiles import get_profile
from .worker import process_pdf, create_preview


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="UltraBook PDF Clarity Studio CLI")
    p.add_argument("input_pdf", help="Input scanned PDF")
    p.add_argument("output_pdf", help="Output enhanced PDF")
    p.add_argument("--profile", default="supreme", choices=["supreme", "balanced", "safe_grayscale", "color_safe"])
    p.add_argument("--dpi", type=int, default=None, help="Override render DPI")
    p.add_argument("--ocr", choices=["none", "ocrmypdf", "tesseract"], default="none")
    p.add_argument("--lang", default="eng", help="OCR language, e.g. eng, hin, mar, eng+hin")
    p.add_argument("--start-page", type=int, default=1)
    p.add_argument("--end-page", type=int, default=None)
    p.add_argument("--page-limit", type=int, default=None)
    p.add_argument("--preview-page", type=int, default=None, help="Create preview images only, then exit")
    p.add_argument("--no-binarize", action="store_true")
    p.add_argument("--output-mode", choices=["auto", "bilevel", "grayscale", "color"], default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_profile(args.profile)
    if args.dpi:
        settings.dpi = args.dpi
    settings.ocr_mode = args.ocr
    settings.ocr_language = args.lang
    settings.start_page = args.start_page
    settings.end_page = args.end_page
    settings.page_limit = args.page_limit
    if args.no_binarize:
        settings.binarize_text_pages = False
    if args.output_mode:
        settings.output_mode = args.output_mode
    settings.normalized()

    if args.preview_page:
        out_dir = Path(args.output_pdf).with_suffix("").with_name(Path(args.output_pdf).stem + "_preview")
        before, after, side = create_preview(args.input_pdf, args.preview_page, settings, out_dir)
        print("Preview created:")
        print("Before:", before)
        print("After:", after)
        print("Side by side:", side)
        return 0

    bar = tqdm(total=100, unit="%")
    last = 0

    def progress(value: float, message: str):
        nonlocal last
        pct = int(value * 100)
        if pct > last:
            bar.update(pct - last)
            last = pct
        bar.set_description(message[:80])

    result = process_pdf(args.input_pdf, args.output_pdf, settings, progress=progress)
    bar.close()
    print("\nEnhanced PDF:", result.output_pdf)
    if result.searchable_pdf:
        print("Searchable OCR PDF:", result.searchable_pdf)
    if result.warnings:
        print("Warnings:")
        for w in result.warnings:
            print(" -", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
