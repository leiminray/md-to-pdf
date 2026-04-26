"""Tests for the transformer chain runner (spec §2.1.3)."""
from mdpdf.markdown.ast import Document, Heading, Paragraph, Text
from mdpdf.markdown.transformers import Transformer, run_transformers


def _doc(*children) -> Document:
    return Document(children=list(children))


def test_run_transformers_passes_doc_through_in_order():
    calls: list[str] = []

    def t1(doc: Document) -> Document:
        calls.append("t1")
        return doc

    def t2(doc: Document) -> Document:
        calls.append("t2")
        return doc

    out = run_transformers(_doc(Paragraph(children=[Text(content="x")])), [t1, t2])
    assert calls == ["t1", "t2"]
    assert isinstance(out, Document)


def test_run_transformers_replaces_document():
    """A transformer can return a new Document; the next sees the new one."""

    def upper(doc: Document) -> Document:
        new_children = []
        for c in doc.children:
            if isinstance(c, Paragraph):
                new_children.append(Paragraph(children=[Text(content="UPPER")]))
            else:
                new_children.append(c)
        return Document(children=new_children)

    def assert_upper(doc: Document) -> Document:
        assert isinstance(doc.children[0], Paragraph)
        assert doc.children[0].children[0].content == "UPPER"
        return doc

    run_transformers(_doc(Paragraph(children=[Text(content="hi")])), [upper, assert_upper])


def test_transformer_protocol_accepts_callable():
    """Transformer is just `Callable[[Document], Document]`."""

    def noop(doc: Document) -> Document:
        return doc

    t: Transformer = noop
    assert callable(t)


def test_empty_transformer_list_is_identity():
    doc = _doc(Heading(level=1, children=[Text(content="A")]))
    out = run_transformers(doc, [])
    assert out is doc
