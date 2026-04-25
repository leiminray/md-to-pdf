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


def test_engine_does_not_leave_partial_file_on_error(tmp_path: Path, monkeypatch):
    """If SimpleDocTemplate.build() raises, the target file must not exist."""
    from mdpdf.markdown.ast import Document, Paragraph, Text
    from reportlab.platypus import SimpleDocTemplate

    original_build = SimpleDocTemplate.build

    def _exploding_build(self, *args, **kwargs):  # noqa: ARG001
        # Write a tiny stub then explode, simulating a mid-render crash.
        raise RuntimeError("simulated render failure")

    monkeypatch.setattr(SimpleDocTemplate, "build", _exploding_build)

    out = tmp_path / "should-not-exist.pdf"
    doc = Document(children=[Paragraph(children=[Text(content="x")])])
    try:
        ReportLabEngine().render(doc, out)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert not out.exists()
    leftovers = list(tmp_path.glob("should-not-exist.pdf.tmp.*"))
    assert leftovers == []
