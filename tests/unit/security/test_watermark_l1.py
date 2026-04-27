"""Tests for security.watermark_l1 — L1 visible diagonal watermark overlay."""
from __future__ import annotations

import io
from pathlib import Path

import pypdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

from mdpdf.errors import SecurityError
from mdpdf.security.watermark_l1 import apply_l1_watermark, build_watermark_page


def _make_test_pdf(path: Path, page_count: int = 2) -> None:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    for i in range(page_count):
        c.drawString(72, 700, f"Page {i + 1} content")
        c.showPage()
    c.save()
    path.write_bytes(buf.getvalue())


# ── build_watermark_page ────────────────────────────────────────────────────


def test_build_watermark_page_returns_bytes() -> None:
    data = build_watermark_page(
        width_pt=A4[0],
        height_pt=A4[1],
        text="ACME // alice@example.com // 2026-04-27",
        color="#EBEFF0",
    )
    assert isinstance(data, bytes)
    assert len(data) > 200


def test_build_watermark_page_custom_color() -> None:
    data = build_watermark_page(
        width_pt=A4[0],
        height_pt=A4[1],
        text="TEST",
        color="#DDDDDD",
    )
    assert len(data) > 200


def test_build_watermark_page_contrast_guard_raises() -> None:
    with pytest.raises(SecurityError) as exc_info:
        build_watermark_page(
            width_pt=A4[0],
            height_pt=A4[1],
            text="TEST",
            color="#FFFFFF",
        )
    assert exc_info.value.code == "WATERMARK_CONTRAST_TOO_LOW"


# ── apply_l1_watermark ──────────────────────────────────────────────────────


def test_apply_watermark_text_on_every_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path, page_count=2)

    apply_l1_watermark(
        pdf_path,
        brand_name="ACME",
        user="alice@example.com",
        render_date="2026-04-27",
    )

    reader = pypdf.PdfReader(str(pdf_path))
    assert len(reader.pages) == 2
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        assert "alice@example.com" in text, f"Watermark text missing on page {i + 1}"

    # Watermark adds ~50KB of overlay content per page; for a tiny test PDF
    # the post-watermark file is dominated by the overlay, so use an absolute
    # cap rather than a tight ratio.
    new_size = pdf_path.stat().st_size
    assert new_size < 1_000_000  # 1MB cap for a 2-page test doc


def test_apply_watermark_custom_template(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path, page_count=1)

    apply_l1_watermark(
        pdf_path,
        brand_name="ACME",
        user="bob@example.com",
        render_date="2026-04-27",
        template="CONFIDENTIAL // {user}",
    )

    reader = pypdf.PdfReader(str(pdf_path))
    text = reader.pages[0].extract_text() or ""
    assert "CONFIDENTIAL" in text
    assert "bob@example.com" in text


def test_apply_watermark_does_not_corrupt_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path, page_count=3)
    apply_l1_watermark(
        pdf_path,
        brand_name="Corp",
        user="user@corp.com",
        render_date="2026-01-01",
    )
    reader = pypdf.PdfReader(str(pdf_path))
    assert len(reader.pages) == 3
