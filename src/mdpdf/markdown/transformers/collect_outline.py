"""Build a heading outline for PDF bookmarks + TOC links.

Walks the document, extracts plain text from each Heading's inline children,
clamps level jumps to ≤ +1 (ReportLab outline restriction — child levels
must increase by exactly 1, not skip), and assigns unique sequential
bookmark ids of the form `ids-h-<n>`.

The result is attached to `Document.outline` (a list of OutlineEntry).
The original `children` are preserved unchanged.
"""
from __future__ import annotations

from mdpdf.markdown.ast import (
    Code,
    Document,
    Emphasis,
    Heading,
    Image,
    Inline,
    Link,
    OutlineEntry,
    Strong,
    Text,
)


def collect_outline(document: Document) -> Document:
    entries: list[OutlineEntry] = []
    last_level = 0
    counter = 0
    for node in document.children:
        if not isinstance(node, Heading):
            continue
        clamped = min(node.level, last_level + 1) if last_level else min(node.level, 1)
        counter += 1
        entries.append(OutlineEntry(
            bookmark_id=f"ids-h-{counter}",
            level=clamped,
            plain_text=_inline_to_plain(node.children),
        ))
        last_level = clamped
    if not entries and not document.outline:
        return document
    return Document(children=document.children, outline=entries)


def _inline_to_plain(children: list[Inline]) -> str:
    parts: list[str] = []
    for c in children:
        match c:
            case Text(content=t):
                parts.append(t)
            case Code(content=t):
                parts.append(t)
            case Emphasis(children=cs) | Strong(children=cs) | Link(children=cs):
                parts.append(_inline_to_plain(cs))
            case Image(alt=alt):
                parts.append(alt)
            case _:
                pass
    return "".join(parts).strip()
