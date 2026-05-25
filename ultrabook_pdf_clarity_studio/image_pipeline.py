from __future__ import annotations

from dataclasses import replace
from typing import Tuple

import cv2
import numpy as np
from PIL import Image

try:
    from skimage.filters import threshold_sauvola
except Exception:  # pragma: no cover - optional fallback
    threshold_sauvola = None

from .models import EnhancementSettings, PageMetrics
from .page_analyzer import classify_page, estimate_skew_degrees


def _odd(n: int) -> int:
    n = int(n)
    return n if n % 2 else n + 1


def _clip_uint8(a: np.ndarray) -> np.ndarray:
    return np.clip(a, 0, 255).astype(np.uint8)


def rgb_to_gray(image_rgb: np.ndarray) -> np.ndarray:
    if image_rgb.ndim == 2:
        return image_rgb
    return cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)


def rotate_bound_white(image: np.ndarray, angle: float) -> np.ndarray:
    if abs(angle) < 0.05:
        return image
    h, w = image.shape[:2]
    center = (w / 2, h / 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    border_value = 255 if image.ndim == 2 else (255, 255, 255)
    return cv2.warpAffine(image, M, (new_w, new_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=border_value)


def clean_outer_borders(gray_or_rgb: np.ndarray, margin_px: int = 16) -> np.ndarray:
    """White out obvious scanner borders while preserving the page content."""
    image = gray_or_rgb.copy()
    gray = rgb_to_gray(image)
    h, w = gray.shape[:2]
    if h < 40 or w < 40:
        return image

    # Find non-background content. Use a lenient threshold to catch grey/yellow borders.
    bg = cv2.GaussianBlur(gray, (_odd(max(31, min(h, w) // 25)), _odd(max(31, min(h, w) // 25))), 0)
    diff = cv2.absdiff(gray, bg)
    content = ((gray < 238) | (diff > 18)).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    content = cv2.morphologyEx(content, cv2.MORPH_CLOSE, kernel)
    coords = cv2.findNonZero(content)
    if coords is None:
        return image
    x, y, bw, bh = cv2.boundingRect(coords)

    # Do not crop too aggressively. Only clear outside a padded content box.
    pad = max(8, margin_px)
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(w, x + bw + pad)
    y1 = min(h, y + bh + pad)

    if x0 > 0:
        image[:, :x0] = 255
    if y0 > 0:
        image[:y0, :] = 255
    if x1 < w:
        image[:, x1:] = 255
    if y1 < h:
        image[y1:, :] = 255
    return image


def flatten_background_gray(gray: np.ndarray, strength: float = 1.0, shadow_strength: float = 1.0) -> np.ndarray:
    gray = gray.astype(np.uint8)
    h, w = gray.shape[:2]
    k = _odd(max(31, int(min(h, w) * 0.035)))
    k = min(k, 251)
    # Median is good for dirty scanned paper but expensive; use morphological + Gaussian mix.
    background = cv2.medianBlur(gray, k if k <= 151 else 151)
    background = cv2.GaussianBlur(background, (_odd(min(251, k)), _odd(min(251, k))), 0)

    # Divide normalization removes uneven illumination.
    normalized = (gray.astype(np.float32) / (background.astype(np.float32) + 1.0)) * 245.0
    normalized = _clip_uint8(normalized)

    # Push background toward white without crushing dark text.
    if shadow_strength > 0:
        white = cv2.normalize(normalized, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
        normalized = cv2.addWeighted(normalized, 1.0 - 0.35 * shadow_strength, white, 0.35 * shadow_strength, 0)

    out = cv2.addWeighted(gray, max(0.0, 1.0 - strength), normalized, min(1.0, strength), 0)
    return _clip_uint8(out)


def flatten_background_color(image_rgb: np.ndarray, strength: float = 0.7, shadow_strength: float = 0.8, sat_reduce: float = 0.15) -> np.ndarray:
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(hsv)
    v2 = flatten_background_gray(v, strength=strength, shadow_strength=shadow_strength)
    if sat_reduce > 0:
        s = _clip_uint8(s.astype(np.float32) * (1.0 - min(0.8, sat_reduce)))
    merged = cv2.merge([h, s, v2])
    out = cv2.cvtColor(merged, cv2.COLOR_HSV2RGB)
    return out


def denoise_gray(gray: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return gray
    h = int(3 + 12 * min(strength, 1.5))
    return cv2.fastNlMeansDenoising(gray, None, h=h, templateWindowSize=7, searchWindowSize=21)


def denoise_color(image_rgb: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return image_rgb
    h = int(2 + 8 * min(strength, 1.5))
    return cv2.fastNlMeansDenoisingColored(image_rgb, None, h=h, hColor=max(2, h // 2), templateWindowSize=7, searchWindowSize=21)


def clahe_gray(gray: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return gray
    clip = 1.0 + 2.5 * min(strength, 1.5)
    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
    return clahe.apply(gray)


def unsharp_gray(gray: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return gray
    sigma = 1.0
    blur = cv2.GaussianBlur(gray, (0, 0), sigma)
    amount = 0.55 + 0.75 * min(strength, 1.5)
    out = cv2.addWeighted(gray, 1.0 + amount, blur, -amount, 0)
    return _clip_uint8(out)


def unsharp_color(image_rgb: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return image_rgb
    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l = unsharp_gray(l, strength)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)


def sauvola_binarize(gray: np.ndarray, window: int = 51, k: float = 0.22) -> np.ndarray:
    window = _odd(window)
    if threshold_sauvola is not None:
        thresh = threshold_sauvola(gray, window_size=window, k=k)
        binary = (gray > thresh).astype(np.uint8) * 255
        return binary
    # Fallback: OpenCV adaptive Gaussian threshold.
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, window, 10)


def remove_black_speckles(binary_white_bg: np.ndarray, max_area: int = 10) -> np.ndarray:
    if max_area <= 0:
        return binary_white_bg
    # binary has black text on white background. Work with black components.
    inv = (binary_white_bg < 128).astype(np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    cleaned = binary_white_bg.copy()
    for label in range(1, num):
        x, y, w, h, area = stats[label]
        # Remove only tiny compact dots. Keep punctuation by being conservative.
        if area <= max_area and w <= 6 and h <= 6:
            cleaned[labels == label] = 255
    return cleaned


def repair_text_strokes(binary_white_bg: np.ndarray) -> np.ndarray:
    inv = (binary_white_bg < 128).astype(np.uint8) * 255
    # Close tiny gaps horizontally/vertically without making letters too fat.
    k1 = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
    k2 = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 2))
    inv = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, k1, iterations=1)
    inv = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, k2, iterations=1)
    return np.where(inv > 0, 0, 255).astype(np.uint8)


def choose_processing_mode(metrics: PageMetrics, settings: EnhancementSettings) -> str:
    if settings.output_mode != "auto":
        return settings.output_mode
    if metrics.kind in {"cover", "color"} and settings.keep_color_pages:
        return "color"
    if metrics.kind == "text_diagram" and settings.preserve_gray_for_diagrams:
        return "grayscale"
    if settings.binarize_text_pages and metrics.kind == "text":
        return "bilevel"
    return "grayscale"


def enhance_page(image_rgb: np.ndarray, settings: EnhancementSettings, page_number: int = 1) -> Tuple[Image.Image, PageMetrics]:
    """Enhance one rendered page and return a PIL image suitable for PDF embedding."""
    settings = settings.normalized()
    metrics = classify_page(image_rgb, page_number=page_number)

    work = image_rgb.copy()
    gray_initial = rgb_to_gray(work)
    angle = estimate_skew_degrees(gray_initial, max_degrees=settings.max_deskew_degrees) if settings.auto_deskew else 0.0
    metrics.estimated_skew_degrees = angle
    if settings.auto_deskew and abs(angle) > 0.05:
        work = rotate_bound_white(work, angle)

    if settings.clean_borders:
        work = clean_outer_borders(work, settings.border_margin_px)

    mode = choose_processing_mode(metrics, settings)
    metrics.output_mode = mode

    if mode == "color":
        out = flatten_background_color(
            work,
            strength=min(1.0, settings.background_strength),
            shadow_strength=min(1.0, settings.shadow_removal_strength),
            sat_reduce=settings.color_saturation_reduction,
        )
        out = denoise_color(out, settings.denoise_strength * 0.7)
        out = unsharp_color(out, settings.sharpen_strength * 0.75)
        return Image.fromarray(out, mode="RGB"), metrics

    gray = rgb_to_gray(work)
    gray = flatten_background_gray(gray, settings.background_strength, settings.shadow_removal_strength)
    gray = denoise_gray(gray, settings.denoise_strength)
    gray = clahe_gray(gray, settings.contrast_strength)
    gray = unsharp_gray(gray, settings.sharpen_strength)

    if mode == "bilevel":
        binary = sauvola_binarize(gray, window=settings.sauvola_window, k=settings.sauvola_k)
        if settings.repair_broken_strokes:
            binary = repair_text_strokes(binary)
        if settings.remove_speckles:
            binary = remove_black_speckles(binary, settings.speckle_area_px)
        # PIL mode 1 saves compact 1-bit PNG. Use L if mode 1 causes compatibility issue; PyMuPDF handles both.
        return Image.fromarray(binary, mode="L"), metrics

    if settings.remove_speckles:
        # Soft speckle clean on grayscale: identify tiny black dots and whiten them.
        temp_bin = sauvola_binarize(gray, window=max(31, settings.sauvola_window), k=settings.sauvola_k)
        clean_bin = remove_black_speckles(temp_bin, max(3, settings.speckle_area_px // 2))
        speckles = (temp_bin < 128) & (clean_bin > 128)
        gray[speckles] = 255
    return Image.fromarray(gray, mode="L"), metrics


def make_side_by_side_preview(before_rgb: np.ndarray, after_image: Image.Image, max_width: int = 1600) -> Image.Image:
    before = Image.fromarray(before_rgb).convert("RGB")
    after = after_image.convert("RGB")
    # Normalize heights for comparison.
    h = min(before.height, after.height)
    before = before.resize((int(before.width * h / before.height), h), Image.LANCZOS)
    after = after.resize((int(after.width * h / after.height), h), Image.LANCZOS)
    combined = Image.new("RGB", (before.width + after.width, h), "white")
    combined.paste(before, (0, 0))
    combined.paste(after, (before.width, 0))
    if combined.width > max_width:
        nh = int(combined.height * max_width / combined.width)
        combined = combined.resize((max_width, nh), Image.LANCZOS)
    return combined
