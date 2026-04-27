"""Issuer card overlay: rendered on the last page only.

Ports the v1.8.9 layout from ``scripts/md_to_pdf.py``:
- Left-edge colour border strip
- Card background rectangle
- Issuer name (bold, title colour)
- Issuer lines (body colour, smaller font)

Writes back atomically (tempfile + fsync + rename) per pass-2 P4-016.
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
from reportlab.pdfgen import canvas as rl_canvas


def _hex_to_color(hex_color: str) -> colors.Color:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return colors.Color(r / 255.0, g / 255.0, b / 255.0)


def _build_card_overlay(
    page_width: float,
    page_height: float,
    *,
    issuer_name: str,
    issuer_lines: list[str],
    card_bg: colors.Color,
    card_border: colors.Color,
    title_color: colors.Color,
    body_color: colors.Color,
    title_pt: int,
    body_pt: int,
    position: tuple[float, float],
) -> bytes:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_width, page_height))

    x_pt, y_pt = position[0] * mm, position[1] * mm
    card_w = 160 * mm
    line_height = body_pt * 1.4
    card_h = title_pt * 1.8 + len(issuer_lines) * line_height + 8

    c.setFillColor(card_bg)
    c.rect(x_pt, y_pt, card_w, card_h, stroke=0, fill=1)

    border_w = 3 * mm
    c.setFillColor(card_border)
    c.rect(x_pt, y_pt, border_w, card_h, stroke=0, fill=1)

    c.setFillColor(title_color)
    c.setFont("Helvetica-Bold", title_pt)
    text_x = x_pt + border_w + 4 * mm
    text_y = y_pt + card_h - title_pt * 1.4
    c.drawString(text_x, text_y, issuer_name)

    c.setFont("Helvetica", body_pt)
    c.setFillColor(body_color)
    for line in issuer_lines:
        text_y -= line_height
        c.drawString(text_x, text_y, line)

    c.save()
    buf.seek(0)
    return buf.read()


def apply_issuer_card(
    pdf_path: Path,
    *,
    issuer_name: str,
    issuer_lines: list[str],
    card_bg_hex: str = "#F8FAFC",
    card_border_hex: str = "#DBE3EA",
    title_color_hex: str = "#374151",
    body_color_hex: str = "#6B7280",
    title_pt: int = 9,
    body_pt: int = 8,
    position: tuple[float, float] = (18, 18),
) -> None:
    """Overlay the issuer card on the last page of *pdf_path* (in-place, atomically)."""
    reader = pypdf.PdfReader(str(pdf_path))
    # Preserve outlines / named destinations from the source PDF.
    writer = pypdf.PdfWriter(clone_from=reader)
    total = len(writer.pages)

    card_bg = _hex_to_color(card_bg_hex)
    card_border = _hex_to_color(card_border_hex)
    title_color = _hex_to_color(title_color_hex)
    body_color = _hex_to_color(body_color_hex)

    last = writer.pages[total - 1]
    media = last.mediabox
    pw = float(media.width)
    ph = float(media.height)
    overlay_bytes = _build_card_overlay(
        pw, ph,
        issuer_name=issuer_name,
        issuer_lines=issuer_lines,
        card_bg=card_bg,
        card_border=card_border,
        title_color=title_color,
        body_color=body_color,
        title_pt=title_pt,
        body_pt=body_pt,
        position=position,
    )
    overlay_reader = pypdf.PdfReader(io.BytesIO(overlay_bytes))
    last.merge_page(overlay_reader.pages[0])

    dir_path = pdf_path.parent
    fd, tmp_path_str = tempfile.mkstemp(
        dir=dir_path, prefix=pdf_path.name + ".issuer.", suffix=".tmp"
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
