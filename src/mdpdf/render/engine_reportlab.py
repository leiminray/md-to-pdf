"""ReportLab rendering engine (Plan 1 minimal: headings + paragraphs).

Plan 3 extends with tables, code, mermaid, images, lists, blockquotes.
Plan 2 wires brand-driven styles. For now the engine uses ReportLab's
sample stylesheet so the walking skeleton produces a recognisable PDF.
"""
from __future__ import annotations

from pathlib import Path
from typing import cast
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph as RLParagraph
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.platypus.flowables import Flowable

from mdpdf.markdown.ast import (
    Block,
    Document,
    Emphasis,
    Heading,
    Inline,
    Link,
    Paragraph,
    Strong,
    Text,
)
from mdpdf.render.engine_base import RenderEngine


class ReportLabEngine(RenderEngine):
    """Default engine — code-defined layout, A4, sample stylesheet."""

    name = "reportlab"

    def render(self, document: Document, output: Path) -> int:
        from mdpdf.cache.tempfiles import atomic_write

        flowables = self._convert(document)
        if not flowables:
            flowables = [Spacer(1, 1)]

        page_count = [0]

        def _on_page(canvas, doc):  # type: ignore[no-untyped-def]
            page_count[0] += 1

        with atomic_write(output) as fp:
            doc = SimpleDocTemplate(
                fp,
                pagesize=A4,
                leftMargin=18 * mm,
                rightMargin=18 * mm,
                topMargin=22 * mm,
                bottomMargin=32 * mm,
            )
            doc.build(flowables, onFirstPage=_on_page, onLaterPages=_on_page)
        return max(page_count[0], 1)

    # --- AST → flowables ---

    def _convert(self, document: Document) -> list[Flowable]:
        styles = getSampleStyleSheet()
        # ReportLab's `getSampleStyleSheet()` returns a StyleSheet1 whose
        # `__getitem__` is typed as `PropertySet` (the common ancestor); the
        # actual instances are `ParagraphStyle`. Narrow with cast.
        body_style = cast(ParagraphStyle, styles["BodyText"])
        h_styles = {
            i: ParagraphStyle(
                f"H{i}",
                parent=cast(
                    ParagraphStyle,
                    styles[f"Heading{i}"] if i <= 4 else styles["Heading4"],
                ),
            )
            for i in range(1, 7)
        }
        unsupported_style = ParagraphStyle(
            "Unsupported",
            parent=body_style,
            textColor=HexColor("#aa0000"),
            fontName="Courier",
            fontSize=9,
        )

        out: list[Flowable] = []
        for node in document.children:
            out.extend(self._convert_block(node, body_style, h_styles, unsupported_style))
        return out

    def _convert_block(
        self,
        node: Block,
        body_style: ParagraphStyle,
        h_styles: dict[int, ParagraphStyle],
        unsupported_style: ParagraphStyle,
    ) -> list[Flowable]:
        if isinstance(node, Paragraph):
            return [RLParagraph(self._inline_to_html(node.children), body_style)]
        if isinstance(node, Heading):
            level = max(1, min(node.level, 6))
            return [RLParagraph(self._inline_to_html(node.children), h_styles[level])]
        # Plan 1 placeholder for everything else.
        type_name = type(node).__name__
        return [RLParagraph(f"[unsupported: {type_name}]", unsupported_style)]

    @staticmethod
    def _inline_to_html(children: list[Inline]) -> str:
        """Flatten inline nodes into the minimal HTML subset ReportLab Paragraph supports."""
        parts: list[str] = []
        for child in children:
            match child:
                case Text(content=c):
                    parts.append(escape(c))
                case Strong(children=cs):
                    parts.append(f"<b>{ReportLabEngine._inline_to_html(cs)}</b>")
                case Emphasis(children=cs):
                    parts.append(f"<i>{ReportLabEngine._inline_to_html(cs)}</i>")
                case Link(href=h, children=cs):
                    parts.append(
                        f'<link href="{escape(h)}">{ReportLabEngine._inline_to_html(cs)}</link>'
                    )
                case _:
                    # Inline Code, Image are Plan 3.
                    parts.append(f"[{type(child).__name__}]")
        return "".join(parts)
