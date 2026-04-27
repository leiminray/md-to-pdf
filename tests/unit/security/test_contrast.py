"""Tests for security.contrast — WCAG luminance + contrast guard."""
from __future__ import annotations

import pytest

from mdpdf.errors import SecurityError
from mdpdf.security.contrast import (
    contrast_ratio,
    enforce_min_contrast,
    relative_luminance,
)

# ── relative_luminance ──────────────────────────────────────────────────────


def test_luminance_white() -> None:
    assert relative_luminance("#FFFFFF") == pytest.approx(1.0, abs=1e-6)


def test_luminance_black() -> None:
    assert relative_luminance("#000000") == pytest.approx(0.0, abs=1e-6)


def test_luminance_red() -> None:
    # R=255, G=0, B=0 → sRGB linear: 0.2126*1.0 = 0.2126
    assert relative_luminance("#FF0000") == pytest.approx(0.2126, abs=1e-4)


def test_luminance_spec_watermark_color() -> None:
    # Spec §5.2 default: light grey ~ #EBEFF0 → luminance between 0.8 and 0.9
    lum = relative_luminance("#EBEFF0")
    assert 0.80 <= lum <= 0.90


def test_luminance_lowercase_hex() -> None:
    assert relative_luminance("#ffffff") == pytest.approx(1.0, abs=1e-6)


def test_luminance_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid hex colour"):
        relative_luminance("notacolour")


# ── contrast_ratio ──────────────────────────────────────────────────────────


def test_contrast_white_black() -> None:
    assert contrast_ratio("#FFFFFF", "#000000") == pytest.approx(21.0, abs=0.01)


def test_contrast_same_color() -> None:
    assert contrast_ratio("#AABBCC", "#AABBCC") == pytest.approx(1.0, abs=1e-6)


def test_contrast_symmetric() -> None:
    r1 = contrast_ratio("#EBEFF0", "#FFFFFF")
    r2 = contrast_ratio("#FFFFFF", "#EBEFF0")
    assert r1 == pytest.approx(r2, abs=1e-6)


def test_contrast_spec_watermark_vs_white() -> None:
    # Spec §5.2 default watermark colour vs white page should be ≥ 1.05
    ratio = contrast_ratio("#EBEFF0", "#FFFFFF")
    assert ratio >= 1.05


# ── enforce_min_contrast ────────────────────────────────────────────────────


def test_enforce_passes_default_watermark() -> None:
    result = enforce_min_contrast("#EBEFF0", page_color="#FFFFFF")
    assert result == "#EBEFF0"


def test_enforce_raises_on_white_watermark() -> None:
    with pytest.raises(SecurityError) as exc_info:
        enforce_min_contrast("#FFFFFF", page_color="#FFFFFF")
    assert exc_info.value.code == "WATERMARK_CONTRAST_TOO_LOW"
    assert "1.05" in exc_info.value.user_message


def test_enforce_raises_on_near_white() -> None:
    with pytest.raises(SecurityError) as exc_info:
        enforce_min_contrast("#FEFEFE", page_color="#FFFFFF")
    assert exc_info.value.code == "WATERMARK_CONTRAST_TOO_LOW"


def test_enforce_custom_min_ratio() -> None:
    colour = "#EBEFF0"
    ratio = contrast_ratio(colour, "#FFFFFF")
    if ratio >= 1.10:
        enforce_min_contrast(colour, page_color="#FFFFFF", min_ratio=1.10)
    else:
        with pytest.raises(SecurityError):
            enforce_min_contrast(colour, page_color="#FFFFFF", min_ratio=1.10)


def test_enforce_dark_watermark_on_dark_page_raises() -> None:
    # Two near-black colours have ratio ≈ 1.20; raise min_ratio above that
    # to verify the guard fires when contrast is genuinely insufficient for
    # the threshold the brand demands.
    with pytest.raises(SecurityError):
        enforce_min_contrast("#222222", page_color="#111111", min_ratio=1.30)
