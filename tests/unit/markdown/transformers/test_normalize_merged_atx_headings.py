"""Tests for normalize_merged_atx_headings transformer (spec §2.1.3, v1.8.9 parity)."""
from mdpdf.markdown.ast import Document, Heading, Paragraph, Text
from mdpdf.markdown.transformers.normalize_merged_atx_headings import (
    normalize_merged_atx_headings,
)


def test_splits_run_on_h1_and_h2():
    doc = Document(children=[
        Heading(level=1, children=[Text(content="Part## Chapter")]),
    ])
    out = normalize_merged_atx_headings(doc)
    assert len(out.children) == 2
    assert isinstance(out.children[0], Heading)
    assert out.children[0].level == 1
    assert out.children[0].children[0].content == "Part"
    assert isinstance(out.children[1], Heading)
    assert out.children[1].level == 2
    assert out.children[1].children[0].content == "Chapter"


def test_splits_h2_and_h3():
    doc = Document(children=[
        Heading(level=2, children=[Text(content="Section### Subsection")]),
    ])
    out = normalize_merged_atx_headings(doc)
    assert [h.level for h in out.children] == [2, 3]
    assert out.children[0].children[0].content == "Section"
    assert out.children[1].children[0].content == "Subsection"


def test_does_not_split_at_lower_level():
    """`# Part# Other` is NOT a run-on (both H1) — left alone per v1.8.9."""
    doc = Document(children=[
        Heading(level=1, children=[Text(content="Part# Other")]),
    ])
    out = normalize_merged_atx_headings(doc)
    # left untouched
    assert len(out.children) == 1
    assert out.children[0].children[0].content == "Part# Other"


def test_does_not_split_inside_paragraph():
    """Hashes inside paragraph text must not be misinterpreted."""
    doc = Document(children=[
        Paragraph(children=[Text(content="See # 1## also")]),
    ])
    out = normalize_merged_atx_headings(doc)
    assert len(out.children) == 1
    assert isinstance(out.children[0], Paragraph)


def test_no_run_on_returns_same_doc():
    doc = Document(children=[
        Heading(level=1, children=[Text(content="Title")]),
        Paragraph(children=[Text(content="body")]),
    ])
    out = normalize_merged_atx_headings(doc)
    assert out is doc


def test_handles_multiple_run_ons():
    doc = Document(children=[
        Heading(level=1, children=[Text(content="A## B")]),
        Heading(level=2, children=[Text(content="C### D")]),
    ])
    out = normalize_merged_atx_headings(doc)
    assert [h.level for h in out.children] == [1, 2, 2, 3]


def test_run_on_with_inline_children_other_than_text_is_left_alone():
    """Conservative: only split when the heading's only child is a single Text."""
    from mdpdf.markdown.ast import Strong
    doc = Document(children=[
        Heading(
            level=1,
            children=[Text(content="Part## "), Strong(children=[Text(content="Chapter")])],
        ),
    ])
    out = normalize_merged_atx_headings(doc)
    assert len(out.children) == 1  # not split
