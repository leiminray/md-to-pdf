"""L1 visible diagonal watermark overlay.

Strategy:
    1. Build a watermark PDF page (same dimensions as the target page) using
       ReportLab's canvas, tiling rotated text at 38° across the page.
    2. Use pypdf to merge this watermark page *under* existing content on every
       page of the target PDF, then write the result back atomically.

The watermark is intentionally subtle: 13pt light-grey text, 38° rotation,
120pt row spacing.  Brand packs may override the colour subject to the
minimum-contrast guard in ``security.contrast``.
"""
from __future__ import annotations

import contextlib
import io
import math
import os
import tempfile
from pathlib import Path

import pypdf
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

from mdpdf.fonts.manager import FontManager, cjk_chars_present
from mdpdf.security.contrast import enforce_min_contrast

_BUNDLED_FONTS_DIR = Path(__file__).resolve().parents[3] / "fonts"


def _select_watermark_font(text: str) -> str:
    """Return a font name that has glyphs for *text*. Falls back to a
    CJK-capable font if non-ASCII (CJK / fullwidth punctuation / emoji)
    is present.
    """
    if not cjk_chars_present(text):
        return "Helvetica"
    fm = FontManager(bundled_dir=_BUNDLED_FONTS_DIR)
    import contextlib
    with contextlib.suppress(Exception):
        fm.register_for_text(text)
    registered = pdfmetrics.getRegisteredFontNames()
    for cand in ("NotoSansSC-Regular", "NotoSansCJK-Regular", "PingFang"):
        if cand in registered:
            return cand
    return "Helvetica"

# Spec §5.2 defaults
_DEFAULT_COLOR = "#EBEFF0"
_FONT_SIZE_PT = 13
_ROTATION_DEG = 38
_ROW_SPACING_PT = 120
_DEFAULT_TEMPLATE = "{brand_name} // {user} // {render_date}"


def _hex_to_rgb_floats(hex_color: str) -> tuple[float, float, float]:
    s = hex_color.lstrip("#")
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return r, g, b


def build_watermark_page(
    *,
    width_pt: float,
    height_pt: float,
    text: str,
    color: str = _DEFAULT_COLOR,
    font_size: float = _FONT_SIZE_PT,
    rotation_deg: float = _ROTATION_DEG,
    row_spacing_pt: float = _ROW_SPACING_PT,
) -> bytes:
    """Return a PDF page (as bytes) containing the tiled diagonal watermark.

    The contrast guard is applied here so any call site (including brand
    override paths) is automatically protected.

    Raises:
        SecurityError: code WATERMARK_CONTRAST_TOO_LOW if *color* fails the
            contrast guard against a white page background.
        ValueError: if *color* is not a valid 6-digit hex string.
    """
    enforce_min_contrast(color, page_color="#FFFFFF")

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(width_pt, height_pt))

    r, g, b = _hex_to_rgb_floats(color)
    c.setFillColorRGB(r, g, b)
    font_name = _select_watermark_font(text)
    c.setFont(font_name, font_size)

    diagonal = math.hypot(width_pt, height_pt)
    approx_char_width = font_size * 0.55
    col_spacing = max(len(text) * approx_char_width + 20, row_spacing_pt)

    n_rows = int(diagonal / row_spacing_pt) + 3
    n_cols = int(diagonal / col_spacing) + 3

    for row in range(-n_rows, n_rows):
        for col in range(-n_cols, n_cols):
            x = col * col_spacing - n_cols * col_spacing / 2 + width_pt / 2
            y = row * row_spacing_pt + height_pt / 2

            c.saveState()
            c.translate(x, y)
            c.rotate(rotation_deg)
            c.drawString(0, 0, text)
            c.restoreState()

    c.save()
    return buf.getvalue()


def apply_l1_watermark(
    pdf_path: Path,
    *,
    brand_name: str,
    user: str,
    render_date: str,
    color: str = _DEFAULT_COLOR,
    template: str = _DEFAULT_TEMPLATE,
    font_size: float = _FONT_SIZE_PT,
    rotation_deg: float = _ROTATION_DEG,
    row_spacing_pt: float = _ROW_SPACING_PT,
) -> None:
    """Apply an L1 visible diagonal watermark to every page of *pdf_path* in-place.

    Updated atomically: written to a temp file in the same directory, then
    renamed over the original.
    """
    watermark_text = template.format_map(
        {"brand_name": brand_name, "user": user, "render_date": render_date}
    )

    reader = pypdf.PdfReader(str(pdf_path))
    # Preserve outlines via clone_from; merge the watermark on top of the
    # cloned pages instead of building a fresh writer that loses metadata.
    writer = pypdf.PdfWriter(clone_from=reader)

    for page in writer.pages:
        media_box = page.mediabox
        width_pt = float(media_box.width)
        height_pt = float(media_box.height)

        wm_bytes = build_watermark_page(
            width_pt=width_pt,
            height_pt=height_pt,
            text=watermark_text,
            color=color,
            font_size=font_size,
            rotation_deg=rotation_deg,
            row_spacing_pt=row_spacing_pt,
        )

        wm_reader = pypdf.PdfReader(io.BytesIO(wm_bytes))
        # over=False places the watermark *under* the existing page content
        # so body text remains readable on top of the diagonal stamp.
        page.merge_page(wm_reader.pages[0], over=False)

    dir_path = pdf_path.parent
    fd, tmp_path_str = tempfile.mkstemp(
        dir=dir_path, prefix=pdf_path.name + ".wm.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as f:
            writer.write(f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path_str, pdf_path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path_str)
        raise
