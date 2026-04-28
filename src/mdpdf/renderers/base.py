"""Renderer ABC.

A `Renderer[SourceT, OutputT]` consumes a source value (a CodeFence's text,
a MermaidBlock's source, an Image's path) plus a `RenderContext` (cache,
brand, security flags) and produces a typed output (e.g., a `Path` to a
generated PNG, or a list of (token, color) tuples).

Concrete implementations live next to this module: `mermaid_kroki.py`,
`mermaid_puppeteer.py`, `mermaid_pure.py`, `code_pygments.py`, `image.py`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from mdpdf.brand.schema import BrandPack

SourceT = TypeVar("SourceT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class RenderContext:
    """Shared context for one Pipeline.render() invocation."""

    cache_root: Path
    brand_pack: BrandPack | None
    allow_remote_assets: bool
    deterministic: bool


class Renderer(ABC, Generic[SourceT, OutputT]):
    """Abstract base for content-renderer plugins."""

    name: str = ""

    @abstractmethod
    def render(self, source: SourceT, ctx: RenderContext) -> OutputT:
        """Produce the rendered output for `source` under `ctx`."""
