"""Mermaid input sandbox.

Rejects sources that exceed resource limits OR contain XSS / injection
patterns. Runs BEFORE dispatching to any renderer (Kroki, Puppeteer, pure)
so the same security guarantee applies regardless of execution path.
"""
from __future__ import annotations

import re

from mdpdf.errors import RendererError

_MAX_CHARS = 50_000
_MAX_NODES = 500
_MAX_NEST = 10

_PATTERNS_BAD = [
    (re.compile(r"click\s+\S+\s+callback\s+javascript:", re.IGNORECASE),
     "click callback with javascript: scheme"),
    (re.compile(r"<\s*script\b", re.IGNORECASE), "raw <script> tag"),
    (re.compile(r"\bstyle\s*=\s*['\"][^'\"]*url\s*\(", re.IGNORECASE),
     "inline style attribute with url() reference"),
    (re.compile(r"<\s*img\b[^>]*\bsrc\s*=\s*['\"]https?://", re.IGNORECASE),
     "img tag with remote src"),
    (re.compile(r"\bjavascript:", re.IGNORECASE), "javascript: URI"),
]


def lint_mermaid_source(source: str) -> None:
    """Raise RendererError if the source is unsafe or oversized."""
    if len(source) > _MAX_CHARS:
        raise RendererError(
            code="MERMAID_RESOURCE_LIMIT",
            user_message=(
                f"mermaid source ({len(source)} chars) exceeds the {_MAX_CHARS}-char limit"
            ),
        )

    arrow_count = len(re.findall(r"-->|--|---|==>", source))
    node_count = arrow_count * 2  # rough upper bound
    if node_count > _MAX_NODES:
        raise RendererError(
            code="MERMAID_RESOURCE_LIMIT",
            user_message=(
                f"mermaid diagram has approximately {node_count} nodes; "
                f"limit is {_MAX_NODES}"
            ),
        )

    nest = 0
    max_nest = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("subgraph"):
            nest += 1
            max_nest = max(max_nest, nest)
        elif stripped == "end":
            nest = max(0, nest - 1)
    if max_nest > _MAX_NEST:
        raise RendererError(
            code="MERMAID_RESOURCE_LIMIT",
            user_message=(
                f"mermaid subgraph nesting depth {max_nest} exceeds the {_MAX_NEST}-level limit"
            ),
        )

    for pat, description in _PATTERNS_BAD:
        if pat.search(source):
            raise RendererError(
                code="MERMAID_INVALID_SYNTAX",
                user_message=f"mermaid source rejected by sandbox: {description}",
            )
