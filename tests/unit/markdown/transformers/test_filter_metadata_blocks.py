"""Tests for filter_metadata_blocks transformer."""
from mdpdf.markdown.ast import (
    Document,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    Text,
)
from mdpdf.markdown.transformers.filter_metadata_blocks import filter_metadata_blocks


def _bullet(text: str) -> ListItem:
    return ListItem(children=[Paragraph(children=[Text(content=text)])])


def test_strips_leading_metadata_bullet_list():
    """A leading bullet list of `Key: value` items at doc start is stripped."""
    doc = Document(children=[
        ListBlock(ordered=False, items=[
            _bullet("Author: Alice"),
            _bullet("Version: 1.0"),
            _bullet("Reviewer: Bob"),
        ]),
        Heading(level=1, children=[Text(content="Real Title")]),
        Paragraph(children=[Text(content="body")]),
    ])
    out = filter_metadata_blocks(doc)
    assert len(out.children) == 2
    assert isinstance(out.children[0], Heading)


def test_strips_metadata_bullets_after_h1():
    """Metadata bullets right after the H1 are also stripped."""
    doc = Document(children=[
        Heading(level=1, children=[Text(content="Title")]),
        ListBlock(ordered=False, items=[
            _bullet("Author: Alice"),
            _bullet("Date: 2026-04-26"),
        ]),
        Paragraph(children=[Text(content="body")]),
    ])
    out = filter_metadata_blocks(doc)
    assert len(out.children) == 2
    assert isinstance(out.children[1], Paragraph)


def test_does_not_strip_non_metadata_bullets():
    """A bullet list that doesn't match `Key: value` shape is preserved."""
    doc = Document(children=[
        Heading(level=1, children=[Text(content="Title")]),
        ListBlock(ordered=False, items=[
            _bullet("This is a plain bullet"),
            _bullet("Another bullet"),
        ]),
    ])
    out = filter_metadata_blocks(doc)
    assert len(out.children) == 2  # both kept


def test_strips_contributor_roles_section():
    """`## Contributor Roles` and everything until the next H2-or-shallower heading is removed."""
    doc = Document(children=[
        Heading(level=1, children=[Text(content="Title")]),
        Paragraph(children=[Text(content="Intro.")]),
        Heading(level=2, children=[Text(content="Contributor Roles")]),
        Paragraph(children=[Text(content="Alice — author")]),
        ListBlock(ordered=False, items=[_bullet("Bob — reviewer")]),
        Heading(level=2, children=[Text(content="Next Section")]),
        Paragraph(children=[Text(content="continues here")]),
    ])
    out = filter_metadata_blocks(doc)
    types_levels = [
        (type(c).__name__, getattr(c, "level", None))
        for c in out.children
    ]
    assert types_levels == [
        ("Heading", 1),
        ("Paragraph", None),
        ("Heading", 2),  # "Next Section" survives
        ("Paragraph", None),
    ]


def test_strips_contributor_role_singular():
    doc = Document(children=[
        Heading(level=2, children=[Text(content="Contributor Role")]),
        Paragraph(children=[Text(content="solo")]),
    ])
    out = filter_metadata_blocks(doc)
    assert out.children == []


def test_case_insensitive_contributor_match():
    doc = Document(children=[
        Heading(level=2, children=[Text(content="contributor roles")]),
        Paragraph(children=[Text(content="x")]),
    ])
    out = filter_metadata_blocks(doc)
    assert out.children == []


def test_no_metadata_returns_same_doc():
    doc = Document(children=[
        Heading(level=1, children=[Text(content="Title")]),
        Paragraph(children=[Text(content="body")]),
    ])
    out = filter_metadata_blocks(doc)
    assert out is doc
