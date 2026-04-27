"""Tests for the MermaidImage flowable."""
from pathlib import Path

from PIL import Image as PILImage
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate

from mdpdf.render.flowables import MermaidImage


def test_mermaid_image_renders(tmp_path: Path) -> None:
    src = tmp_path / "diagram.png"
    PILImage.new("RGB", (300, 200), (255, 255, 255)).save(src, "PNG")
    out = tmp_path / "out.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=32 * mm,
    )
    doc.build([MermaidImage(image_path=src, caption="Figure 1: example")])
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "Figure 1" in text


def test_mermaid_image_no_caption(tmp_path: Path) -> None:
    src = tmp_path / "noc.png"
    PILImage.new("RGB", (200, 100), (255, 255, 255)).save(src, "PNG")
    out = tmp_path / "out.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=32 * mm,
    )
    doc.build([MermaidImage(image_path=src, caption=None)])
    assert out.exists()
