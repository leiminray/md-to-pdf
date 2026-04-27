"""Tests for post_process.footer — all-pages footer overlay."""
from __future__ import annotations

from pathlib import Path

import pypdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from mdpdf.post_process.footer import apply_footer


def _make_pdf(tmp_path: Path, num_pages: int = 3) -> Path:
    out = tmp_path / "source.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)
    for i in range(num_pages):
        c.drawString(72, 700, f"Page content {i + 1}")
        c.showPage()
    c.save()
    return out


class TestApplyFooterEnglish:
    def test_footer_text_appears_on_every_page(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=3)
        apply_footer(
            pdf,
            brand_name="Acme Corp",
            confidential_text="Confidential",
            locale="en",
        )

        reader = pypdf.PdfReader(str(pdf))
        assert len(reader.pages) == 3
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            assert "Confidential" in text, f"Page {i+1} missing confidential text"
            assert "Acme Corp" in text, f"Page {i+1} missing brand name"
            assert f"Page {i + 1} of 3" in text, f"Page {i+1} missing page counter"

    def test_footer_page_counter_single_page(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=1)
        apply_footer(pdf, brand_name="WidgetCo", confidential_text="PRIVATE", locale="en")

        reader = pypdf.PdfReader(str(pdf))
        text = reader.pages[0].extract_text() or ""
        assert "Page 1 of 1" in text

    def test_footer_five_pages(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=5)
        apply_footer(pdf, brand_name="Corp", confidential_text="Confidential", locale="en")

        reader = pypdf.PdfReader(str(pdf))
        assert len(reader.pages) == 5
        for i in range(5):
            text = reader.pages[i].extract_text() or ""
            assert f"Page {i + 1} of 5" in text


class TestApplyFooterChineseCN:
    def test_footer_zh_cn_confidential_label(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=3)
        apply_footer(pdf, brand_name="艾可公司", confidential_text="机密", locale="zh-CN")

        reader = pypdf.PdfReader(str(pdf))
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            assert "机密" in text or "艾可公司" in text, (
                f"Page {i+1} missing zh-CN confidential or brand text"
            )

    def test_footer_zh_cn_page_format(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=2)
        apply_footer(pdf, brand_name="Brand", confidential_text="机密", locale="zh-CN")

        reader = pypdf.PdfReader(str(pdf))
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            assert f"第 {i + 1} 页" in text, f"Page {i+1} missing zh-CN page counter"


class TestApplyFooterDefaults:
    def test_custom_font_size_accepted(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=1)
        apply_footer(
            pdf,
            brand_name="X",
            confidential_text="C",
            locale="en",
            font_size=6,
        )

    def test_custom_margins_accepted(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=1)
        apply_footer(
            pdf,
            brand_name="X",
            confidential_text="C",
            locale="en",
            left_margin_mm=25.0,
            bottom_margin_mm=12.0,
        )

    def test_custom_color_accepted(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=1)
        apply_footer(
            pdf,
            brand_name="X",
            confidential_text="C",
            locale="en",
            color="#374151",
        )
