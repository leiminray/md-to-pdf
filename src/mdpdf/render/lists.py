"""AST ListBlock → ReportLab ListFlowable."""
from __future__ import annotations

from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import ListFlowable
from reportlab.platypus import ListItem as RLListItem
from reportlab.platypus import Paragraph as RLParagraph
from reportlab.platypus.flowables import Flowable

from mdpdf.markdown.ast import (
    Code,
    Emphasis,
    Image,
    Inline,
    Link,
    ListBlock,
    Paragraph,
    Strong,
    Text,
)


def _script_aware_style(text: str, base: ParagraphStyle) -> ParagraphStyle:
    """Swap fontName to a CJK font when text contains scripts the base font lacks."""
    from mdpdf.fonts.manager import select_cjk_font_for_text
    chosen = select_cjk_font_for_text(text)
    if chosen is None or chosen == base.fontName:
        return base
    return ParagraphStyle(
        name=f"{base.name}_{chosen}",
        parent=base,
        fontName=chosen,
    )


def _inline_plain(children: list[Inline]) -> str:
    """Flatten inline AST to plain text for script detection."""
    parts: list[str] = []
    for c in children:
        match c:
            case Text(content=t):
                parts.append(t)
            case Code(content=t):
                parts.append(t)
            case Strong(children=cs) | Emphasis(children=cs) | Link(children=cs):
                parts.append(_inline_plain(cs))
            case _:
                pass
    return "".join(parts)


def ast_list_to_flowable(lst: ListBlock, body: ParagraphStyle) -> Flowable:
    """Convert an AST ListBlock to a ReportLab ListFlowable, recursing for nests."""
    items: list[RLListItem] = []
    for ast_item in lst.items:
        children_flowables: list[Flowable] = []
        for child in ast_item.children:
            if isinstance(child, Paragraph):
                style = _script_aware_style(_inline_plain(child.children), body)
                children_flowables.append(
                    RLParagraph(_inline_to_html(child.children), style)
                )
            elif isinstance(child, ListBlock):
                children_flowables.append(ast_list_to_flowable(child, body))
            else:
                # Other block types inside list items (e.g., CodeFence, BlockQuote)
                # are rare; render as plain paragraph fallback.
                children_flowables.append(
                    RLParagraph(f"[{type(child).__name__}]", body)
                )
        items.append(RLListItem(children_flowables, leftIndent=12))
    # Cast to Flowable for reportlab-stubs compatibility (RLListItem is a Flowable).
    return ListFlowable(
        list(items),  # type: ignore[arg-type]
        bulletType="1" if lst.ordered else "bullet",
        leftIndent=18,
    )


def _inline_to_html(children: list[Inline]) -> str:
    parts: list[str] = []
    for child in children:
        match child:
            case Text(content=c):
                parts.append(escape(c))
            case Code(content=c):
                parts.append(f'<font face="Courier">{escape(c)}</font>')
            case Strong(children=cs):
                parts.append(f"<b>{_inline_to_html(cs)}</b>")
            case Emphasis(children=cs):
                parts.append(f"<i>{_inline_to_html(cs)}</i>")
            case Link(href=h, children=cs):
                parts.append(f'<link href="{escape(h)}">{_inline_to_html(cs)}</link>')
            case Image(alt=alt):
                parts.append(escape(alt))
            case _:
                parts.append("")
    return "".join(parts)
