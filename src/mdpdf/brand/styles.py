"""Build ReportLab ParagraphStyles from a BrandPack.

Replaces ReportLab's default styles with brand-aware ones.
"""
from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle

from mdpdf.brand.schema import BrandPack


@dataclass
class BrandStyles:
    """Brand-driven ReportLab styles + layout for the engine to consume."""

    paragraph_styles: dict[str, ParagraphStyle]
    page_size: str
    left_margin: int   # in mm
    right_margin: int
    top_margin: int
    bottom_margin: int


def build_brand_styles(bp: BrandPack) -> BrandStyles:
    body_font = bp.theme.typography.body
    heading_font = bp.theme.typography.heading
    code_font = bp.theme.typography.code
    text_color = HexColor(bp.theme.colors.text)
    primary_color = HexColor(bp.theme.colors.primary)
    muted_color = HexColor(bp.theme.colors.muted)

    body_style = ParagraphStyle(
        name="Body",
        fontName=body_font.family,
        fontSize=body_font.size,
        leading=body_font.leading,
        textColor=text_color,
        wordWrap="CJK",
    )
    code_style = ParagraphStyle(
        name="Code",
        fontName=code_font.family,
        fontSize=code_font.size,
        leading=code_font.leading,
        textColor=muted_color,
    )

    h_styles: dict[str, ParagraphStyle] = {}
    for level in range(1, 7):
        h_styles[f"H{level}"] = ParagraphStyle(
            name=f"H{level}",
            parent=body_style,
            fontName=heading_font.family,
            fontSize=max(8, body_font.size + (8 - level * 2)),
            leading=int(max(8, body_font.size + (8 - level * 2)) * 1.4),
            textColor=primary_color,
            spaceBefore=8 if level <= 2 else 4,
            spaceAfter=4,
        )

    return BrandStyles(
        paragraph_styles={"Body": body_style, "Code": code_style, **h_styles},
        page_size=bp.theme.layout.page_size,
        left_margin=bp.theme.layout.margins.left,
        right_margin=bp.theme.layout.margins.right,
        top_margin=bp.theme.layout.margins.top,
        bottom_margin=bp.theme.layout.margins.bottom,
    )
