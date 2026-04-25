"""markdown-it-py → internal AST conversion (spec §2.1.3).

GFM extensions: tables, strikethrough. AST transformers (frontmatter strip,
heading-merge, metadata-filter, TOC promotion, mermaid extraction, outline
collection) are added in Plan 2 (this file currently performs only the
parse step; transformers are a separate module).
"""
from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.token import Token

from mdpdf.markdown.ast import (
    Block,
    BlockQuote,
    Code,
    CodeFence,
    Document,
    Emphasis,
    Heading,
    Image,
    Inline,
    Link,
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

_MERMAID_LANGS = {"mermaid", "mmd"}


def parse_markdown(source: str) -> Document:
    """Parse a markdown source string into a Document AST."""
    md = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
    tokens = md.parse(source)
    children = _convert_blocks(tokens, 0, len(tokens))
    return Document(children=children)


def _convert_blocks(tokens: list[Token], start: int, end: int) -> list[Block]:
    """Walk a token slice and emit block-level nodes."""
    out: list[Block] = []
    i = start
    while i < end:
        tok = tokens[i]
        match tok.type:
            case "heading_open":
                close = _find_close(tokens, i, "heading_close")
                level = int(tok.tag[1])  # "h1" → 1
                inline_children = _convert_inline(tokens, i + 1, close)
                out.append(Heading(level=level, children=inline_children))
                i = close + 1
            case "paragraph_open":
                close = _find_close(tokens, i, "paragraph_close")
                inline_children = _convert_inline(tokens, i + 1, close)
                out.append(Paragraph(children=inline_children))
                i = close + 1
            case "fence":
                lang = (tok.info or "").strip().split()[0] if tok.info else ""
                if lang.lower() in _MERMAID_LANGS:
                    out.append(MermaidBlock(source=tok.content))
                else:
                    out.append(CodeFence(lang=lang, content=tok.content))
                i += 1
            case "blockquote_open":
                close = _find_close(tokens, i, "blockquote_close")
                out.append(BlockQuote(children=_convert_blocks(tokens, i + 1, close)))
                i = close + 1
            case "bullet_list_open" | "ordered_list_open":
                ordered = tok.type == "ordered_list_open"
                close = _find_close(
                    tokens, i, "ordered_list_close" if ordered else "bullet_list_close"
                )
                items = _convert_list_items(tokens, i + 1, close)
                out.append(ListBlock(ordered=ordered, items=items))
                i = close + 1
            case "table_open":
                close = _find_close(tokens, i, "table_close")
                out.append(_convert_table(tokens, i + 1, close))
                i = close + 1
            case "hr":
                out.append(ThematicBreak())
                i += 1
            case _:
                # Unknown / unsupported block — skip silently in Plan 1.
                # Plan 2's transformers may handle additional cases (HTML).
                i += 1
    return out


def _convert_list_items(tokens: list[Token], start: int, end: int) -> list[ListItem]:
    items: list[ListItem] = []
    i = start
    while i < end:
        tok = tokens[i]
        if tok.type == "list_item_open":
            close = _find_close(tokens, i, "list_item_close")
            items.append(ListItem(children=_convert_blocks(tokens, i + 1, close)))
            i = close + 1
        else:
            i += 1
    return items


def _convert_table(tokens: list[Token], start: int, end: int) -> Table:
    header_row: TableRow | None = None
    body_rows: list[TableRow] = []
    in_header = False
    in_body = False
    i = start
    while i < end:
        tok = tokens[i]
        match tok.type:
            case "thead_open":
                in_header = True
            case "thead_close":
                in_header = False
            case "tbody_open":
                in_body = True
            case "tbody_close":
                in_body = False
            case "tr_open":
                close = _find_close(tokens, i, "tr_close")
                row = _convert_table_row(tokens, i + 1, close)
                if in_header:
                    header_row = row
                elif in_body:
                    body_rows.append(row)
                i = close
            case _:
                pass
        i += 1
    if header_row is None:
        header_row = TableRow(cells=[])
    return Table(header=header_row, rows=body_rows)


def _convert_table_row(tokens: list[Token], start: int, end: int) -> TableRow:
    cells: list[TableCell] = []
    i = start
    while i < end:
        tok = tokens[i]
        if tok.type in {"th_open", "td_open"}:
            close_type = "th_close" if tok.type == "th_open" else "td_close"
            close = _find_close(tokens, i, close_type)
            cells.append(TableCell(children=_convert_inline(tokens, i + 1, close)))
            i = close + 1
        else:
            i += 1
    return TableRow(cells=cells)


def _convert_inline(tokens: list[Token], start: int, end: int) -> list[Inline]:
    """Inline-token conversion. markdown-it nests inline content under an `inline` token."""
    out: list[Inline] = []
    for i in range(start, end):
        tok = tokens[i]
        if tok.type == "inline":
            out.extend(_walk_inline(tok.children or []))
    return out


def _walk_inline(children: list[Token]) -> list[Inline]:
    out: list[Inline] = []
    i = 0
    while i < len(children):
        tok = children[i]
        match tok.type:
            case "text":
                out.append(Text(content=tok.content))
            case "code_inline":
                out.append(Code(content=tok.content))
            case "strong_open":
                close = _find_close(children, i, "strong_close")
                out.append(Strong(children=_walk_inline(children[i + 1 : close])))
                i = close
            case "em_open":
                close = _find_close(children, i, "em_close")
                out.append(Emphasis(children=_walk_inline(children[i + 1 : close])))
                i = close
            case "link_open":
                close = _find_close(children, i, "link_close")
                href = _attr(tok, "href") or ""
                out.append(Link(href=href, children=_walk_inline(children[i + 1 : close])))
                i = close
            case "image":
                src = _attr(tok, "src") or ""
                alt = tok.content or ""
                out.append(Image(src=src, alt=alt))
            case "softbreak" | "hardbreak":
                out.append(Text(content="\n"))
            case _:
                # Unknown inline — skip silently in Plan 1.
                pass
        i += 1
    return out


def _attr(tok: Token, name: str) -> str | None:
    """Return the value of a token attribute, or None if missing."""
    if not tok.attrs:
        return None
    val = tok.attrs.get(name)
    if val is None:
        return None
    return str(val)


def _find_close(tokens: list[Token], open_idx: int, close_type: str) -> int:
    """Find the matching close token at the same nesting level."""
    depth = 0
    open_type = tokens[open_idx].type
    for j in range(open_idx + 1, len(tokens)):
        if tokens[j].type == open_type:
            depth += 1
        elif tokens[j].type == close_type:
            if depth == 0:
                return j
            depth -= 1
    raise ValueError(f"unmatched {open_type} at index {open_idx}")
