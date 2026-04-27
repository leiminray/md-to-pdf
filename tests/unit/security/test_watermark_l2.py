"""Tests for security.watermark_l2 — L2 XMP RDF metadata watermark."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pikepdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

from mdpdf.security.watermark_l2 import apply_l2_xmp


def _make_test_pdf(path: Path) -> None:
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 700, "Test page")
    c.showPage()
    c.save()
    path.write_bytes(buf.getvalue())


_SAMPLE_KWARGS: dict[str, Any] = {
    "dc_creator": "ACME Corp",
    "dc_title": "Test Document",
    "render_id": "12345678-1234-1234-1234-123456789abc",
    "render_user": "alice@example.com",
    "render_host": "abcdef0123456789",
    "brand_id": "acme",
    "brand_version": "1.0.0",
    "input_hash": "a" * 64,
    "create_date": "2026-04-27T10:00:00+00:00",
    "watermark_level": "L1+L2",
}


def test_apply_l2_xmp_all_keys_present(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path)
    apply_l2_xmp(pdf_path, **_SAMPLE_KWARGS)

    with pikepdf.open(str(pdf_path)) as pdf, pdf.open_metadata() as meta:
        # dc:creator is an XMP Bag/Seq per spec; pikepdf returns a list-like.
        assert list(meta["dc:creator"]) == ["ACME Corp"]
        assert meta["dc:title"] == "Test Document"
        assert meta["pdf:Producer"] == "md-to-pdf 2.0"
        assert meta["xmp:CreatorTool"] == "md-to-pdf 2.0"
        assert meta["xmp:CreateDate"] == "2026-04-27T10:00:00+00:00"
        assert meta["mdpdf:RenderId"] == "12345678-1234-1234-1234-123456789abc"
        assert meta["mdpdf:RenderUser"] == "alice@example.com"
        assert meta["mdpdf:RenderHost"] == "abcdef0123456789"
        assert meta["mdpdf:BrandId"] == "acme"
        assert meta["mdpdf:BrandVersion"] == "1.0.0"
        assert meta["mdpdf:InputHash"] == "a" * 64
        assert meta["mdpdf:WatermarkLevel"] == "L1+L2"


def test_apply_l2_xmp_watermark_level_l2_only(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path)
    kwargs = dict(_SAMPLE_KWARGS, watermark_level="L2")
    apply_l2_xmp(pdf_path, **kwargs)

    with pikepdf.open(str(pdf_path)) as pdf, pdf.open_metadata() as meta:
        assert meta["mdpdf:WatermarkLevel"] == "L2"


def test_apply_l2_xmp_does_not_corrupt_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path)
    apply_l2_xmp(pdf_path, **_SAMPLE_KWARGS)

    with pikepdf.open(str(pdf_path)) as pdf:
        assert len(pdf.pages) == 1


def test_apply_l2_xmp_idempotent_on_second_call(tmp_path: Path) -> None:
    pdf_path = tmp_path / "test.pdf"
    _make_test_pdf(pdf_path)
    apply_l2_xmp(pdf_path, **_SAMPLE_KWARGS)

    kwargs2 = dict(_SAMPLE_KWARGS, render_user="bob@example.com")
    apply_l2_xmp(pdf_path, **kwargs2)

    with pikepdf.open(str(pdf_path)) as pdf, pdf.open_metadata() as meta:
        assert meta["mdpdf:RenderUser"] == "bob@example.com"
