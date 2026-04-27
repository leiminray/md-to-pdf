"""Tests for post_process.issuer_card — last-page issuer overlay."""
from __future__ import annotations

from pathlib import Path

import pypdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from mdpdf.post_process.issuer_card import apply_issuer_card


def _make_pdf(tmp_path: Path, num_pages: int = 3) -> Path:
    out = tmp_path / "source.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)
    for i in range(num_pages):
        c.drawString(72, 700, f"Page content {i + 1}")
        c.showPage()
    c.save()
    return out


class TestApplyIssuerCard:
    def test_issuer_name_on_last_page_only(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=3)
        apply_issuer_card(
            pdf,
            issuer_name="Acme Corp Ltd",
            issuer_lines=["Registered in Hong Kong", "Reg. No. 12345678"],
        )

        reader = pypdf.PdfReader(str(pdf))
        assert len(reader.pages) == 3

        last_text = reader.pages[2].extract_text() or ""
        assert "Acme Corp Ltd" in last_text

        for i in range(2):
            text = reader.pages[i].extract_text() or ""
            assert "Acme Corp Ltd" not in text, f"Page {i+1} should not have issuer card"

    def test_issuer_lines_on_last_page(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=2)
        apply_issuer_card(
            pdf,
            issuer_name="Widget Inc",
            issuer_lines=["Line one", "Line two"],
        )

        reader = pypdf.PdfReader(str(pdf))
        last_text = reader.pages[1].extract_text() or ""
        assert "Widget Inc" in last_text

    def test_single_page_pdf(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=1)
        apply_issuer_card(
            pdf,
            issuer_name="Solo Corp",
            issuer_lines=["Only line"],
        )

        reader = pypdf.PdfReader(str(pdf))
        text = reader.pages[0].extract_text() or ""
        assert "Solo Corp" in text

    def test_custom_colors_accepted(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=1)
        apply_issuer_card(
            pdf,
            issuer_name="Corp",
            issuer_lines=["Line"],
            card_bg_hex="#FFFFFF",
            card_border_hex="#000000",
            title_color_hex="#111111",
            body_color_hex="#888888",
        )

    def test_empty_issuer_lines(self, tmp_path: Path) -> None:
        pdf = _make_pdf(tmp_path, num_pages=1)
        apply_issuer_card(pdf, issuer_name="Corp", issuer_lines=[])

        reader = pypdf.PdfReader(str(pdf))
        text = reader.pages[0].extract_text() or ""
        assert "Corp" in text
