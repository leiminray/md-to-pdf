"""WCAG 2.1 relative luminance and contrast ratio utilities.

Used by the watermark layer to enforce the minimum-contrast guard.
"""
from __future__ import annotations

from mdpdf.errors import SecurityError


def _srgb_to_linear(channel: float) -> float:
    """Convert a normalised sRGB channel value [0,1] to linear light."""
    if channel <= 0.04045:
        return channel / 12.92
    return float(((channel + 0.055) / 1.055) ** 2.4)


def _parse_hex(hex_color: str) -> tuple[float, float, float]:
    """Parse a 6-digit hex colour (with or without leading #) to normalised RGB floats."""
    s = hex_color.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Invalid hex colour: {hex_color!r} (expected 6-digit hex)")
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
    except ValueError as exc:
        raise ValueError(f"Invalid hex colour: {hex_color!r}") from exc
    return r, g, b


def relative_luminance(hex_color: str) -> float:
    """Return the WCAG 2.1 relative luminance of a hex colour.

    Result is in [0.0, 1.0]: 0.0 = absolute black, 1.0 = absolute white.

    Raises:
        ValueError: if *hex_color* is not a valid 6-digit hex string.
    """
    r, g, b = _parse_hex(hex_color)
    rl = _srgb_to_linear(r)
    gl = _srgb_to_linear(g)
    bl = _srgb_to_linear(b)
    return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl


def contrast_ratio(c1: str, c2: str) -> float:
    """Return the WCAG 2.1 contrast ratio between two hex colours.

    Result is in [1.0, 21.0]: 1.0 = no contrast, 21.0 = black on white.
    The function is symmetric: ``contrast_ratio(a, b) == contrast_ratio(b, a)``.
    """
    l1 = relative_luminance(c1)
    l2 = relative_luminance(c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def enforce_min_contrast(
    watermark_color: str,
    page_color: str = "#FFFFFF",
    min_ratio: float = 1.05,
) -> str:
    """Return *watermark_color* if contrast is sufficient; raise otherwise.

    The minimum ratio of 1.05 ensures the watermark is perceptible against the
    page background while remaining unobtrusive ("visible-yet-subtle"
    requirement). Brand packs may override the watermark colour subject to this
    guard — the guard is not bypassed even by override.

    Raises:
        SecurityError: code ``WATERMARK_CONTRAST_TOO_LOW`` if the ratio is below
            *min_ratio*.
    """
    ratio = contrast_ratio(watermark_color, page_color)
    if ratio < min_ratio:
        raise SecurityError(
            code="WATERMARK_CONTRAST_TOO_LOW",
            user_message=(
                f"Watermark colour {watermark_color!r} has contrast ratio "
                f"{ratio:.3f} against page background {page_color!r}, "
                f"below the minimum {min_ratio}. "
                "Choose a darker or lighter watermark colour."
            ),
            technical_details=(
                f"WCAG relative luminance: watermark={relative_luminance(watermark_color):.4f}, "
                f"page={relative_luminance(page_color):.4f}, ratio={ratio:.4f}"
            ),
        )
    return watermark_color
