"""security — watermark, contrast guard, determinism, and audit."""
from mdpdf.security.contrast import (
    contrast_ratio,
    enforce_min_contrast,
    relative_luminance,
)
from mdpdf.security.deterministic import (
    derive_render_id,
    freeze_pdf_dates,
    frozen_create_date,
    serialise_options,
)
from mdpdf.security.watermark_l1 import apply_l1_watermark, build_watermark_page
from mdpdf.security.watermark_l2 import apply_l2_xmp

__all__ = [
    "apply_l1_watermark",
    "apply_l2_xmp",
    "build_watermark_page",
    "contrast_ratio",
    "derive_render_id",
    "enforce_min_contrast",
    "freeze_pdf_dates",
    "frozen_create_date",
    "relative_luminance",
    "serialise_options",
]
