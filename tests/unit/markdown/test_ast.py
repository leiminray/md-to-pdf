"""Tests for AST node dataclasses."""
from mdpdf.markdown.ast import (
    CodeFence,
    Document,
    Heading,
    Html,
    Image,
    ListBlock,
    ListItem,
    MermaidBlock,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)


def test_document_holds_children():
    doc = Document(children=[Paragraph(children=[Text(content="hi")])])
    assert len(doc.children) == 1
    assert isinstance(doc.children[0], Paragraph)


def test_heading_level_is_required():
    h = Heading(level=2, children=[Text(content="Section")])
    assert h.level == 2
    assert h.children[0].content == "Section"


def test_paragraph_holds_inline_children():
    para = Paragraph(children=[
        Text(content="Hello "),
        Strong(children=[Text(content="world")]),
        Text(content="!"),
    ])
    assert len(para.children) == 3
    assert isinstance(para.children[1], Strong)


def test_code_fence_carries_lang_and_content():
    fence = CodeFence(lang="python", content="x = 1")
    assert fence.lang == "python"
    assert fence.content == "x = 1"


def test_mermaid_block_distinct_from_code_fence():
    block = MermaidBlock(source="graph TD;\n  A-->B")
    assert "graph TD" in block.source


def test_table_structure():
    table = Table(
        header=TableRow(cells=[TableCell(children=[Text(content="A")])]),
        rows=[TableRow(cells=[TableCell(children=[Text(content="1")])])],
    )
    assert len(table.rows) == 1


def test_list_block_with_items():
    lst = ListBlock(
        ordered=False,
        items=[
            ListItem(children=[Paragraph(children=[Text(content="a")])]),
            ListItem(children=[Paragraph(children=[Text(content="b")])]),
        ],
    )
    assert lst.ordered is False
    assert len(lst.items) == 2


def test_image_carries_src_and_alt():
    img = Image(src="./pic.png", alt="picture")
    assert img.src == "./pic.png"
    assert img.alt == "picture"


def test_thematic_break_is_self_contained():
    hr = ThematicBreak()
    assert hr is not None


def test_html_passthrough():
    h = Html(content="<div>raw</div>")
    assert "<div>" in h.content


def test_front_matter_carries_raw_yaml():
    from mdpdf.markdown.ast import FrontMatter
    fm = FrontMatter(raw="title: Hi\nauthor: Alice\n")
    assert "title: Hi" in fm.raw
