"""Tests for collect_outline transformer (spec §2.1.3)."""
from mdpdf.markdown.ast import (
    Document,
    Heading,
    OutlineEntry,
    Paragraph,
    Strong,
    Text,
)
from mdpdf.markdown.transformers.collect_outline import collect_outline


def _h(level: int, *texts: str) -> Heading:
    return Heading(level=level, children=[Text(content=t) for t in texts])


def test_collects_simple_outline():
    doc = Document(children=[
        _h(1, "Chapter 1"),
        _h(2, "Section A"),
        _h(2, "Section B"),
    ])
    out = collect_outline(doc)
    assert len(out.outline) == 3
    titles = [e.plain_text for e in out.outline]
    assert titles == ["Chapter 1", "Section A", "Section B"]
    assert [e.level for e in out.outline] == [1, 2, 2]


def test_clamps_skip_jumps():
    """Going from h1 -> h4 directly is clamped to +1 (h2)."""
    doc = Document(children=[
        _h(1, "A"),
        _h(4, "B"),  # would jump to level 4; clamped to 2
        _h(5, "C"),  # +1 from B's clamped 2 → 3
    ])
    out = collect_outline(doc)
    assert [e.level for e in out.outline] == [1, 2, 3]


def test_unique_bookmark_ids():
    doc = Document(children=[
        _h(1, "Same"),
        _h(2, "Same"),
        _h(2, "Same"),
    ])
    out = collect_outline(doc)
    ids = [e.bookmark_id for e in out.outline]
    assert len(ids) == len(set(ids))


def test_extracts_plain_text_from_complex_inline():
    doc = Document(children=[
        Heading(level=1, children=[
            Text(content="Part "),
            Strong(children=[Text(content="One")]),
            Text(content=" of Three"),
        ]),
    ])
    out = collect_outline(doc)
    assert out.outline[0].plain_text == "Part One of Three"


def test_no_headings_empty_outline():
    doc = Document(children=[Paragraph(children=[Text(content="just body")])])
    out = collect_outline(doc)
    assert out.outline == []


def test_returns_new_document_when_outline_added():
    doc = Document(children=[_h(1, "X")])
    out = collect_outline(doc)
    assert out is not doc
    # Original children preserved
    assert out.children == doc.children


# Touch OutlineEntry import so ruff doesn't flag it as unused.
_ = OutlineEntry
