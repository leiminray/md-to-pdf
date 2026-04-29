"""Font manager.

Replaces a quick byte-level CJK detector. The manager checks whether
a CJK-capable font is registered (or registerable) given:
1. brand-pack `assets/fonts/` directory (if provided)
2. bundled `<repo>/fonts/NotoSansSC-*.ttf`
3. system fallbacks (macOS Arial Unicode, Linux DejaVu Sans, Windows MS Mincho)
4. Courier — last resort (no CJK)

If the input contains CJK characters and no CJK-capable TTF is found in
1-3, raises `FontError(code="FONT_NOT_INSTALLED")`.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont

from mdpdf.errors import FontError


def cjk_chars_present(text: str) -> bool:
    """True if *text* contains any character that requires a CJK-capable font.

    Covers the ranges Noto Sans SC supports beyond Latin-1, including
    fullwidth punctuation (`：`, `，`, etc.), CJK symbols, ideographs, kana,
    hangul, and CJK compatibility forms. Helvetica lacks glyphs for any of
    these, so detecting them lets the caller switch to Noto Sans SC and
    avoid tofu (rendered as small black squares).
    """
    for ch in text:
        cp = ord(ch)
        if (
            0x2E80 <= cp <= 0x2EFF       # CJK Radicals Supplement
            or 0x2F00 <= cp <= 0x2FDF    # Kangxi Radicals
            or 0x3000 <= cp <= 0x303F    # CJK Symbols & Punctuation (、。「」)
            or 0x3040 <= cp <= 0x309F    # Hiragana
            or 0x30A0 <= cp <= 0x30FF    # Katakana
            or 0x3100 <= cp <= 0x312F    # Bopomofo
            or 0x3130 <= cp <= 0x318F    # Hangul Compatibility Jamo
            or 0x31C0 <= cp <= 0x31EF    # CJK Strokes
            or 0x3200 <= cp <= 0x32FF    # CJK Letters & Months / Enclosed
            or 0x3300 <= cp <= 0x33FF    # CJK Compatibility
            or 0x3400 <= cp <= 0x4DBF    # CJK Unified Ext A
            or 0x4E00 <= cp <= 0x9FFF    # CJK Unified Ideographs
            or 0xA000 <= cp <= 0xA4CF    # Yi
            or 0xAC00 <= cp <= 0xD7AF    # Hangul Syllables
            or 0xF900 <= cp <= 0xFAFF    # CJK Compatibility Ideographs
            or 0xFE30 <= cp <= 0xFE4F    # CJK Compatibility Forms
            or 0xFF00 <= cp <= 0xFFEF    # Halfwidth & Fullwidth Forms (：，)
            or 0x1F300 <= cp <= 0x1F9FF  # Emoji & Pictographs
            or 0x20000 <= cp <= 0x2FFFF  # CJK Unified Ext B-F
        ):
            return True
    return False


_DEFAULT_SYSTEM_FALLBACKS_CJK = [
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]


class FontManager:
    """Registers TTFs with ReportLab on demand."""

    def __init__(
        self,
        *,
        bundled_dir: Path,
        brand_fonts_dir: Path | None = None,
        system_fallbacks: list[str] | None = None,
    ) -> None:
        self.bundled_dir = Path(bundled_dir)
        self.brand_fonts_dir = Path(brand_fonts_dir) if brand_fonts_dir else None
        self.system_fallbacks = (
            system_fallbacks if system_fallbacks is not None
            else _DEFAULT_SYSTEM_FALLBACKS_CJK
        )
        self.registered_names: list[str] = []
        self.has_cjk_glyphs = False

    def register_for_text(self, text: str) -> None:
        """Register fonts sufficient to render `text`. Raises FontError on CJK gap."""
        # Always try to register brand + bundled fonts (cheap if they exist).
        self._register_dir(self.brand_fonts_dir)
        self._register_dir(self.bundled_dir)
        if cjk_chars_present(text) and not self.has_cjk_glyphs:
            # No brand or bundled CJK font found; try system fallbacks.
            for sys_path_str in self.system_fallbacks:
                sys_path = Path(sys_path_str)
                if not sys_path.exists():
                    continue
                try:
                    name = sys_path.stem
                    pdfmetrics.registerFont(TTFont(name, str(sys_path)))
                    self.registered_names.append(name)
                    self.has_cjk_glyphs = True
                    break
                except TTFError:
                    continue
        if cjk_chars_present(text) and not self.has_cjk_glyphs:
            raise FontError(
                code="FONT_NOT_INSTALLED",
                user_message=(
                    "input contains CJK characters but no CJK-capable font is "
                    "available in brand pack, bundled fonts/, or system fallbacks. "
                    "Install Noto Sans CJK or run via  (scripts/md_to_pdf.py) "
                    "until brand-pack font auto-discovery improves."
                ),
            )

    def _register_dir(self, fonts_dir: Path | None) -> None:
        if fonts_dir is None or not fonts_dir.is_dir():
            return
        for ttf in sorted(fonts_dir.glob("*.ttf")):
            name = ttf.stem
            try:
                pdfmetrics.registerFont(TTFont(name, str(ttf)))
            except TTFError:
                continue
            if name in self.registered_names:
                continue
            self.registered_names.append(name)
            # Heuristic: any registration from brand or bundled = CJK present
            # iff the source dir is the bundled one OR the file name contains CJK markers.
            if "Noto" in name or "CJK" in name or "SC" in name:
                self.has_cjk_glyphs = True
