"""AST transformer chain (spec §2.1.3).

Transformers are pure functions `Document → Document`. The chain runner
applies them in order; any transformer may return the same instance
(passthrough) or a new Document (replacement). The chain is sequential,
not parallel, because later transformers may depend on earlier results
(e.g., `promote_toc` runs after `filter_metadata_blocks`).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable

from mdpdf.markdown.ast import Document

Transformer = Callable[[Document], Document]


def run_transformers(document: Document, transformers: Iterable[Transformer]) -> Document:
    """Apply transformers in order; return the final Document."""
    out = document
    for t in transformers:
        out = t(out)
    return out
