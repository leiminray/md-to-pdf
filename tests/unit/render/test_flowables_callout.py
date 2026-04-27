"""Tests for the CalloutBox flowable."""
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph as RLParagraph
from reportlab.platypus import SimpleDocTemplate

from mdpdf.render.flowables import CalloutBox


def test_callout_box_renders_text(tmp_path: Path) -> None:
    body_style = ParagraphStyle(name="b", fontName="Helvetica", fontSize=11, leading=16)
    out = tmp_path / "out.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=32 * mm,
    )
    cb = CalloutBox(
        body=[RLParagraph("This is a quoted line.", body_style)],
        accent_color="#0066CC",
    )
    doc.build([cb])
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "quoted line" in text
