"""Promote a `## 目录` / `## Table of Contents` block to right after the H1.

parity: the TOC heading and its immediately-following block (a pipe
table or paragraph) get cut from their original position and re-inserted
at position 1 (right after the H1). Without an H1 in the document, the
transformer is a no-op (defensive — TOC needs an anchor).

Internal-PDF-link generation against headings is deferred
(`render/outline.py` consumes the `collect_outline` map and rewrites the
TOC table cells into `<link>` runs).
"""
from __future__ import annotations

from mdpdf.markdown.ast import Block, Document, Heading, Text

_TOC_TITLES = {"目录", "table of contents"}


def promote_toc(document: Document) -> Document:
    children = list(document.children)
    h1_idx = _find_h1(children)
    if h1_idx is None:
        return document
    toc_idx = _find_toc(children, after=h1_idx)
    if toc_idx is None:
        return document
    if toc_idx == h1_idx + 1:
        return document  # already in place

    # Cut TOC heading + next block (if present and not another heading at lvl <= 2)
    toc_block: list[Block] = [children[toc_idx]]
    after = toc_idx + 1
    if after < len(children):
        nxt = children[after]
        if not (isinstance(nxt, Heading) and nxt.level <= 2):
            toc_block.append(nxt)

    # Remove from original position
    for _ in toc_block:
        children.pop(toc_idx)

    # Insert after H1
    new_children = children[: h1_idx + 1] + toc_block + children[h1_idx + 1:]
    return Document(children=new_children)


def _find_h1(children: list[Block]) -> int | None:
    for i, c in enumerate(children):
        if isinstance(c, Heading) and c.level == 1:
            return i
    return None


def _find_toc(children: list[Block], *, after: int) -> int | None:
    for i in range(after + 1, len(children)):
        c = children[i]
        if (
            isinstance(c, Heading)
            and len(c.children) == 1
            and isinstance(c.children[0], Text)
            and c.children[0].content.strip().lower() in _TOC_TITLES
        ):
            return i
    return None
