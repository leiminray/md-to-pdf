"""RenderEngine abstract base class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from mdpdf.markdown.ast import Document


class RenderEngine(ABC):
    """Engine ABC — one impl in v0.2.1 (ReportLab); WeasyPrint deferred to v2.x.

    Implementations consume a fully-resolved Document AST and write the
    PDF bytes to `output`. Watermark/footer/issuer post-processing happens
    later in the pipeline  and is engine-agnostic.

    Returns the page count as an integer.
    """

    name: str = ""

    @abstractmethod
    def render(self, document: Document, output: Path) -> int:
        """Render `document` to a PDF at `output`. Returns page count."""
