"""Tests for font_manager."""
from pathlib import Path

import pytest

from mdpdf.errors import FontError
from mdpdf.fonts.manager import FontManager, cjk_chars_present

REPO_ROOT = Path(__file__).resolve().parents[3]
BUNDLED_FONTS_DIR = REPO_ROOT / "fonts"


def test_cjk_chars_present_chinese():
    assert cjk_chars_present("Hello 你好 world") is True


def test_cjk_chars_present_japanese_kana():
    assert cjk_chars_present("テスト") is True


def test_cjk_chars_present_korean_hangul():
    assert cjk_chars_present("안녕") is True


def test_cjk_chars_present_pure_english():
    assert cjk_chars_present("Hello world") is False


def test_cjk_chars_present_empty():
    assert cjk_chars_present("") is False


# Regression tests for fullwidth punctuation tofu bug.
# Helvetica has no glyph for these so they need a CJK font.

def test_cjk_chars_present_fullwidth_colon():
    """`：` (U+FF1A) must trigger CJK font fallback."""
    assert cjk_chars_present("Marketing：marketing@idimsum.com") is True


def test_cjk_chars_present_fullwidth_comma():
    assert cjk_chars_present("test，hello") is True


def test_cjk_chars_present_fullwidth_period():
    assert cjk_chars_present("hello。world") is True


def test_cjk_chars_present_fullwidth_parens():
    assert cjk_chars_present("（test）") is True


def test_cjk_chars_present_corner_brackets():
    """`「」` (U+300C/D) — CJK Symbols & Punctuation block."""
    assert cjk_chars_present("「quote」") is True


def test_cjk_chars_present_chinese_dun_period():
    """`、` (U+3001) ideographic comma."""
    assert cjk_chars_present("苹果、香蕉") is True


def test_cjk_chars_present_emoji():
    assert cjk_chars_present("hello 🚀") is True


def test_cjk_chars_present_face_emoji():
    assert cjk_chars_present("😀 face") is True


def test_cjk_chars_present_latin_supplement_stays_false():
    """`é` (U+00E9) — Helvetica has it, should NOT trigger CJK fallback."""
    assert cjk_chars_present("café") is False


def test_cjk_chars_present_pure_ascii_punctuation():
    """ASCII punctuation must NOT trigger CJK fallback."""
    assert cjk_chars_present("a@b.com, hello.") is False


def test_font_manager_registers_bundled_noto():
    """The bundled fonts/NotoSansSC-*.ttf must be available."""
    fm = FontManager(bundled_dir=BUNDLED_FONTS_DIR)
    fm.register_for_text("你好世界")
    # If this didn't raise, registration succeeded.
    assert fm.has_cjk_glyphs is True


def test_font_manager_fail_loud_when_no_cjk_font_anywhere(tmp_path: Path):
    """Empty bundled dir + no system Noto = FontError on CJK content."""
    fm = FontManager(bundled_dir=tmp_path, system_fallbacks=[])
    with pytest.raises(FontError) as ei:
        fm.register_for_text("你好")
    assert ei.value.code == "FONT_NOT_INSTALLED"


def test_font_manager_does_not_complain_for_pure_english(tmp_path: Path):
    """Pure English requires no CJK font; should not raise even with empty bundled dir."""
    fm = FontManager(bundled_dir=tmp_path, system_fallbacks=[])
    fm.register_for_text("Hello world")  # no exception


def test_font_manager_picks_brand_fonts_first(tmp_path: Path):
    """If the brand pack ships its own font, register it (not the bundled fallback)."""
    brand_fonts = tmp_path / "brand-fonts"
    brand_fonts.mkdir()
    # Copy bundled NotoSC into the brand-fonts dir so it's a real TTF
    src = BUNDLED_FONTS_DIR / "NotoSansSC-Regular.ttf"
    dst = brand_fonts / "BrandSerif-Regular.ttf"
    dst.write_bytes(src.read_bytes())
    fm = FontManager(bundled_dir=BUNDLED_FONTS_DIR, brand_fonts_dir=brand_fonts)
    fm.register_for_text("你好")
    # Brand fonts take precedence
    assert "BrandSerif-Regular" in fm.registered_names
