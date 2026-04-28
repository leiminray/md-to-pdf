"""Unit tests for AST transformers.

Tests coverage for the transformer pipeline:
- Verifies Document.metadata field exists and can be populated
- Tests that transformers work with the enhanced Document structure
"""
from mdpdf.markdown.ast import (
    Document,
    FrontMatter,
    Heading,
    Paragraph,
    Text,
)
from mdpdf.markdown.transformers.collect_outline import collect_outline
from mdpdf.markdown.transformers.strip_yaml_frontmatter import strip_yaml_frontmatter


class TestDocumentMetadata:
    """Tests for Document.metadata field."""

    def test_document_has_metadata_field(self) -> None:
        """Document should have metadata field that can store key-value pairs."""
        doc = Document(children=[], metadata={})
        assert hasattr(doc, "metadata")
        assert isinstance(doc.metadata, dict)

    def test_document_metadata_default_empty(self) -> None:
        """Document.metadata should default to empty dict."""
        doc = Document(children=[])
        assert doc.metadata == {}

    def test_document_metadata_can_be_populated(self) -> None:
        """Document.metadata should accept and store arbitrary values."""
        doc = Document(children=[], metadata={"title": "My Doc", "author": "Alice"})
        assert doc.metadata["title"] == "My Doc"
        assert doc.metadata["author"] == "Alice"

    def test_document_metadata_persists_through_transformers(self) -> None:
        """Metadata should persist when document is processed by transformers."""
        para = Paragraph(children=[Text(content="Content")])
        doc = Document(children=[para], metadata={"preserved": "value"})

        # Run through transformer
        result = strip_yaml_frontmatter(doc)

        # Metadata should persist (even if transformer doesn't add to it)
        assert result.metadata.get("preserved") == "value"


class TestFrontmatterStripper:
    """Tests for strip_yaml_frontmatter transformer."""

    def test_removes_frontmatter_from_children(self) -> None:
        """Frontmatter node should be removed from document children."""
        frontmatter = FrontMatter(raw="title: Test")
        para = Paragraph(children=[Text(content="Content")])
        doc = Document(children=[frontmatter, para], metadata={})

        result = strip_yaml_frontmatter(doc)

        # Frontmatter removed
        assert len(result.children) == 1
        assert isinstance(result.children[0], Paragraph)

    def test_preserves_non_frontmatter_documents(self) -> None:
        """Document without frontmatter should pass through unchanged."""
        para = Paragraph(children=[Text(content="Content")])
        doc = Document(children=[para], metadata={})

        result = strip_yaml_frontmatter(doc)

        assert len(result.children) == 1
        assert result.children[0] is para

    def test_empty_document(self) -> None:
        """Empty document should return unchanged."""
        doc = Document(children=[], metadata={})
        result = strip_yaml_frontmatter(doc)

        assert result.children == []


class TestOutlineCollector:
    """Tests for collect_outline transformer."""

    def test_collects_headings_into_outline(self) -> None:
        """Headings should be collected into document outline."""
        h1 = Heading(level=1, children=[Text(content="Introduction")])
        para = Paragraph(children=[Text(content="Content")])
        doc = Document(children=[h1, para], metadata={})

        result = collect_outline(doc)

        # Document children unchanged
        assert len(result.children) == 2

        # Outline created
        assert len(result.outline) > 0

    def test_no_headings_creates_empty_outline(self) -> None:
        """Document with no headings should have empty outline."""
        para = Paragraph(children=[Text(content="Just text")])
        doc = Document(children=[para], metadata={})

        result = collect_outline(doc)

        assert result.outline == []

    def test_outline_entries_have_required_fields(self) -> None:
        """Outline entries should have bookmark_id, level, and plain_text."""
        h1 = Heading(level=1, children=[Text(content="Chapter")])
        doc = Document(children=[h1], metadata={})

        result = collect_outline(doc)

        assert len(result.outline) > 0
        entry = result.outline[0]
        assert hasattr(entry, "bookmark_id")
        assert hasattr(entry, "level")
        assert hasattr(entry, "plain_text")
        assert entry.level == 1
        assert entry.plain_text == "Chapter"
