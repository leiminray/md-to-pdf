"""Internal AST node types (spec §2.1.3).

Decoupled from ReportLab so the AST can be reused by future engines and
golden tests (`expected.ast.json`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


# Forward declarations are deferred via `Node` union; see end of module.


@dataclass
class Text:
    content: str


@dataclass
class Code:
    """Inline code (single backticks)."""

    content: str


@dataclass
class Emphasis:
    children: list["Inline"] = field(default_factory=list)


@dataclass
class Strong:
    children: list["Inline"] = field(default_factory=list)


@dataclass
class Link:
    href: str
    children: list["Inline"] = field(default_factory=list)


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
    children: list["Inline"] = field(default_factory=list)


@dataclass
class Heading:
    level: int
    children: list["Inline"] = field(default_factory=list)


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
    children: list["Inline"] = field(default_factory=list)


@dataclass
class TableRow:
    cells: list[TableCell] = field(default_factory=list)


@dataclass
class Table:
    header: TableRow
    rows: list[TableRow] = field(default_factory=list)


@dataclass
class ListItem:
    children: list["Block"] = field(default_factory=list)


@dataclass
class ListBlock:
    ordered: bool
    items: list[ListItem] = field(default_factory=list)


@dataclass
class BlockQuote:
    children: list["Block"] = field(default_factory=list)


@dataclass
class ThematicBreak:
    """Horizontal rule (`---`)."""


@dataclass
class Html:
    """Raw HTML pass-through (optional; default-stripped in Plan 2)."""

    content: str


@dataclass
class Document:
    children: list["Block"] = field(default_factory=list)


Inline = Union[Text, Code, Emphasis, Strong, Link, Image]
Block = Union[
    Paragraph,
    Heading,
    CodeFence,
    MermaidBlock,
    Table,
    ListBlock,
    BlockQuote,
    ThematicBreak,
    Html,
    Image,
]
