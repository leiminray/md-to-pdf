"""Tests for BrandStyles (ReportLab ParagraphStyle factory from BrandPack)."""
from pathlib import Path

from mdpdf.brand.schema import load_brand_pack
from mdpdf.brand.styles import BrandStyles, build_brand_styles

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_brand_styles_returns_paragraph_styles():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    styles = build_brand_styles(bp)
    assert isinstance(styles, BrandStyles)
    # H1-H6 + body + code
    for level in range(1, 7):
        assert f"H{level}" in styles.paragraph_styles
    assert "Body" in styles.paragraph_styles
    assert "Code" in styles.paragraph_styles


def test_brand_styles_uses_brand_colors():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    styles = build_brand_styles(bp)
    body = styles.paragraph_styles["Body"]
    # ReportLab stores colour as Color or HexColor; check it is not None
    assert body.textColor is not None


def test_brand_styles_carries_layout():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    styles = build_brand_styles(bp)
    assert styles.page_size == "A4"
    assert styles.left_margin == 18
    assert styles.right_margin == 18
    assert styles.top_margin == 22
    assert styles.bottom_margin == 32
