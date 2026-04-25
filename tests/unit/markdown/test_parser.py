"""Tests for the markdown-it-py → AST conversion (spec §2.1.3)."""
from mdpdf.markdown.ast import (
    BlockQuote,
    CodeFence,
    Document,
    Heading,
    Image,
    ListBlock,
    MermaidBlock,
    Paragraph,
    Strong,
    Table,
)
from mdpdf.markdown.parser import parse_markdown


def test_empty_document():
    doc = parse_markdown("")
    assert isinstance(doc, Document)
    assert doc.children == []


def test_single_paragraph():
    doc = parse_markdown("Hello, world.")
    assert len(doc.children) == 1
    assert isinstance(doc.children[0], Paragraph)


def test_heading_levels():
    doc = parse_markdown("# H1\n\n## H2\n\n### H3")
    headings = [n for n in doc.children if isinstance(n, Heading)]
    assert [h.level for h in headings] == [1, 2, 3]


def test_inline_strong():
    doc = parse_markdown("This is **bold** text.")
    para = doc.children[0]
    assert isinstance(para, Paragraph)
    strong_children = [c for c in para.children if isinstance(c, Strong)]
    assert len(strong_children) == 1
    assert strong_children[0].children[0].content == "bold"


def test_code_fence_with_language():
    doc = parse_markdown("```python\nprint('hi')\n```")
    fence = doc.children[0]
    assert isinstance(fence, CodeFence)
    assert fence.lang == "python"
    assert "print('hi')" in fence.content


def test_mermaid_fence_becomes_mermaid_block():
    doc = parse_markdown("```mermaid\ngraph TD;\n  A-->B\n```")
    block = doc.children[0]
    assert isinstance(block, MermaidBlock)
    assert "graph TD" in block.source


def test_mmd_fence_becomes_mermaid_block():
    doc = parse_markdown("```mmd\ngraph TD;\n  A-->B\n```")
    assert isinstance(doc.children[0], MermaidBlock)


def test_pipe_table():
    src = "| h1 | h2 |\n|----|----|\n| a  | b  |\n"
    doc = parse_markdown(src)
    table = doc.children[0]
    assert isinstance(table, Table)
    assert len(table.header.cells) == 2
    assert len(table.rows) == 1


def test_unordered_list():
    doc = parse_markdown("- a\n- b\n- c\n")
    lst = doc.children[0]
    assert isinstance(lst, ListBlock)
    assert lst.ordered is False
    assert len(lst.items) == 3


def test_ordered_list():
    doc = parse_markdown("1. a\n2. b\n")
    lst = doc.children[0]
    assert isinstance(lst, ListBlock)
    assert lst.ordered is True


def test_block_quote():
    doc = parse_markdown("> quoted line")
    bq = doc.children[0]
    assert isinstance(bq, BlockQuote)


def test_thematic_break():
    doc = parse_markdown("Before\n\n---\n\nAfter")
    types = [type(c).__name__ for c in doc.children]
    assert "ThematicBreak" in types


def test_image_block():
    doc = parse_markdown("![alt text](./pic.png)")
    # Markdown-it parses standalone image as a paragraph containing Image.
    para = doc.children[0]
    assert isinstance(para, Paragraph)
    images = [c for c in para.children if isinstance(c, Image)]
    assert len(images) == 1
    assert images[0].src == "./pic.png"
    assert images[0].alt == "alt text"


def test_unknown_fence_lang_falls_back_to_codefence():
    doc = parse_markdown("```\nplain code\n```")
    fence = doc.children[0]
    assert isinstance(fence, CodeFence)
    assert fence.lang == ""
