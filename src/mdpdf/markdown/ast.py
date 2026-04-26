"""Internal AST node types (spec §2.1.3).

Decoupled from ReportLab so the AST can be reused by future engines and
golden tests (`expected.ast.json`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Forward references for `Inline` and `Block` are resolved by the
# `Inline` / `Block` Union aliases declared at the bottom of this module
# (Python evaluates dataclass annotations as strings under
# `from __future__ import annotations`).


@dataclass
class Text:
    content: str


@dataclass
class Code:
    """Inline code (single backticks)."""

    content: str


@dataclass
class Emphasis:
    children: list[Inline] = field(default_factory=list)


@dataclass
class Strong:
    children: list[Inline] = field(default_factory=list)


@dataclass
class Link:
    href: str
    children: list[Inline] = field(default_factory=list)


@dataclass
class Image:
    """Image node — appears in both `Inline` and `Block` unions per CommonMark
    (an image-only paragraph is conventionally promoted to a block-level figure).
    """

    src: str
    alt: str = ""


# --- Block nodes ---


@dataclass
class Paragraph:
    children: list[Inline] = field(default_factory=list)


@dataclass
class Heading:
    level: int
    children: list[Inline] = field(default_factory=list)


@dataclass
class CodeFence:
    """Fenced code block with non-mermaid language tag."""

    lang: str
    content: str


@dataclass
class MermaidBlock:
    """Fenced code block with `mermaid` (or `mmd`) language tag.

    Plan 1 leaves these as MermaidBlock instances; Plan 3 wires the
    Mermaid renderer chain to convert them to PNG flowables.
    """

    source: str


@dataclass
class TableCell:
    children: list[Inline] = field(default_factory=list)


@dataclass
class TableRow:
    cells: list[TableCell] = field(default_factory=list)


@dataclass
class Table:
    header: TableRow
    rows: list[TableRow] = field(default_factory=list)


@dataclass
class ListItem:
    children: list[Block] = field(default_factory=list)


@dataclass
class ListBlock:
    ordered: bool
    items: list[ListItem] = field(default_factory=list)


@dataclass
class BlockQuote:
    children: list[Block] = field(default_factory=list)


@dataclass
class ThematicBreak:
    """Horizontal rule (`---`)."""


@dataclass
class Html:
    """Raw HTML pass-through (optional; default-stripped in Plan 2)."""

    content: str


@dataclass
class FrontMatter:
    """YAML front-matter at the start of a document.

    Stored as raw text (not parsed). Plan 2's `strip_yaml_frontmatter`
    transformer removes this from the document body but the brand/template
    layers (Plan 2+) may consume the raw YAML separately.
    """

    raw: str


@dataclass
class OutlineEntry:
    """A heading destination for PDF bookmarks + TOC internal links."""

    bookmark_id: str           # unique id, e.g. "ids-h-3"
    level: int                 # display level (clamped to +1 jumps)
    plain_text: str            # the visible heading text (CJK preserved)


@dataclass
class Document:
    children: list[Block] = field(default_factory=list)
    outline: list[OutlineEntry] = field(default_factory=list)


Inline = Text | Code | Emphasis | Strong | Link | Image
Block = (
    Paragraph
    | Heading
    | CodeFence
    | MermaidBlock
    | Table
    | ListBlock
    | BlockQuote
    | ThematicBreak
    | Html
    | Image
    | FrontMatter
)
