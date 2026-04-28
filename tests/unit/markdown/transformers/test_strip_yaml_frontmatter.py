"""Tests for strip_yaml_frontmatter transformer."""
from mdpdf.markdown.ast import Document, FrontMatter, Heading, Paragraph, Text
from mdpdf.markdown.transformers.strip_yaml_frontmatter import strip_yaml_frontmatter


def test_removes_leading_front_matter():
    doc = Document(children=[
        FrontMatter(raw="title: x"),
        Heading(level=1, children=[Text(content="H")]),
        Paragraph(children=[Text(content="body")]),
    ])
    out = strip_yaml_frontmatter(doc)
    assert len(out.children) == 2
    assert isinstance(out.children[0], Heading)
    assert isinstance(out.children[1], Paragraph)


def test_no_front_matter_unchanged():
    doc = Document(children=[
        Heading(level=1, children=[Text(content="H")]),
    ])
    out = strip_yaml_frontmatter(doc)
    assert out.children == doc.children


def test_front_matter_only_in_leading_position_is_removed():
    """A FrontMatter node not at position 0 is left alone (defensive — should never happen)."""
    doc = Document(children=[
        Heading(level=1, children=[Text(content="H")]),
        FrontMatter(raw="title: x"),  # malformed input
    ])
    out = strip_yaml_frontmatter(doc)
    assert len(out.children) == 2
    assert isinstance(out.children[1], FrontMatter)


def test_returns_new_document_instance_when_changed():
    doc = Document(children=[FrontMatter(raw="x")])
    out = strip_yaml_frontmatter(doc)
    assert out is not doc
    assert out.children == []


def test_returns_same_document_when_unchanged():
    doc = Document(children=[Heading(level=1, children=[Text(content="H")])])
    out = strip_yaml_frontmatter(doc)
    assert out is doc
