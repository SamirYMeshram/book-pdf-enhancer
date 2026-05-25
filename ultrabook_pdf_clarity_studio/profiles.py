from __future__ import annotations

from .models import EnhancementSettings


def supreme() -> EnhancementSettings:
    """Slowest, strongest profile for black-text scanned book pages."""
    return EnhancementSettings(
        profile_name="Supreme Text Clarity - 600 DPI",
        dpi=600,
        output_mode="auto",
        auto_deskew=True,
        clean_borders=True,
        background_strength=1.0,
        shadow_removal_strength=1.0,
        denoise_strength=0.70,
        sharpen_strength=0.95,
        contrast_strength=0.95,
        binarize_text_pages=True,
        sauvola_window=61,
        sauvola_k=0.20,
        preserve_gray_for_diagrams=True,
        repair_broken_strokes=True,
        remove_speckles=True,
        speckle_area_px=14,
        keep_color_pages=True,
        color_saturation_reduction=0.25,
    )


def safe_grayscale() -> EnhancementSettings:
    """Safer mode for thin/faint letters, tables, and diagrams."""
    return EnhancementSettings(
        profile_name="Safe Grayscale Book - 400 DPI",
        dpi=400,
        output_mode="grayscale",
        auto_deskew=True,
        clean_borders=True,
        background_strength=0.85,
        shadow_removal_strength=0.85,
        denoise_strength=0.45,
        sharpen_strength=0.65,
        contrast_strength=0.75,
        binarize_text_pages=False,
        preserve_gray_for_diagrams=True,
        repair_broken_strokes=False,
        remove_speckles=True,
        speckle_area_px=8,
        keep_color_pages=False,
    )


def color_safe() -> EnhancementSettings:
    """Preserves color diagrams/covers while cleaning background."""
    return EnhancementSettings(
        profile_name="Color Diagram Safe - 400 DPI",
        dpi=400,
        output_mode="color",
        auto_deskew=True,
        clean_borders=True,
        background_strength=0.65,
        shadow_removal_strength=0.75,
        denoise_strength=0.35,
        sharpen_strength=0.55,
        contrast_strength=0.55,
        binarize_text_pages=False,
        preserve_gray_for_diagrams=True,
        repair_broken_strokes=False,
        remove_speckles=False,
        keep_color_pages=True,
        color_saturation_reduction=0.10,
    )


def balanced() -> EnhancementSettings:
    return EnhancementSettings(
        profile_name="Balanced Clean Book - 400 DPI",
        dpi=400,
        output_mode="auto",
        auto_deskew=True,
        clean_borders=True,
        background_strength=0.85,
        shadow_removal_strength=0.85,
        denoise_strength=0.55,
        sharpen_strength=0.75,
        contrast_strength=0.80,
        binarize_text_pages=True,
        sauvola_window=51,
        sauvola_k=0.22,
        preserve_gray_for_diagrams=True,
        repair_broken_strokes=True,
        remove_speckles=True,
        speckle_area_px=10,
    )


PROFILES = {
    "supreme": supreme,
    "balanced": balanced,
    "safe_grayscale": safe_grayscale,
    "color_safe": color_safe,
}

PROFILE_LABELS = {
    "Supreme Text Clarity - 600 DPI": "supreme",
    "Balanced Clean Book - 400 DPI": "balanced",
    "Safe Grayscale Book - 400 DPI": "safe_grayscale",
    "Color Diagram Safe - 400 DPI": "color_safe",
}


def get_profile(name: str) -> EnhancementSettings:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    if name in PROFILE_LABELS:
        key = PROFILE_LABELS[name]
    if key not in PROFILES:
        valid = ", ".join(PROFILES)
        raise ValueError(f"Unknown profile '{name}'. Valid profiles: {valid}")
    return PROFILES[key]().normalized()
