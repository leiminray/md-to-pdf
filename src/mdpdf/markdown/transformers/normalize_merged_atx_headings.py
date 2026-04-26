"""Split run-on ATX headings like `# Part## Chapter` into two heading nodes.

v1.8.9 parity behaviour. Conservative: only splits when:
- the heading's only child is a single Text node
- the text contains a substring `##+` (two or more hashes) at a position
  that would form a higher-level heading (level + N where N >= 1)

If the heading already contains formatting (Strong, Emphasis, Code), it is
left alone — splitting would be ambiguous.
"""
from __future__ import annotations

import re

from mdpdf.markdown.ast import Block, Document, Heading, Text

# Match `##+ ` followed by content. Group 1: hashes, Group 2: rest.
_RUN_ON = re.compile(r"(#{2,})\s*(.+)$")


def normalize_merged_atx_headings(document: Document) -> Document:
    out_children: list[Block] = []
    changed = False
    for node in document.children:
        if not _is_splittable(node):
            out_children.append(node)
            continue
        # _is_splittable narrows to Heading with [Text] child; re-narrow for mypy.
        if not isinstance(node, Heading):
            out_children.append(node)
            continue
        first = node.children[0]
        if not isinstance(first, Text):
            out_children.append(node)
            continue
        text = first.content
        m = _RUN_ON.search(text)
        if m is None:
            out_children.append(node)
            continue
        n_hashes = len(m.group(1))
        # ATX semantics: `##` = absolute level 2 regardless of parent heading.
        # Run-on must produce a strictly deeper level than the parent.
        new_level = n_hashes
        if new_level <= node.level or new_level > 6:
            out_children.append(node)
            continue
        head_text = text[: m.start()].rstrip()
        tail_text = m.group(2).strip()
        if not head_text or not tail_text:
            out_children.append(node)
            continue
        out_children.append(
            Heading(level=node.level, children=[Text(content=head_text)])
        )
        out_children.append(
            Heading(level=new_level, children=[Text(content=tail_text)])
        )
        changed = True
    if not changed:
        return document
    return Document(children=out_children)


def _is_splittable(node: Block) -> bool:
    if not isinstance(node, Heading):
        return False
    if len(node.children) != 1:
        return False
    return isinstance(node.children[0], Text)
