"""Footer overlay: confidential text + page N/M stamped on every page.

Uses ReportLab to build per-page overlay canvases, then pypdf to merge them
onto the source PDF. Writes the result back atomically (tempfile + fsync +
os.replace) so a crash during pypdf.write cannot truncate the original.
"""
from __future__ import annotations

import contextlib
import io
import os
import tempfile
from pathlib import Path

import pypdf
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

from mdpdf.fonts.manager import FontManager, cjk_chars_present
from mdpdf.i18n.strings import lookup

_BUNDLED_FONTS_DIR = Path(__file__).resolve().parents[3] / "fonts"


def _hex_to_color(hex_color: str) -> colors.Color:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return colors.Color(r / 255.0, g / 255.0, b / 255.0)


def _build_overlay(
    page_width: float,
    page_height: float,
    *,
    left_text: str,
    right_text: str,
    left_margin_pt: float,
    bottom_margin_pt: float,
    font_name: str,
    font_size: int,
    color: colors.Color,
) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_width, page_height))
    c.setFont(font_name, font_size)
    c.setFillColor(color)
    y = bottom_margin_pt
    c.drawString(left_margin_pt, y, left_text)
    right_width = c.stringWidth(right_text, font_name, font_size)
    c.drawString(page_width - left_margin_pt - right_width, y, right_text)
    c.save()
    buf.seek(0)
    return buf.read()


def apply_footer(
    pdf_path: Path,
    *,
    brand_name: str,
    confidential_text: str,
    locale: str = "en",
    left_margin_mm: float = 18,
    bottom_margin_mm: float = 8,
    font_name: str = "Helvetica",
    font_size: int = 8,
    color: str = "#6B7280",
) -> None:
    """Overlay a footer on every page of *pdf_path*, modifying the file in-place.

    If the rendered footer text contains CJK characters, switches *font_name*
    to a CJK-capable font (registered on demand via FontManager). Falls back
    to the supplied *font_name* if no CJK font is available — the caller is
    expected to handle the resulting tofu in that case.
    """
    left_pt = left_margin_mm * mm
    bottom_pt = bottom_margin_mm * mm
    fill = _hex_to_color(color)
    page_fmt = lookup(locale, "footer.page_format")

    sample_text = f"{confidential_text} {brand_name} {page_fmt}"
    if cjk_chars_present(sample_text):
        fm = FontManager(bundled_dir=_BUNDLED_FONTS_DIR)
        with contextlib.suppress(Exception):
            fm.register_for_text(sample_text)
        for cand in ("NotoSansSC-Regular", "NotoSansCJK-Regular", "PingFang"):
            if cand in pdfmetrics.getRegisteredFontNames():
                font_name = cand
                break

    reader = pypdf.PdfReader(str(pdf_path))
    # clone_from preserves outlines, named destinations, and metadata that
    # plain `add_page` would drop (Plan 3's PDF outline must survive
    # post-process).
    writer = pypdf.PdfWriter(clone_from=reader)
    total = len(writer.pages)

    for i, page in enumerate(writer.pages):
        media = page.mediabox
        pw = float(media.width)
        ph = float(media.height)

        left_text = f"{confidential_text} — {brand_name}"
        right_text = page_fmt.format(n=i + 1, total=total)

        overlay_bytes = _build_overlay(
            pw, ph,
            left_text=left_text,
            right_text=right_text,
            left_margin_pt=left_pt,
            bottom_margin_pt=bottom_pt,
            font_name=font_name,
            font_size=font_size,
            color=fill,
        )
        overlay_reader = pypdf.PdfReader(io.BytesIO(overlay_bytes))
        page.merge_page(overlay_reader.pages[0])

    # Atomic write: tempfile + fsync + rename in same dir (P4-012).
    dir_path = pdf_path.parent
    fd, tmp_path_str = tempfile.mkstemp(
        dir=dir_path, prefix=pdf_path.name + ".footer.", suffix=".tmp"
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
