"""Filter metadata blocks (specification,  default-strip behaviour).

Removes:
1. A leading bullet list (right at document start, optionally after the H1)
   whose every item is a paragraph beginning with `Key: value` shape, where
   Key is one or two capitalised words (Author, Date, Version, Reviewer,
   Last Updated, etc.).
2. The `## Contributor Roles` (or `## Contributor Role`) section and every
   block below it up to the next heading at level <= 2 (which means: until
   the next h1 or h2). Case-insensitive heading match.

CLI `--no-filter` flag (Task 18) bypasses this transformer.
"""
from __future__ import annotations

import re

from mdpdf.markdown.ast import (
    Block,
    Document,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    Text,
)

_METADATA_KEY = re.compile(r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+){0,3}:\s")
_CONTRIBUTOR_HEADING = re.compile(r"^contributor\s+roles?$", re.IGNORECASE)


def filter_metadata_blocks(document: Document) -> Document:
    children = list(document.children)
    changed = False

    # Pass 1: strip leading metadata bullet list.
    # Allow at most one Heading(level=1) before it.
    cursor = 0
    if (
        cursor < len(children)
        and isinstance(children[cursor], Heading)
        and children[cursor].level == 1  # type: ignore[union-attr]
    ):
        cursor += 1
    if cursor < len(children) and _is_metadata_list(children[cursor]):
        del children[cursor]
        changed = True

    # Pass 2: strip Contributor Roles section.
    out: list[Block] = []
    skipping = False
    for node in children:
        if skipping:
            if isinstance(node, Heading) and node.level <= 2:
                # End of the skipped section; this heading survives.
                skipping = False
                out.append(node)
            # else: still inside the skipped section
            continue
        if (
            isinstance(node, Heading)
            and len(node.children) == 1
            and isinstance(node.children[0], Text)
            and _CONTRIBUTOR_HEADING.match(node.children[0].content.strip())
        ):
            skipping = True
            changed = True
            continue
        out.append(node)

    if not changed:
        return document
    return Document(children=out)


def _is_metadata_list(node: Block) -> bool:
    if not isinstance(node, ListBlock):
        return False
    if node.ordered:
        return False
    if not node.items:
        return False
    return all(_item_starts_with_metadata_key(item) for item in node.items)


def _item_starts_with_metadata_key(item: ListItem) -> bool:
    if not item.children:
        return False
    first = item.children[0]
    if not isinstance(first, Paragraph):
        return False
    if not first.children or not isinstance(first.children[0], Text):
        return False
    return bool(_METADATA_KEY.match(first.children[0].content))
