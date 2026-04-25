"""Tests for the ReportLab engine (Plan 1 minimal: headings + paragraphs).

Plan 3 extends to tables, code, mermaid, images, lists, blockquotes.
"""
from pathlib import Path

from pypdf import PdfReader

from mdpdf.markdown.ast import Document, Heading, Paragraph, Text
from mdpdf.render.engine_reportlab import ReportLabEngine


def test_engine_renders_blank_document(tmp_path: Path):
    engine = ReportLabEngine()
    out = tmp_path / "blank.pdf"
    pages = engine.render(Document(children=[]), out)
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")
    assert pages >= 1  # SimpleDocTemplate emits at least one page


def test_engine_renders_paragraph(tmp_path: Path):
    doc = Document(children=[Paragraph(children=[Text(content="Hello, world.")])])
    out = tmp_path / "para.pdf"
    pages = ReportLabEngine().render(doc, out)
    assert pages == 1
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "Hello, world" in text


def test_engine_renders_heading(tmp_path: Path):
    doc = Document(children=[
        Heading(level=1, children=[Text(content="Title")]),
        Paragraph(children=[Text(content="Body text.")]),
    ])
    out = tmp_path / "h.pdf"
    ReportLabEngine().render(doc, out)
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "Title" in text
    assert "Body text" in text


def test_unsupported_node_renders_placeholder(tmp_path: Path):
    """In Plan 1, unsupported node types render as `[unsupported: <type>]`."""
    from mdpdf.markdown.ast import CodeFence
    doc = Document(children=[CodeFence(lang="python", content="x = 1")])
    out = tmp_path / "u.pdf"
    ReportLabEngine().render(doc, out)
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    assert "unsupported" in text.lower()
    assert "codefence" in text.lower()
