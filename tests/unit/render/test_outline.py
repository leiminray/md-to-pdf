"""Tests for PDF outline generation (spec §2.1.5)."""
from pathlib import Path

from pypdf import PdfReader

from mdpdf.markdown.ast import Document, Heading, OutlineEntry, Paragraph, Text
from mdpdf.render.engine_reportlab import ReportLabEngine


def test_engine_produces_pdf_outline(tmp_path: Path):
    doc = Document(
        children=[
            Heading(level=1, children=[Text(content="Chapter 1")]),
            Paragraph(children=[Text(content="body")]),
            Heading(level=2, children=[Text(content="Section A")]),
            Paragraph(children=[Text(content="body")]),
            Heading(level=2, children=[Text(content="Section B")]),
            Paragraph(children=[Text(content="body")]),
        ],
        outline=[
            OutlineEntry(bookmark_id="ids-h-1", level=1, plain_text="Chapter 1"),
            OutlineEntry(bookmark_id="ids-h-2", level=2, plain_text="Section A"),
            OutlineEntry(bookmark_id="ids-h-3", level=2, plain_text="Section B"),
        ],
    )
    out = tmp_path / "outlined.pdf"
    ReportLabEngine().render(doc, out)
    reader = PdfReader(str(out))
    outline = reader.outline
    # outline is a (possibly nested) list; flatten and count entries.
    flat = _flatten_outline(outline)
    assert len(flat) >= 3
    titles = [item.title for item in flat]
    assert "Chapter 1" in titles
    assert "Section A" in titles
    assert "Section B" in titles


def _flatten_outline(outline) -> list:
    out = []
    for item in outline:
        if isinstance(item, list):
            out.extend(_flatten_outline(item))
        else:
            out.append(item)
    return out
