"""Custom ReportLab Flowables (spec §2.1.5).

This module hosts the brand-styled Flowables used by `engine_reportlab`:
- FencedCodeCard: code fences with lang badge + accent bar + line numbers
- MermaidImage:   diagram PNG with optional caption (Task 13)
- CalloutBox:     bordered card for blockquotes (Task 16)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Spacer, Table, TableStyle
from reportlab.platypus import Paragraph as RLParagraph

from mdpdf.renderers.code_pygments import CodeRenderResult


@dataclass
class FencedCodeCard(Flowable):
    """A code-fence flowable with lang badge, left accent bar, optional line numbers."""

    result: CodeRenderResult
    accent_color: str = "#0066CC"
    body_font: str = "Courier"
    body_font_size: int = 9
    line_numbers: bool = False
    badge_font_size: int = 7

    def __post_init__(self) -> None:
        # ReportLab Flowable base does not use __init__ args we need; init manually.
        Flowable.__init__(self)
        self._table: Table | None = None
        self._build()

    def _build(self) -> None:
        body_style = ParagraphStyle(
            name="FencedBody",
            fontName=self.body_font,
            fontSize=self.body_font_size,
            leading=int(self.body_font_size * 1.4),
            textColor=HexColor("#1f2328"),
            wordWrap="CJK",
        )
        gutter_style = ParagraphStyle(
            name="FencedGutter",
            fontName=self.body_font,
            fontSize=self.body_font_size,
            leading=int(self.body_font_size * 1.4),
            textColor=HexColor("#6e7781"),
            alignment=2,  # right-aligned
        )

        # Build per-line HTML once.
        body_lines: list[str] = []
        for line_frags in self.result.lines:
            html_parts: list[str] = []
            for frag in line_frags:
                html_parts.append(
                    f'<font color="{frag.color}">{escape(frag.text) or " "}</font>'
                )
            body_lines.append("".join(html_parts) or " ")

        rows: list[list[Flowable | str]] = []
        if self.result.lang:
            badge = RLParagraph(
                f'<font color="#6e7781" size="{self.badge_font_size}">{self.result.lang}</font>',
                ParagraphStyle(name="LangBadge", alignment=2, fontName=self.body_font),
            )
            rows.append(["", badge])
            rows.append(["", Spacer(1, 2)])

        # Chunk the body into N-line groups so the wrapping Table has multiple
        # rows it can split between, instead of one giant Paragraph that
        # ReportLab can't break across pages. Tables only split between rows.
        chunk_size = 30
        for start in range(0, len(body_lines), chunk_size):
            chunk_html = "<br/>".join(body_lines[start : start + chunk_size])
            chunk_paragraph = RLParagraph(chunk_html, body_style)
            if self.line_numbers:
                end = min(start + chunk_size, len(body_lines))
                gutter_html = "<br/>".join(str(i + 1) for i in range(start, end))
                rows.append([RLParagraph(gutter_html, gutter_style), chunk_paragraph])
            else:
                rows.append(["", chunk_paragraph])

        col_widths: list[float] = (
            [9 * mm, None]  # type: ignore[list-item]
            if self.line_numbers
            else [3 * mm, None]  # type: ignore[list-item]
        )

        table = Table(rows, colWidths=col_widths)
        table.setStyle(TableStyle([
            ("LINEBEFORE", (0, 0), (0, -1), 2, HexColor(self.accent_color)),
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#f6f8fa")),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        self._table = table

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        assert self._table is not None  # noqa: S101 — type narrow for mypy
        return self._table.wrap(available_width, available_height)

    def draw(self) -> None:
        assert self._table is not None  # noqa: S101 — type narrow for mypy
        self._table.canv = self.canv
        self._table.drawOn(self.canv, 0, 0)

    def split(self, available_width: float, available_height: float) -> list[Flowable]:
        """Delegate splitting to the inner Table so long code blocks can span
        pages. Without this, a code fence taller than the remaining page area
        triggers ReportLab's "Flowable too large" LayoutError instead of
        being broken across pages.
        """
        assert self._table is not None  # noqa: S101
        return list(self._table.split(available_width, available_height))


@dataclass
class MermaidImage(Flowable):
    """Mermaid diagram PNG with optional caption."""

    image_path: Path
    caption: str | None = None
    max_width_mm: int = 170
    caption_font_size: int = 8

    def __post_init__(self) -> None:
        Flowable.__init__(self)
        from PIL import Image as PILImage
        with PILImage.open(self.image_path) as img:
            self._w_px, self._h_px = img.size
        self._table: Table | None = None
        self._build()

    def _build(self) -> None:
        from reportlab.platypus import Image as RLImage
        max_width_pt = self.max_width_mm * mm
        scale = min(1.0, max_width_pt / self._w_px)
        img = RLImage(
            str(self.image_path),
            width=self._w_px * scale,
            height=self._h_px * scale,
        )
        rows: list[list[Flowable]] = [[img]]
        if self.caption:
            cap_style = ParagraphStyle(
                name="MermaidCaption",
                fontName="Helvetica-Oblique",
                fontSize=self.caption_font_size,
                textColor=HexColor("#6e7781"),
                alignment=1,  # centre
                spaceBefore=2,
            )
            rows.append([RLParagraph(self.caption, cap_style)])
        # KeepInFrame-like: a single-column Table keeps image+caption together
        # within the parent frame (Table won't split mid-row without explicit
        # splitByRow), giving us atomic placement.
        self._table = Table(rows, colWidths=[max_width_pt])
        self._table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        assert self._table is not None  # noqa: S101 — type narrow for mypy
        return self._table.wrap(available_width, available_height)

    def draw(self) -> None:
        assert self._table is not None  # noqa: S101 — type narrow for mypy
        self._table.canv = self.canv
        self._table.drawOn(self.canv, 0, 0)


@dataclass
class CalloutBox(Flowable):
    """Bordered card for blockquotes (spec §2.1.5).

    Optional left-edge accent bar in brand colour. Body is a list of
    Flowables (paragraphs, lists, etc.) that get wrapped in a Table.
    """

    body: list[Flowable]
    accent_color: str = "#0066CC"
    background_color: str = "#f6f8fa"
    border_color: str = "#dbe3ea"

    def __post_init__(self) -> None:
        Flowable.__init__(self)
        self._table: Table | None = None
        self._build()

    def _build(self) -> None:
        rows: list[list[Flowable | str]] = [["", body_item] for body_item in self.body]
        if not rows:
            rows = [["", Spacer(1, 1)]]
        self._table = Table(
            rows,
            colWidths=[3 * mm, None],
        )
        self._table.setStyle(TableStyle([
            ("LINEBEFORE", (0, 0), (0, -1), 2, HexColor(self.accent_color)),
            ("BACKGROUND", (1, 0), (-1, -1), HexColor(self.background_color)),
            ("BOX", (1, 0), (-1, -1), 0.5, HexColor(self.border_color)),
            ("LEFTPADDING", (1, 0), (-1, -1), 6),
            ("RIGHTPADDING", (1, 0), (-1, -1), 6),
            ("TOPPADDING", (1, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (1, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))

    def wrap(self, aw: float, ah: float) -> tuple[float, float]:
        assert self._table is not None  # noqa: S101 — type narrow for mypy
        return self._table.wrap(aw, ah)

    def draw(self) -> None:
        assert self._table is not None  # noqa: S101 — type narrow for mypy
        self._table.canv = self.canv
        self._table.drawOn(self.canv, 0, 0)
