"""ReportLab rendering engine.

Accepts BrandStyles for brand-aware rendering.
The Pipeline  constructs BrandStyles after brand resolution and
passes it to the engine via constructor injection.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, B5, LEGAL, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph as RLParagraph
from reportlab.platypus import SimpleDocTemplate, Spacer, TableStyle
from reportlab.platypus import Table as RLTable
from reportlab.platypus.flowables import Flowable

from mdpdf.brand.styles import BrandStyles
from mdpdf.cache.tempfiles import atomic_write
from mdpdf.markdown.ast import (
    Block,
    BlockQuote,
    CodeFence,
    Document,
    Emphasis,
    Heading,
    Inline,
    Link,
    ListBlock,
    MermaidBlock,
    OutlineEntry,
    Paragraph,
    Strong,
    Text,
)
from mdpdf.markdown.ast import Image as ASTImage
from mdpdf.markdown.ast import Table as ASTTable
from mdpdf.markdown.transformers.collect_outline import _inline_to_plain
from mdpdf.render.engine_base import RenderEngine
from mdpdf.render.flowables import CalloutBox, FencedCodeCard, MermaidImage
from mdpdf.render.lists import ast_list_to_flowable
from mdpdf.render.outline import HeadingBookmark
from mdpdf.render.tables import compute_column_widths
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.code_pygments import CodeRenderer
from mdpdf.renderers.image import ImageRenderer
from mdpdf.renderers.mermaid_chain import select_mermaid_renderer

_PAGE_SIZES = {"A4": A4, "Letter": LETTER, "B5": B5, "Legal": LEGAL}


class ReportLabEngine(RenderEngine):
    name = "reportlab"

    def __init__(self, brand_styles: BrandStyles | None = None) -> None:
        self._brand_styles = brand_styles or _default_styles()
        self._style_cache: dict[tuple[str, str], ParagraphStyle] = {}

    def _style_for_text(
        self, text: str, base: ParagraphStyle
    ) -> ParagraphStyle:
        """Return a style with `fontName` swapped to a script-appropriate
        CJK font when *text* contains characters the base font may lack
        (e.g., Korean Hangul or Japanese kana).
        """
        from mdpdf.fonts.manager import select_cjk_font_for_text
        chosen = select_cjk_font_for_text(text)
        if chosen is None or chosen == base.fontName:
            return base
        cache_key = (base.name, chosen)
        if cache_key in self._style_cache:
            return self._style_cache[cache_key]
        # Clone the base style and swap fontName
        cloned = ParagraphStyle(
            name=f"{base.name}_{chosen}",
            parent=base,
            fontName=chosen,
        )
        self._style_cache[cache_key] = cloned
        return cloned

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
        consumed: set[str] = set()

        def _next_entry_for(plain: str) -> OutlineEntry | None:
            for entry in document.outline:
                if entry.plain_text == plain and entry.bookmark_id not in consumed:
                    consumed.add(entry.bookmark_id)
                    return entry
            return None

        for node in document.children:
            flowables = self._convert_block(node, body)
            if isinstance(node, Heading) and flowables:
                plain = _inline_to_plain(node.children)
                entry = _next_entry_for(plain)
                if entry is not None:
                    flowables[0] = HeadingBookmark(inner=flowables[0], entry=entry)
            out.extend(flowables)
        return out

    def _convert_block(self, node: Block, body: ParagraphStyle) -> list[Flowable]:
        if isinstance(node, Paragraph):
            if len(node.children) == 1 and isinstance(node.children[0], ASTImage):
                return self._convert_block(node.children[0], body)
            html = self._inline_to_html(node.children)
            style = self._style_for_text(_inline_to_plain(node.children), body)
            return [RLParagraph(html, style)]
        if isinstance(node, Heading):
            level = max(1, min(node.level, 6))
            base_style = self._brand_styles.paragraph_styles[f"H{level}"]
            html = self._inline_to_html(node.children)
            style = self._style_for_text(_inline_to_plain(node.children), base_style)
            return [RLParagraph(html, style)]
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
            body_font = code_style.fontName
            # Auto-fallback to CJK font when code contains CJK characters
            # (most monospace fonts like Courier lack CJK glyphs).
            from mdpdf.fonts.manager import select_cjk_font_for_text
            cjk_fallback = select_cjk_font_for_text(node.content)
            if cjk_fallback is not None:
                body_font = cjk_fallback
            return [FencedCodeCard(
                result=result,
                accent_color=str(accent.hexval()) if hasattr(accent, "hexval") else "#0066CC",
                body_font=body_font,
                body_font_size=int(code_style.fontSize),
                line_numbers=False,
            )]
        if isinstance(node, MermaidBlock):
            mctx = RenderContext(
                cache_root=Path.home() / ".md-to-pdf" / "cache",
                brand_pack=None,
                allow_remote_assets=False,
                deterministic=False,
            )
            mermaid_renderer = select_mermaid_renderer(preference="auto", ctx=mctx)
            png_path = mermaid_renderer.render(node.source, mctx)
            return [MermaidImage(image_path=png_path, caption=None)]
        if isinstance(node, ASTImage):
            img_ctx = RenderContext(
                cache_root=Path.home() / ".md-to-pdf" / "cache",
                brand_pack=None,
                allow_remote_assets=False,
                deterministic=False,
            )
            img_result = ImageRenderer().render(node, img_ctx)
            max_width_mm = 170  # leave margin; 1px = 1pt at 72dpi
            scale = min(1.0, (max_width_mm * mm) / img_result.width_px)
            return [RLImage(
                str(img_result.path),
                width=img_result.width_px * scale,
                height=img_result.height_px * scale,
            )]
        if isinstance(node, ASTTable):
            cells_text: list[list[str]] = []
            header_text = [self._inline_to_html(c.children) for c in node.header.cells]
            cells_text.append(list(header_text))
            for row in node.rows:
                cells_text.append([self._inline_to_html(c.children) for c in row.cells])
            # P3-006: Use the actual page width for the current brand (default A4 = 210mm).
            _page_w_pt = _PAGE_SIZES.get(self._brand_styles.page_size, A4)[0]
            _margins_pt = (self._brand_styles.left_margin + self._brand_styles.right_margin) * mm
            available_pt = _page_w_pt - _margins_pt
            widths = compute_column_widths(cells_text, available_width_pt=available_pt)
            rl_data = [[RLParagraph(t, body) for t in row] for row in cells_text]
            tbl = RLTable(rl_data, colWidths=widths)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f3f4f6")),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            return [tbl]
        if isinstance(node, ListBlock):
            return [ast_list_to_flowable(node, body)]
        if isinstance(node, BlockQuote):
            inner_flowables: list[Flowable] = []
            for child in node.children:
                inner_flowables.extend(self._convert_block(child, body))
            accent = self._brand_styles.paragraph_styles["H1"].textColor
            return [CalloutBox(
                body=inner_flowables,
                accent_color=str(accent.hexval()) if hasattr(accent, "hexval") else "#0066CC",
            )]
        # Additional AST node types are handled by dedicated renderers.
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
    """Minimal styles when no brand is supplied (compat fallback)."""
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
