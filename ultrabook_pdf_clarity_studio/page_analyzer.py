from __future__ import annotations

import cv2
import numpy as np

from .models import PageKind, PageMetrics


def _to_gray(image_rgb: np.ndarray) -> np.ndarray:
    if image_rgb.ndim == 2:
        return image_rgb
    return cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)


def colorfulness_score(image_rgb: np.ndarray) -> float:
    if image_rgb.ndim != 3 or image_rgb.shape[2] < 3:
        return 0.0
    # Hasler-Susstrunk colorfulness metric, downsampled for speed.
    small = image_rgb
    h, w = small.shape[:2]
    scale = max(1, int(max(h, w) / 1200))
    if scale > 1:
        small = small[::scale, ::scale]
    r = small[:, :, 0].astype("float32")
    g = small[:, :, 1].astype("float32")
    b = small[:, :, 2].astype("float32")
    rg = np.abs(r - g)
    yb = np.abs(0.5 * (r + g) - b)
    std_rg, std_yb = np.std(rg), np.std(yb)
    mean_rg, mean_yb = np.mean(rg), np.mean(yb)
    return float(np.sqrt(std_rg**2 + std_yb**2) + 0.3 * np.sqrt(mean_rg**2 + mean_yb**2))


def dark_ratio(gray: np.ndarray) -> float:
    small = gray
    scale = max(1, int(max(gray.shape[:2]) / 1600))
    if scale > 1:
        small = small[::scale, ::scale]
    return float(np.mean(small < 110))


def edge_density(gray: np.ndarray) -> float:
    small = gray
    scale = max(1, int(max(gray.shape[:2]) / 1600))
    if scale > 1:
        small = small[::scale, ::scale]
    edges = cv2.Canny(small, 60, 160)
    return float(np.mean(edges > 0))


def classify_page(image_rgb: np.ndarray, page_number: int = 1) -> PageMetrics:
    gray = _to_gray(image_rgb)
    cf = colorfulness_score(image_rgb)
    dr = dark_ratio(gray)
    ed = edge_density(gray)

    kind: PageKind = "text"
    if cf > 24 and dr > 0.10:
        kind = "cover"
    elif cf > 18:
        kind = "color"
    elif ed > 0.060 and dr > 0.055:
        kind = "text_diagram"
    elif dr < 0.006 and ed < 0.010:
        kind = "unknown"
    else:
        kind = "text"

    return PageMetrics(
        page_number=page_number,
        kind=kind,
        colorfulness=cf,
        dark_ratio=dr,
        edge_density=ed,
        original_width_px=int(image_rgb.shape[1]),
        original_height_px=int(image_rgb.shape[0]),
    )


def estimate_skew_degrees(gray: np.ndarray, max_degrees: float = 7.0) -> float:
    """Estimate skew for text pages. Returns 0 when confidence is low."""
    if gray.ndim == 3:
        gray = _to_gray(gray)
    h, w = gray.shape[:2]
    scale = max(1, int(max(h, w) / 2200))
    small = gray[::scale, ::scale] if scale > 1 else gray

    # Strong text mask.
    blur = cv2.GaussianBlur(small, (3, 3), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Remove giant borders/blocks a little.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    coords = np.column_stack(np.where(binary > 0))
    if coords.shape[0] < 300:
        return 0.0

    rect = cv2.minAreaRect(coords)
    angle = float(rect[-1])
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) > max_degrees:
        return 0.0
    if abs(angle) < 0.05:
        return 0.0
    return angle
