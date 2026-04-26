"""Tests for promote_toc transformer (spec §2.1.3)."""
from mdpdf.markdown.ast import (
    Document,
    Heading,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    Text,
)
from mdpdf.markdown.transformers.promote_toc import promote_toc


def _h(level: int, txt: str) -> Heading:
    return Heading(level=level, children=[Text(content=txt)])


def _p(txt: str) -> Paragraph:
    return Paragraph(children=[Text(content=txt)])


def _table_one_row() -> Table:
    return Table(
        header=TableRow(cells=[TableCell(children=[Text(content="H")])]),
        rows=[TableRow(cells=[TableCell(children=[Text(content="r1")])])],
    )


def test_promotes_chinese_toc_to_after_h1():
    doc = Document(children=[
        _h(1, "Title"),
        _p("intro"),
        _h(2, "Section A"),
        _p("a body"),
        _h(2, "目录"),
        _table_one_row(),
        _h(2, "Section B"),
        _p("b body"),
    ])
    out = promote_toc(doc)
    # Expected order: H1 Title, H2 目录, Table, Paragraph intro, H2 Section A, …
    assert out.children[0].children[0].content == "Title"
    assert isinstance(out.children[1], Heading)
    assert out.children[1].children[0].content == "目录"
    assert isinstance(out.children[2], Table)
    assert isinstance(out.children[3], Paragraph)


def test_promotes_english_toc():
    doc = Document(children=[
        _h(1, "Title"),
        _p("intro"),
        _h(2, "Table of Contents"),
        _p("dummy toc body"),
        _h(2, "Section A"),
    ])
    out = promote_toc(doc)
    assert out.children[1].children[0].content == "Table of Contents"
    assert isinstance(out.children[2], Paragraph)
    assert "dummy toc body" in out.children[2].children[0].content


def test_no_toc_returns_same_doc():
    doc = Document(children=[
        _h(1, "Title"),
        _p("body"),
    ])
    out = promote_toc(doc)
    assert out is doc


def test_no_h1_leaves_toc_alone():
    """Without an H1 anchor, leave the TOC where it is (defensive)."""
    doc = Document(children=[
        _h(2, "目录"),
        _p("toc body"),
        _h(2, "Section"),
    ])
    out = promote_toc(doc)
    assert out is doc


def test_toc_already_at_correct_position_no_op():
    doc = Document(children=[
        _h(1, "Title"),
        _h(2, "目录"),
        _table_one_row(),
        _p("body"),
    ])
    out = promote_toc(doc)
    assert out is doc


def test_toc_with_no_following_content_still_promoted_alone():
    """If TOC heading has no body block after it, just move the heading."""
    doc = Document(children=[
        _h(1, "Title"),
        _p("intro"),
        _h(2, "Section A"),
        _h(2, "目录"),  # last node; nothing follows
    ])
    out = promote_toc(doc)
    assert out.children[1].children[0].content == "目录"
    # Original intro paragraph still present somewhere
    body_paras = [c for c in out.children if isinstance(c, Paragraph)]
    assert any(p.children[0].content == "intro" for p in body_paras)


def test_case_insensitive_english_match():
    doc = Document(children=[
        _h(1, "Title"),
        _p("body"),
        _h(2, "table of contents"),
        _p("toc"),
    ])
    out = promote_toc(doc)
    assert out.children[1].children[0].content.lower() == "table of contents"
