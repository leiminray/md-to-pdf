"""Tests for list rendering (spec §2.1.5)."""
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate

from mdpdf.markdown.ast import ListBlock, ListItem, Paragraph, Text
from mdpdf.render.lists import ast_list_to_flowable


def _body_style() -> ParagraphStyle:
    return ParagraphStyle(name="b", fontName="Helvetica", fontSize=11, leading=16)


def test_unordered_list_renders(tmp_path: Path):
    lst = ListBlock(
        ordered=False,
        items=[
            ListItem(children=[Paragraph(children=[Text(content="alpha")])]),
            ListItem(children=[Paragraph(children=[Text(content="beta")])]),
            ListItem(children=[Paragraph(children=[Text(content="gamma")])]),
        ],
    )
    out = tmp_path / "ul.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=32 * mm,
    )
    doc.build([ast_list_to_flowable(lst, _body_style())])
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    for word in ("alpha", "beta", "gamma"):
        assert word in text


def test_ordered_list_renders(tmp_path: Path):
    lst = ListBlock(
        ordered=True,
        items=[
            ListItem(children=[Paragraph(children=[Text(content="first")])]),
            ListItem(children=[Paragraph(children=[Text(content="second")])]),
        ],
    )
    out = tmp_path / "ol.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=32 * mm,
    )
    doc.build([ast_list_to_flowable(lst, _body_style())])
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    for word in ("first", "second"):
        assert word in text


def test_nested_list_renders(tmp_path: Path):
    inner = ListBlock(
        ordered=False,
        items=[
            ListItem(children=[Paragraph(children=[Text(content="inner-a")])]),
            ListItem(children=[Paragraph(children=[Text(content="inner-b")])]),
        ],
    )
    outer = ListBlock(
        ordered=False,
        items=[
            ListItem(children=[Paragraph(children=[Text(content="outer-1")]), inner]),
            ListItem(children=[Paragraph(children=[Text(content="outer-2")])]),
        ],
    )
    out = tmp_path / "nested.pdf"
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=32 * mm,
    )
    doc.build([ast_list_to_flowable(outer, _body_style())])
    text = "".join(p.extract_text() for p in PdfReader(str(out)).pages)
    for word in ("outer-1", "outer-2", "inner-a", "inner-b"):
        assert word in text
