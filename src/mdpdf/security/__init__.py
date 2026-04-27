"""security — watermark, contrast guard, determinism, and audit."""
from mdpdf.security.contrast import (
    contrast_ratio,
    enforce_min_contrast,
    relative_luminance,
)

__all__ = [
    "contrast_ratio",
    "enforce_min_contrast",
    "relative_luminance",
]
