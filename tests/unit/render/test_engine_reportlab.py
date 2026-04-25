"""Tests for the ReportLab engine (Plan 1 minimal: headings + paragraphs).

Plan 3 extends to tables, code, mermaid, images, lists, blockquotes.
"""
from pathlib import Path

import pytest
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
    """If SimpleDocTemplate.build() crashes mid-write, target stays absent and no
    .tmp.* leftover remains. Strengthened to actually write bytes through the
    atomic_write fp before raising — exercises the rollback path that the
    refactor introduced (without mid-write bytes the same postconditions would
    hold trivially even without atomic_write)."""
    from reportlab.platypus import SimpleDocTemplate

    from mdpdf.markdown.ast import Document, Paragraph, Text

    def _exploding_build(self, *args, **kwargs):  # noqa: ARG001
        # In the post-Task-12 engine, self.filename is the file-like fp from
        # atomic_write — write some bytes to simulate a partial PDF, then crash.
        if hasattr(self.filename, "write"):
            self.filename.write(b"%PDF-1.4 partial bytes\n")
        raise RuntimeError("simulated mid-render failure")

    monkeypatch.setattr(SimpleDocTemplate, "build", _exploding_build)

    out = tmp_path / "should-not-exist.pdf"
    doc = Document(children=[Paragraph(children=[Text(content="x")])])
    with pytest.raises(RuntimeError, match="mid-render"):
        ReportLabEngine().render(doc, out)
    assert not out.exists(), "atomic_write must roll back partial writes"
    leftovers = list(tmp_path.glob("should-not-exist.pdf*"))
    assert leftovers == [], f"unexpected leftovers: {leftovers}"
