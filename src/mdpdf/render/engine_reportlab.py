"""ReportLab rendering engine.

Plan 2 changes: accepts BrandStyles instead of getSampleStyleSheet().
The Pipeline (Plan 2) constructs BrandStyles after brand resolution and
passes it to the engine via constructor injection.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, B5, LEGAL, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph as RLParagraph
from reportlab.platypus import SimpleDocTemplate, Spacer
from reportlab.platypus.flowables import Flowable

from mdpdf.brand.styles import BrandStyles
from mdpdf.cache.tempfiles import atomic_write
from mdpdf.markdown.ast import (
    Block,
    CodeFence,
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
from mdpdf.render.flowables import FencedCodeCard
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.code_pygments import CodeRenderer

_PAGE_SIZES = {"A4": A4, "Letter": LETTER, "B5": B5, "Legal": LEGAL}


class ReportLabEngine(RenderEngine):
    name = "reportlab"

    def __init__(self, brand_styles: BrandStyles | None = None) -> None:
        # Allow None for back-compat with Plan 1 minimal tests, in which
        # case we synthesise a minimal default. Pipeline always passes
        # brand_styles in Plan 2+.
        self._brand_styles = brand_styles or _default_styles()

    def render(self, document: Document, output: Path) -> int:
        flowables = self._convert(document)
        if not flowables:
            flowables = [Spacer(1, 1)]
        page_count = [0]

        def _on_page(canvas, doc):  # type: ignore[no-untyped-def]
            page_count[0] += 1

        with atomic_write(output) as fp:
            doc = SimpleDocTemplate(
                fp,
                pagesize=_PAGE_SIZES.get(self._brand_styles.page_size, A4),
                leftMargin=self._brand_styles.left_margin * mm,
                rightMargin=self._brand_styles.right_margin * mm,
                topMargin=self._brand_styles.top_margin * mm,
                bottomMargin=self._brand_styles.bottom_margin * mm,
            )
            doc.build(flowables, onFirstPage=_on_page, onLaterPages=_on_page)
        return max(page_count[0], 1)

    def _convert(self, document: Document) -> list[Flowable]:
        body = self._brand_styles.paragraph_styles["Body"]
        out: list[Flowable] = []
        for node in document.children:
            out.extend(self._convert_block(node, body))
        return out

    def _convert_block(self, node: Block, body: ParagraphStyle) -> list[Flowable]:
        if isinstance(node, Paragraph):
            return [RLParagraph(self._inline_to_html(node.children), body)]
        if isinstance(node, Heading):
            level = max(1, min(node.level, 6))
            style = self._brand_styles.paragraph_styles[f"H{level}"]
            return [RLParagraph(self._inline_to_html(node.children), style)]
        if isinstance(node, CodeFence):
            ctx = RenderContext(
                cache_root=Path.home() / ".md-to-pdf" / "cache",
                brand_pack=None,
                allow_remote_assets=False,
                deterministic=False,
            )
            result = CodeRenderer().render(node, ctx)
            code_style = self._brand_styles.paragraph_styles["Code"]
            accent = code_style.textColor
            return [FencedCodeCard(
                result=result,
                accent_color=str(accent.hexval()) if hasattr(accent, "hexval") else "#0066CC",
                body_font=code_style.fontName,
                body_font_size=int(code_style.fontSize),
                line_numbers=False,
            )]
        # Other AST node types remain Plan 3 territory until subsequent tasks land.
        unsupported = ParagraphStyle(
            "Unsupported",
            parent=body,
            textColor=HexColor("#aa0000"),
            fontName="Courier",
            fontSize=9,
        )
        return [RLParagraph(f"[unsupported: {type(node).__name__}]", unsupported)]

    @staticmethod
    def _inline_to_html(children: list[Inline]) -> str:
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
                    inner = ReportLabEngine._inline_to_html(cs)
                    parts.append(f'<link href="{escape(h)}">{inner}</link>')
                case _:
                    parts.append(f"[{type(child).__name__}]")
        return "".join(parts)


def _default_styles() -> BrandStyles:
    """Minimal styles when no brand is supplied (Plan 1 walking-skeleton compat)."""
    body = ParagraphStyle(
        name="Body", fontName="Helvetica", fontSize=11, leading=16, wordWrap="CJK",
    )
    h_styles = {
        f"H{i}": ParagraphStyle(
            name=f"H{i}", parent=body, fontName="Helvetica-Bold",
            fontSize=max(10, 22 - i * 2), leading=int(max(10, 22 - i * 2) * 1.4),
        )
        for i in range(1, 7)
    }
    return BrandStyles(
        paragraph_styles={"Body": body, "Code": body, **h_styles},
        page_size="A4", left_margin=18, right_margin=18, top_margin=22, bottom_margin=32,
    )
