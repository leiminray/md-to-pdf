"""Strip a leading FrontMatter node from a Document (spec §2.1.3).

Front-matter parsed by markdown-it-py is captured as a `FrontMatter` AST
node. This transformer removes it from the rendered body — brand /
template layers may have already consumed the `raw` text via a different
path (e.g., explicit pre-pipeline parse).
"""
from __future__ import annotations

from mdpdf.markdown.ast import Document, FrontMatter


def strip_yaml_frontmatter(document: Document) -> Document:
    if not document.children:
        return document
    if not isinstance(document.children[0], FrontMatter):
        return document
    return Document(children=document.children[1:])
