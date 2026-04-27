"""security — watermark, contrast guard, determinism, and audit."""
from mdpdf.security.contrast import (
    contrast_ratio,
    enforce_min_contrast,
    relative_luminance,
)
from mdpdf.security.watermark_l1 import apply_l1_watermark, build_watermark_page
from mdpdf.security.watermark_l2 import apply_l2_xmp

__all__ = [
    "apply_l1_watermark",
    "apply_l2_xmp",
    "build_watermark_page",
    "contrast_ratio",
    "enforce_min_contrast",
    "relative_luminance",
]
