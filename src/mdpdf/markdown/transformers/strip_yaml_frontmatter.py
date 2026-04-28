"""Strip a leading FrontMatter node from a Document.

Front-matter parsed by markdown-it-py is captured as a `FrontMatter` AST
node. This transformer removes it from the rendered body and parses the
YAML content into document.metadata — brand / template layers may have
already consumed the `raw` text via a different path (e.g., explicit
pre-pipeline parse).
"""
from __future__ import annotations

import yaml

from mdpdf.markdown.ast import Document, FrontMatter


def strip_yaml_frontmatter(document: Document) -> Document:
    if not document.children:
        return document
    if not isinstance(document.children[0], FrontMatter):
        return document

    # Extract and parse frontmatter YAML
    frontmatter_node = document.children[0]
    try:
        metadata = yaml.safe_load(frontmatter_node.raw) or {}
        if isinstance(metadata, dict):
            document.metadata.update(metadata)
    except yaml.YAMLError:
        # If YAML parsing fails, leave metadata unchanged
        pass

    # Remove frontmatter from children
    return Document(
        children=document.children[1:],
        outline=document.outline,
        metadata=document.metadata,
    )
