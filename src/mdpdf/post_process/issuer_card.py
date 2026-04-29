"""Issuer card overlay: rendered on the last page only.

Layout:
- Left-edge accent bar (border)
- Card background
- Optional brand icon at top-left
- Issuer name (bold, title colour)
- Issuer lines (body colour, smaller font); CJK-aware font fallback
- Optional QR code at right (URL or vCard payload)

Writes back atomically (tempfile + fsync + rename).
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
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas as rl_canvas

from mdpdf.fonts.manager import FontManager, cjk_chars_present

_BUNDLED_FONTS_DIR = Path(__file__).resolve().parents[3] / "fonts"


def _hex_to_color(hex_color: str) -> colors.Color:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return colors.Color(r / 255.0, g / 255.0, b / 255.0)


def _select_text_font(text: str, default: str = "Helvetica") -> tuple[str, str]:
    """Return (regular_font, bold_font) names. Falls back to a CJK font when the
    text contains CJK characters or fullwidth punctuation that Helvetica lacks.
    """
    if not cjk_chars_present(text):
        return default, "Helvetica-Bold"
    fm = FontManager(bundled_dir=_BUNDLED_FONTS_DIR)
    with contextlib.suppress(Exception):
        fm.register_for_text(text)
    registered = pdfmetrics.getRegisteredFontNames()
    for cand in ("NotoSansSC-Regular", "NotoSansCJK-Regular", "PingFang"):
        if cand in registered:
            bold_cand = cand.replace("-Regular", "-Bold")
            return cand, bold_cand if bold_cand in registered else cand
    return default, "Helvetica-Bold"


def _build_qr_png(payload: str, *, box_size: int = 4) -> bytes | None:
    """Generate a QR code PNG (no quiet zone padding bloat)."""
    try:
        import qrcode  # type: ignore[import-untyped]
    except ImportError:
        return None
    qr = qrcode.QRCode(border=1, box_size=box_size)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_card_overlay(
    page_width: float,
    page_height: float,
    *,
    issuer_name: str,
    issuer_lines: list[str],
    icon_path: Path | None,
    qr_payload: str | None,
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

    sample = issuer_name + " " + " ".join(issuer_lines)
    body_font, bold_font = _select_text_font(sample)

    x_pt, y_pt = position[0] * mm, position[1] * mm
    card_w = 175 * mm
    line_height = body_pt * 1.5
    icon_size = 14 * mm
    qr_size = 22 * mm
    card_h = max(
        title_pt * 1.8 + len(issuer_lines) * line_height + 10,
        icon_size + 6,
        qr_size + 6,
    )

    c.setFillColor(card_bg)
    c.rect(x_pt, y_pt, card_w, card_h, stroke=0, fill=1)

    border_w = 3 * mm
    c.setFillColor(card_border)
    c.rect(x_pt, y_pt, border_w, card_h, stroke=0, fill=1)

    text_x = x_pt + border_w + 4 * mm

    if icon_path is not None and icon_path.exists():
        try:
            c.drawImage(
                ImageReader(str(icon_path)),
                text_x,
                y_pt + card_h - icon_size - 3,
                width=icon_size,
                height=icon_size,
                mask="auto",
                preserveAspectRatio=True,
            )
            text_x += icon_size + 4 * mm
        except Exception:  # noqa: S110, BLE001 — best-effort image overlay; missing-asset is non-fatal
            pass

    qr_png = _build_qr_png(qr_payload) if qr_payload else None
    text_right_limit = x_pt + card_w - 4 * mm
    if qr_png is not None:
        qr_x = x_pt + card_w - qr_size - 4 * mm
        qr_y = y_pt + (card_h - qr_size) / 2
        try:
            c.drawImage(
                ImageReader(io.BytesIO(qr_png)),
                qr_x, qr_y,
                width=qr_size, height=qr_size,
                mask="auto",
            )
            text_right_limit = qr_x - 3 * mm
        except Exception:  # noqa: S110, BLE001 — best-effort image overlay; missing-asset is non-fatal
            pass

    c.setFillColor(title_color)
    c.setFont(bold_font, title_pt)
    text_y = y_pt + card_h - title_pt * 1.4
    c.drawString(text_x, text_y, issuer_name[: max(20, int((text_right_limit - text_x) / 5))])

    c.setFont(body_font, body_pt)
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
    icon_path: Path | None = None,
    qr_payload: str | None = None,
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
        icon_path=icon_path,
        qr_payload=qr_payload,
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
