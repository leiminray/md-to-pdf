#!/usr/bin/env python3
"""
Markdown → PDF for the md-to-pdf skill (see .cursor/skills/md-to-pdf/SKILL.md).

Branded layout (see .cursor/skills/md-to-pdf/brand_kits/branding-and-ux.md):
  - Header: IDIMSUM logo (left) + Generated timestamp (right), same vertical band; #0f4c81 rule
  - Footer: pypdf overlay (full-page stamp with text only) after issuer; same margins as header; confidential left; Page i / n right
  - Last page issuer box: pypdf merge; issuer bottom = footer draw top − 10pt. Body frame uses a larger bottomMargin so text clears the issuer (avoids a trailing Spacer that could add a blank last page).
  - ## 目录 / ## Table of Contents + pipe table: TOC rows link to heading bookmarks (ids-h-*) when text matches; optional --watermark: company only from brand_kits ``compliance.md``; user required (else no watermark); user-only if no company in compliance + user for diagonal pypdf watermark (merged under text) on all pages after footer.
  - Body/table: brand blue headings, gray table header row, grid #d1d5db
  - ReportLab cannot embed some Noto OTF — use TTF in this skill’s fonts/ (OFL) when available
  - Leading YAML frontmatter (`---` … `---`, e.g. Cursor plan exports) is stripped before layout (not shown in PDF body).
  - Run-on ATX headings (`# Part## Chapter` on one line) are split outside ``` fences before parsing.
  - ```mermaid``` blocks: PNG via mmdc (Noto TTF + references/mermaid-noto-config.json, -w/-H from --mermaid-E|S|H or env).
  - Fence lang: first token after ``` (e.g. ```mermaid {.opts} → mermaid). Other fences: GitHub-like card, optional Pygments (MDPDF_FENCED_PYGMENTS) + optional line numbers (MDPDF_FENCED_LINE_NUMBERS); see SKILL.md. Chunk caps: MDPDF_FENCED_*.
  - Preset: mutually exclusive --mermaid-E / --mermaid-S / --mermaid-H, or MDPDF_MERMAID_PRESET (default S if none set); invalid env → S.
  - Mermaid: below each image a **centered** caption (muted, **50%** of body font size) from YAML ``title:`` in the diagram or nearest ATX heading above the fence; omitted if none resolved. Small Mermaid blocks use ``KeepTogether`` when scaled block height is below ~45% of body height (automatic).
  - First-time Mermaid: see requirements-md-pdf.txt Step B and scripts/ensure_mermaid_deps.py.
  - Puppeteer downloads default to .mdpdf-puppeteer-cache/ under this skill folder (gitignored) when cache would be sandbox temp or unset.
  - Skip Mermaid (no mmdc/Puppeteer/Chrome): --no-mermaid or MDPDF_SKIP_MERMAID=1; mermaid blocks render as the usual fenced code (same as other code fences), not a short note.
  - Diagnostics: MDPDF_MERMAID_VERBOSE=1 logs browser path, cache dir, mmdc --version (once), and mmdc invocations to stderr.

Usage (from repository root; adjust if the clone path differs):
  .cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py INPUT.md
    → default PDF: .cursor/skills/md-to-pdf/fixtures/out/<INPUT stem>.pdf
  .cursor/skills/md-to-pdf/.venv/bin/python .cursor/skills/md-to-pdf/scripts/md_to_pdf.py INPUT.md -o OTHER.pdf
    → -o is relative to the current working directory unless an absolute path is given.
"""
from __future__ import annotations

import argparse
import getpass
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Callable

try:
    import reportlab  # noqa: F401 — probe deps before other reportlab.* imports
except ModuleNotFoundError:
    _skill = Path(__file__).resolve().parents[1]
    print(
        "md-to-pdf: missing Python dependencies.\n"
        f"  Setup: python3 -m venv {_skill / '.venv'}\n"
        f"  Then:  {_skill / '.venv' / 'bin' / 'pip'} install -r "
        f"{_skill / 'requirements-md-pdf.txt'}\n"
        f"  Full steps: {_skill / 'README.md'}",
        file=sys.stderr,
    )
    raise SystemExit(1) from None

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from brand_pack import BrandPack, load_brand_pack, watermark_company_name

try:
    import fenced_rl
except ImportError:
    fenced_rl = None

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Flowable
from reportlab.platypus import Image as RLImage
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.rl_config import _FUZZ

# scripts/ → md-to-pdf skill folder; repo root still needed for optional OTF fallback in register_fonts().
SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BRAND_PACK_DIR = SKILL_ROOT / "brand_kits"
DEFAULT_FIXTURES_OUT_DIR = SKILL_ROOT / "fixtures" / "out"
FONTS_DIR = SKILL_ROOT / "fonts"
# Optional local-only recovery (OFL, same TTFs). Not versioned by default; if present, used when
# loose .ttf files are missing. Place `noto_sans_sc_bundled.zip` here yourself or omit it.
BUNDLED_FONTS_ZIP = FONTS_DIR / "noto_sans_sc_bundled.zip"
# Default ReportLab post-registration names (see register_fonts)
FONT_NOTO_R = "IDS-Noto-Regular"
FONT_NOTO_B = "IDS-Noto-Bold"
# Monospace for fenced code: prefer **Noto Sans Mono** (OFL) from the OS when present, then other monos, → Courier
FONT_CODE_MONO = "IDS-Mono"
# (path, subfontIndex or None) — NotoSansMono-Regular first (aligned with “default to Noto” like body), then fallbacks
_MONO_TTF_CANDIDATES: list[tuple[Path, int | None]] = [
    (Path("/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf"), None),
    (Path("/usr/share/fonts/noto/NotoSansMono-Regular.ttf"), None),
    (Path("/opt/homebrew/share/fonts/noto/NotoSansMono-Regular.ttf"), None),
    (Path("/usr/local/share/fonts/noto/NotoSansMono-Regular.ttf"), None),
    (Path("/Library/Fonts/NotoSansMono-Regular.ttf"), None),
    (Path.home() / "Library" / "Fonts" / "NotoSansMono-Regular.ttf", None),
    (Path("C:/Windows/Fonts/NotoSansMono-Regular.ttf"), None),
    (Path("/System/Library/Fonts/Supplemental/Menlo.ttc"), 0),
    (Path("/System/Library/Fonts/Menlo.ttc"), 0),
    (Path("C:/Windows/Fonts/consola.ttf"), None),
    (Path("C:/Windows/Fonts/cour.ttf"), None),
    (Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"), None),
]
# Mermaid (mmdc) → Puppeteer: keep downloads under the skill dir (gitignored) when possible.
MDPDF_PUPPETEER_CACHE = SKILL_ROOT / ".mdpdf-puppeteer-cache"
NOTO_BOLD_OTF = (
    REPO_ROOT
    / "company_assets"
    / "brand"
    / "assets"
    / "fonts"
    / "external-standard-a"
    / "NotoSansCJKsc-Bold.otf"
)
MAC_ARIAL_UNICODE = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")

_brand_pack_instance: BrandPack | None = None


def get_brand_pack() -> BrandPack:
    """Active brand pack (set in main(); defaults to built-in `brand_kits/`)."""
    global _brand_pack_instance
    if _brand_pack_instance is None:
        _brand_pack_instance = load_brand_pack(DEFAULT_BRAND_PACK_DIR)
    return _brand_pack_instance


def set_brand_pack(pack: BrandPack) -> None:
    global _brand_pack_instance
    _brand_pack_instance = pack


def resolve_output_pdf(md_path: Path, output_arg: Path | None) -> Path:
    """
    If output_arg is None: write to skill fixtures/out/<md_stem>.pdf (dir created as needed).
    If output_arg is set: expanduser; absolute paths used as-is; relative paths resolved from cwd.
    """
    if output_arg is None:
        DEFAULT_FIXTURES_OUT_DIR.mkdir(parents=True, exist_ok=True)
        return (DEFAULT_FIXTURES_OUT_DIR / f"{md_path.stem}.pdf").resolve()
    o = Path(output_arg).expanduser()
    if o.is_absolute():
        return o.resolve()
    return (Path.cwd() / o).resolve()


def wrote_path_display(path: Path) -> str:
    """Prefer a path relative to cwd for the single-line success message."""
    abs_p = path.resolve()
    try:
        return str(abs_p.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(abs_p)


def _color_xml_hex(c: colors.Color) -> str:
    """#rrggbb for Paragraph <font color='…'>."""
    hv = str(c.hexval())
    if hv.startswith("#"):
        return hv
    if hv.startswith("0x"):
        return "#" + hv[2:]
    return "#" + hv


# Text block L/R margin (mm): shared by header canvas, SimpleDocTemplate, footer stamp
PAGE_H_MARGIN_MM = 18.0
# Text block bottom margin (mm) — must match SimpleDocTemplate bottomMargin in main()
BODY_BOTTOM_MARGIN_MM = 32.0
# Footer right-side width reserved for “Page i / n” (pt)
FOOTER_PAGE_NUM_SLOT_PT = 200.0

# Issuer card width as fraction of text block (was 70%, widened by 5 pp → 75%)
ISSUER_BOX_WIDTH_FRAC = 0.75
ICON_SZ_PT = 22.0
QR_SZ_PT = 44.0
# Padding between QR and issuer box right edge (col width = L pad + image + R pad; avoids overlap when image fills column)
ISSUER_QR_LEFT_PAD_PT = 2.0
ISSUER_QR_RIGHT_PAD_PT = 10.0
# Gap (pt) between issuer box bottom and top of footer stamp band
GAP_ISSUER_ABOVE_FOOTER_DRAW_TOP_PT = 10.0
# Footer text rect extends slightly above y_row1_top (historical fit to former overlay)
FOOTER_DRAW_RECT_TOP_PAD_PT = 2.0
# Issuer fragment height from build_issuer_outer_table().wrap(); fallback cap on error
ISSUER_FRAGMENT_HEIGHT_FALLBACK_PT = 280.0
# Footer band top offset from page bottom (coords: y from top, downward)
FOOTER_ROW_TOP_OFFSET_PT = 10
FOOTER_BOTTOM_PAD_PT = 8  # Footer text bottom inset from page edge
FOOTER_BAND_MIN_HEIGHT_PT = 12  # Min band height when OFFSET is small after bottom clamp

# Tiled pypdf watermark: spacing between baselines in the “row” direction (rotated space), pt
WATERMARK_ROW_SPACING_PT = 120.0
# Horizontal gap between repeated text copies on the same row (rotated +x)
WATERMARK_COL_GAP_PT = 20.0
WATERMARK_TILE_ANGLE_DEG = 38.0
WATERMARK_FONT_SIZE_PT = 13.0
# Light gray text fill: again 50% blend toward white vs prior (0.85, 0.86, 0.89)
WATERMARK_FILL_RGB = (0.925, 0.93, 0.945)
# Rotated grid radius vs page size — large enough to cover page corners when tiled
WATERMARK_PAGE_EXTENT_MULT = 1.4

# Markdown tables: content-weighted columns; each column ≤ 70% of table width (avoids one “notes” column starving “item”)
TABLE_COL_MAX_FRAC = 0.7
# Two-column tables: short columns (≤10 chars) often labels — down-weight vs long prose columns
TABLE_SHORT_COL_WEIGHT_N2 = 0.45
# Three+ columns: short cells often dimension/category names — do not apply harsh 0.45 (would crush that column)
TABLE_SHORT_COL_WEIGHT_N3PLUS = 0.88
# Three+ columns: first column often dimension/item — slight boost to balance long text in later columns
TABLE_FIRST_COL_BOOST_N3PLUS = 1.22
# Three+ columns: minimum fraction of table width per column (avoids hairline columns)
TABLE_MIN_COL_FRAC_3PLUS = 0.17
TABLE_COL_MIN_PT = 26.0
TABLE_CELL_PAD_PT = 4.0  # Tighter row height than former 6pt
# Mermaid → PNG (mmdc): max embedded height so one diagram does not fill the page
MERMAID_MAX_HEIGHT_PT = 440.0
# Mermaid: use same OFL Noto as PDF body (see references/mermaid-noto-config.json)
MERMAID_NOTO_FAMILY = "IDS Noto Sans SC"
MERMAID_CONFIG_PATH = SKILL_ROOT / "references" / "mermaid-noto-config.json"
MERMAID_CSS_FILENAME = "mdpdf-mermaid.css"
MERMAID_PRESET_DIMENSIONS: dict[str, tuple[int, int]] = {
    "E": (800, 600),
    "S": (1024, 768),
    "H": (1920, 1080),
}
MERMAID_SUBPROCESS_TIMEOUT_SHORT = 180
MERMAID_SUBPROCESS_TIMEOUT_HIGH = 300
# Fenced blocks / Mermaid input bounds (override via env)
_DEFAULT_MERMAID_MAX_CHARS = 200_000
_DEFAULT_FENCED_MAX_CHARS = 262_144  # 256 KiB
_DEFAULT_FENCED_MAX_LINES = 500
MERMAID_KEEP_TOGETHER_FRAC = 0.45
# Fenced code: ``LeftRuleCodeBlock`` + single ``Paragraph`` does not split across pages; chunk by line count.
_FENCED_CODE_LINES_PER_CHUNK = 48
# Must match SimpleDocTemplate topMargin in main()
_BODY_STACK_TOP_MM = 34.0


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name, "").strip()
    if not v:
        return default
    try:
        x = int(v, 10)
        return x if x > 0 else default
    except ValueError:
        return default


def _env_float_mm(
    name: str,
    default: float,
    *,
    lo: float = 0.0,
    hi: float = 25.0,
) -> float:
    """Parse ``MDPDF_*`` millimetre spacing; clamp to ``[lo, hi]``."""
    v = os.environ.get(name, "").strip()
    if not v:
        return default
    try:
        x = float(v.replace(",", "."))
    except ValueError:
        return default
    return max(lo, min(hi, x))


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _fenced_starts_soon_after(lines: list[str], j: int) -> bool:
    """
    True when the first non-blank line at or after index ``j`` is an opening ``` fence.
    Used to tighten the previous paragraph/heading spaceAfter before a code block.
    """
    n = len(lines)
    k = j
    while k < n and not lines[k].strip():
        k += 1
    if k >= n:
        return False
    return lines[k].strip().startswith("```")


def _env_fenced_pygments() -> bool:
    """``MDPDF_FENCED_PYGMENTS=0`` disables Pygments; default on when Pygments is installed."""
    v = os.environ.get("MDPDF_FENCED_PYGMENTS", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


# GitHub light–inspired (fenced code header / border; body fill)
_FENCED_GH_HDR_BG = colors.HexColor("#f6f8fa")
_FENCED_GH_HDR_TXT = colors.HexColor("#57606a")
_FENCED_GH_CODE_BG = colors.white
_FENCED_GH_BORDER = colors.HexColor("#d0d7de")
_FENCED_GH_CODE_INK = colors.HexColor("#24292f")
# Default mm of Spacer *above* a fenced code card (override ``MDPDF_FENCED_CARD_ABOVE_MM``).
_DEFAULT_FENCED_CARD_ABOVE_MM = 0.0
# Cell padding (pt) under the ``LINEBELOW`` seam before the first line of code
_FENCED_TABLE_BODY_TOP_PAD_PT = 12.0


def _fence_truncate(
    body_lines: list[str],
    max_lines: int,
    max_chars: int,
) -> tuple[list[str], bool]:
    """Return (lines, truncated) when exceeding line or character limits (UTF-8 code points via len())."""
    max_lines = max(1, max_lines)
    max_chars = max(1, max_chars)
    out: list[str] = []
    for line in body_lines:
        if len(out) >= max_lines:
            return out, True
        trial = out + [line]
        blob = "\n".join(trial)
        if len(blob) > max_chars:
            prefix = "\n".join(out)
            sep = 1 if out else 0
            remain = max_chars - len(prefix) - sep
            if remain > 0:
                out.append(line[:remain])
            return out, True
        out.append(line)
    return out, False


def cell_plain_for_width_estimate(cell: str) -> str:
    """Strip MD for width measurement (same spirit as md_inline_to_xml, no XML entities)."""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cell)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    return s.strip()


def string_width_pt(text: str, font_name: str, font_size: float) -> float:
    if not text:
        return 0.0
    try:
        return float(pdfmetrics.stringWidth(text, font_name, font_size))
    except Exception:
        return len(text) * font_size * 0.52


def _table_max_col_frac(ncols: int) -> float:
    """Single-column tables use full width; multi-column tables cap each column at TABLE_COL_MAX_FRAC."""
    if ncols <= 1:
        return 1.0
    return TABLE_COL_MAX_FRAC


def _enforce_min_col_frac_3plus(
    widths: list[float],
    total_width_pt: float,
    w_cap: float,
    ncols: int,
    min_frac: float,
) -> list[float]:
    """
    For three or more columns: enforce at least min_frac of table width per column,
    then normalize together with the 70% per-column cap. Prevents very short label
    columns (e.g. “dimension”) from becoming too narrow.
    """
    if ncols < 3:
        return widths
    min_w = total_width_pt * min_frac
    for _ in range(6):
        widths = [max(w, min_w) for w in widths]
        widths = [min(w, w_cap) for w in widths]
        s = sum(widths)
        if abs(s - total_width_pt) < 0.5:
            return widths
        if s > total_width_pt + 0.5:
            scale = total_width_pt / s
            widths = [w * scale for w in widths]
        else:
            slack = total_width_pt - s
            room = [max(0.0, w_cap - w) for w in widths]
            sroom = sum(room)
            if sroom > 0.5:
                widths = [w + slack * (room[j] / sroom) for j, w in enumerate(widths)]
            else:
                widths = [w + slack / ncols for w in widths]
    s = sum(widths)
    if abs(s - total_width_pt) > 0.5:
        scale = total_width_pt / s
        widths = [w * scale for w in widths]
    return widths


def compute_table_col_widths_pt(
    rows: list[list[str]],
    total_width_pt: float,
    font_name: str,
    font_size: float,
    max_col_frac: float | None = None,
    min_col_pt: float = TABLE_COL_MIN_PT,
) -> list[float]:
    """
    Content-weighted column widths: short / numeric-heavy columns get lower weight;
    each column capped at max_col_frac * total_width_pt (default 70% of table width).
    First slack pass uses content weight; if still short after caps, remaining width
    is distributed by headroom under the cap (so a maxed wide column does not keep
    absorbing slack—label columns can grow toward 30%+).
    """
    ncols = len(rows[0])
    if ncols == 0:
        return []
    if ncols == 1:
        return [total_width_pt]

    if max_col_frac is None:
        max_col_frac = _table_max_col_frac(ncols)
    w_cap = total_width_pt * max_col_frac
    raw_weights: list[float] = []

    for j in range(ncols):
        max_sw = 0.0
        col_texts: list[str] = []
        for row in rows:
            cell = row[j] if j < len(row) else ""
            plain = cell_plain_for_width_estimate(cell)
            col_texts.append(plain)
            max_sw = max(max_sw, string_width_pt(plain, font_name, font_size))

        joined = "".join(col_texts)
        max_len = max(len(t) for t in col_texts) if col_texts else 0
        short_numeric = False
        if max_len <= 18 and joined:
            digitish = sum(
                1
                for ch in joined
                if ch.isdigit() or ch in "%.,+-−￥$€£ \t"
            )
            if digitish / len(joined) >= 0.28:
                short_numeric = True
        if short_numeric:
            max_sw *= 0.22
        elif max_len <= 10:
            max_sw *= TABLE_SHORT_COL_WEIGHT_N2 if ncols <= 2 else TABLE_SHORT_COL_WEIGHT_N3PLUS

        # Total chars: wrapped line count follows column width; boost “description”-style columns via char mass
        char_sum = sum(len(t) for t in col_texts)
        char_boost = (char_sum**0.5) * font_size * 0.35
        combined = max(max_sw, char_boost)
        if ncols >= 3 and j == 0:
            combined *= TABLE_FIRST_COL_BOOST_N3PLUS
        raw_weights.append(max(combined, min_col_pt))

    s = sum(raw_weights)
    if s <= 0:
        return [total_width_pt / ncols] * ncols

    widths = [total_width_pt * w / s for w in raw_weights]
    widths = [min(w, w_cap) for w in widths]
    widths = [max(w, min_col_pt * 0.85) for w in widths]

    total = sum(widths)
    if total > total_width_pt + 0.5:
        scale = total_width_pt / total
        widths = [w * scale for w in widths]
    elif total < total_width_pt - 0.5:
        slack = total_width_pt - total
        # Distribute slack by content weight so narrow columns under the cap do not absorb all slack
        need = [max(raw_weights[j], min_col_pt * 0.5) for j in range(ncols)]
        sneed = sum(need)
        if sneed > 0.5:
            widths = [w + slack * (need[j] / sneed) for j, w in enumerate(widths)]
        else:
            widths = [w + slack / ncols for w in widths]
        widths = [min(w, w_cap) for w in widths]
        total2 = sum(widths)
        if total2 < total_width_pt - 0.5:
            # When wide columns hit the 70% cap, give remainder to columns with headroom (e.g. item labels)
            slack2 = total_width_pt - total2
            room = [max(0.0, w_cap - w) for w in widths]
            sroom = sum(room)
            if sroom > 0.5:
                widths = [w + slack2 * (room[j] / sroom) for j, w in enumerate(widths)]
            else:
                widths = [w + slack2 / ncols for w in widths]
            widths = [min(w, w_cap) for w in widths]

    total = sum(widths)
    if abs(total - total_width_pt) > 0.5:
        scale = total_width_pt / total
        widths = [w * scale for w in widths]

    if ncols >= 3:
        widths = _enforce_min_col_frac_3plus(
            widths,
            total_width_pt,
            w_cap,
            ncols,
            TABLE_MIN_COL_FRAC_3PLUS,
        )

    return widths


def footer_draw_top_y(h: float) -> float:
    """
    Footer band top y (origin top-left, y increases downward): top edge of confidential/page-num band.
    """
    y_row1_top, _ = footer_strip_y_bounds(h)
    return y_row1_top - FOOTER_DRAW_RECT_TOP_PAD_PT


def issuer_bottom_y_for_page(h: float) -> float:
    """Issuer block bottom y: footer draw top minus GAP_ISSUER_ABOVE_FOOTER_DRAW_TOP_PT."""
    return footer_draw_top_y(h) - GAP_ISSUER_ABOVE_FOOTER_DRAW_TOP_PT


def measure_issuer_fragment_height_pt(font: str, font_bold: str, qr_path: Path | None) -> float:
    """Measured outer issuer Table height (pt) at text width tw; matches write_issuer_fragment_pdf page height."""
    row = build_issuer_outer_table(font, font_bold, qr_path, get_brand_pack())
    fw = A4[0] - 2 * PAGE_H_MARGIN_MM * mm
    tw = fw * ISSUER_BOX_WIDTH_FRAC
    _w, ht = row.wrap(tw, 10**6)
    h = float(ht) if ht and ht > 0.5 else ISSUER_FRAGMENT_HEIGHT_FALLBACK_PT
    return h


def required_bottom_margin_for_issuer_pt(issuer_fragment_height_pt: float) -> float:
    """
    Minimum ``SimpleDocTemplate`` bottom margin so body text never enters the pypdf issuer
    overlay (same geometry as ``overlay_issuer_on_last_page``). Using a tall **trailing Spacer**
    instead used to force an **extra blank page** when the spacer was larger than the remaining
    frame height on the last content page (Spacer cannot “split” across the page break the way
    we need). Reserving space via ``bottomMargin`` applies on every page and avoids that.
    """
    h = float(A4[1])
    y_issuer_bot = issuer_bottom_y_for_page(h)
    y_issuer_top = y_issuer_bot - issuer_fragment_height_pt
    clearance_pt = 4.0
    # Frame lower edge (y from top) must stay at or above y_issuer_top - clearance.
    need = h - y_issuer_top + clearance_pt
    return max(BODY_BOTTOM_MARGIN_MM * mm, need)


def footer_strip_y_bounds(h: float) -> tuple[float, float]:
    """
    (y_top, y_bot) for the confidential line / page-number band; shared by footer stamp and issuer.
    Coords: origin top-left, y increases downward (same numeric convention as page height h).
    """
    y_row1_bot = h - FOOTER_BOTTOM_PAD_PT
    y_row1_top = h - FOOTER_ROW_TOP_OFFSET_PT
    if y_row1_top >= y_row1_bot - FOOTER_BAND_MIN_HEIGHT_PT:
        y_row1_top = y_row1_bot - FOOTER_BAND_MIN_HEIGHT_PT
    return y_row1_top, y_row1_bot


def _restore_noto_ttf_from_bundled_zip() -> None:
    """
    If either Noto TTF is missing, try the same two files from an optional
    `noto_sans_sc_bundled.zip` in `fonts/` (OFL, not committed by project policy) so
    local/offline recovery works without curl when someone drops that zip in place.
    """
    reg_ttf = FONTS_DIR / "NotoSansSC-Regular.ttf"
    bold_ttf = FONTS_DIR / "NotoSansSC-Bold.ttf"
    if reg_ttf.is_file() and bold_ttf.is_file():
        return
    if not BUNDLED_FONTS_ZIP.is_file():
        return
    import zipfile

    want = {"NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf"}
    try:
        with zipfile.ZipFile(BUNDLED_FONTS_ZIP) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                if name not in want:
                    continue
                dest = FONTS_DIR / name
                if dest.is_file():
                    continue
                dest.write_bytes(zf.read(info))
    except (OSError, zipfile.BadZipFile):
        return


def _font_unavailable_exit() -> None:
    reg_ttf = FONTS_DIR / "NotoSansSC-Regular.ttf"
    bold_ttf = FONTS_DIR / "NotoSansSC-Bold.ttf"
    msg = [
        "md-to-pdf: 无可用嵌入字体。正文/页眉(Generated)/页脚(密级+页码)与 CJK 需要 Noto Sans SC。",
        f"1) 从版本库恢复: git restore --source=HEAD {reg_ttf} {bold_ttf}",
    ]
    if BUNDLED_FONTS_ZIP.is_file() and (not reg_ttf.is_file() or not bold_ttf.is_file()):
        msg.append(
            f"2) 若你已在 {FONTS_DIR} 放入可选的 {BUNDLED_FONTS_ZIP.name}，入口脚本会尝试从 zip 自动写回 TTF；"
            " 也可手工解压到该目录。"
        )
    msg.append(
        f"3) 有网络: 用 curl 从 Google Fonts 拉取 (步骤见 {FONTS_DIR / 'README.md'}，OFL 可商用)。"
    )
    msg.append(
        "4) 无网络: 从其他已克隆的机器复制两个 TTF 到上述目录(各约 10MB)。"
        " 仅使用西文内置字体会导致中文缺字，请勿依赖 Helvetica/Times 作为 CJK 替代。"
    )
    msg.append("5) 仅部分环境: 若本机有 Arial Unicode 或公司 OTF(可嵌入), register_fonts 会尝试次优回退。")
    raise SystemExit("\n".join(msg))


def register_fonts() -> tuple[str, str]:
    """Register Noto Sans SC (body + Mermaid + theme.yaml header/footer faces). Fallbacks: OTF, macOS."""
    _restore_noto_ttf_from_bundled_zip()
    # Primary: TrueType from fonts.google.com (ReportLab-embeddable)
    reg_ttf = FONTS_DIR / "NotoSansSC-Regular.ttf"
    bold_ttf = FONTS_DIR / "NotoSansSC-Bold.ttf"
    if reg_ttf.is_file() and bold_ttf.is_file():
        try:
            pdfmetrics.registerFont(TTFont(FONT_NOTO_R, str(reg_ttf)))
            pdfmetrics.registerFont(TTFont(FONT_NOTO_B, str(bold_ttf)))
            return FONT_NOTO_R, FONT_NOTO_B
        except TTFError:
            pass
    # Legacy filenames (full Noto CJK OTF; may fail if PostScript outlines)
    reg = FONTS_DIR / "NotoSansCJKsc-Regular.otf"
    bold = FONTS_DIR / "NotoSansCJKsc-Bold.otf"
    if reg.is_file() and bold.is_file() and reg.stat().st_size > 10_000_000 and bold.stat().st_size > 10_000_000:
        try:
            pdfmetrics.registerFont(TTFont(FONT_NOTO_R, str(reg)))
            pdfmetrics.registerFont(TTFont(FONT_NOTO_B, str(bold)))
            return FONT_NOTO_R, FONT_NOTO_B
        except TTFError:
            pass
    if NOTO_BOLD_OTF.is_file():
        try:
            pdfmetrics.registerFont(TTFont(FONT_NOTO_R, str(NOTO_BOLD_OTF)))
            pdfmetrics.registerFont(TTFont(FONT_NOTO_B, str(NOTO_BOLD_OTF)))
            return FONT_NOTO_R, FONT_NOTO_B
        except TTFError:
            pass
    if MAC_ARIAL_UNICODE.is_file():
        pdfmetrics.registerFont(TTFont(FONT_NOTO_R, str(MAC_ARIAL_UNICODE)))
        return FONT_NOTO_R, FONT_NOTO_R
    _font_unavailable_exit()


def register_mono_font() -> str:
    """
    Register a monospace font for fenced code (aligned with any2pdf: Mono + small text + left accent).

    Order: (1) **Noto Sans Mono** ``NotoSansMono-Regular.ttf`` on the system (Linux/macOS/Windows
    search paths, user ``~/Library/Fonts`` on macOS) — same *default* intent as body Noto, but
    not bundled in ``fonts/``; (2) Menlo/Consolas/DejaVu; (3) built-in Courier.
    """
    if FONT_CODE_MONO in pdfmetrics.getRegisteredFontNames():
        return FONT_CODE_MONO
    for path, sub in _MONO_TTF_CANDIDATES:
        if not path.is_file():
            continue
        try:
            if sub is not None:
                pdfmetrics.registerFont(
                    TTFont(FONT_CODE_MONO, str(path), subfontIndex=sub)
                )
            else:
                pdfmetrics.registerFont(TTFont(FONT_CODE_MONO, str(path)))
            return FONT_CODE_MONO
        except (TTFError, OSError):
            continue
    return "Courier"


# std-document header fields — strip from PDF (TOC heading shown via move_toc_after_title)
_RE_META_DASH = re.compile(
    r"^[-*•]\s*\*\*(Project Name|Client Name|Document Type|Document Version|Creation Date|"
    r"Last Update Date|Document Author|Reviewer|Document Status)\*\*\s*[:：]?",
    re.I,
)
_RE_META_BULLET = re.compile(
    r"^[•·]\s*(Document Type|Document Version|Creation Date|Last Update Date|Document Author|"
    r"Document Status|Project Name|Client Name|Reviewer)\s*[:：]",
    re.I,
)
_RE_META_PLAIN = re.compile(
    r"^(Document Type|Document Version|Creation Date|Last Update Date|Document Author|"
    r"Document Status|Project Name|Client Name|Reviewer)\s*[:：]",
    re.I,
)
_RE_META_CN = re.compile(
    r"^(文档类型|文档版本|创建日期|最后更新日期|文档作者|审阅人|文档状态)\s*[:：]",
)


_YAML_FM_MAX_SCAN = 600  # do not treat as frontmatter if closing --- is beyond this (from opening ---)


def strip_yaml_frontmatter(lines: list[str]) -> list[str]:
    """
    Remove a leading YAML block fenced by --- lines (CommonMark/Hugo/Cursor plan style).
    If there is no well-formed fence, return lines unchanged.
    """
    if not lines:
        return lines
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        return lines
    start = i
    j = i + 1
    limit = min(len(lines), start + 1 + _YAML_FM_MAX_SCAN)
    while j < limit:
        if lines[j].strip() == "---":
            return lines[:start] + lines[j + 1 :]
        j += 1
    return lines


def is_std_document_metadata_line(line: str) -> bool:
    """True if line is IDS std-document header metadata (not body bullets)."""
    t = line.strip()
    if not t:
        return False
    if _RE_META_DASH.match(t) or _RE_META_BULLET.match(t) or _RE_META_PLAIN.match(t) or _RE_META_CN.match(t):
        return True
    return False


def filter_md_for_branded_pdf(lines: list[str]) -> list[str]:
    """Drop std-document metadata bullets and ## Contributor Roles (+ table until ---)."""
    out: list[str] = []
    i = 0
    n = len(lines)
    skip_meta = False
    while i < n:
        raw = lines[i]
        s = raw.strip()
        if is_std_document_metadata_line(raw):
            i += 1
            continue
        if s.startswith("- **Project Name**") or s.startswith("- **Document Type**") or s.startswith(
            "- **Client Name**"
        ):
            skip_meta = True
            i += 1
            continue
        if skip_meta:
            if s.startswith("##"):
                skip_meta = False
            else:
                i += 1
                continue
        if s == "## Contributor Roles":
            i += 1
            while i < n:
                t = lines[i].strip()
                if t == "---":
                    i += 1
                    break
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def move_toc_after_title(lines: list[str]) -> list[str]:
    """
    Cut the `##` TOC heading and the following markdown table (exact titles match the scan loop below);
    insert immediately after the first `#` title. If no such section, return lines unchanged.
    """
    toc_i: int | None = None
    for idx, line in enumerate(lines):
        st = line.strip()
        if not st.startswith("## "):
            continue
        h = st[3:].strip()
        if h == "目录" or h.lower() == "table of contents":
            toc_i = idx
            break
    if toc_i is None:
        return lines
    j = toc_i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines) or not lines[j].strip().startswith("|"):
        return lines
    _rows, next_j = consume_markdown_table(lines, j)
    toc_end = next_j
    while toc_end < len(lines) and not lines[toc_end].strip():
        toc_end += 1
    if toc_end < len(lines) and lines[toc_end].strip() == "---":
        toc_end += 1
    while toc_end < len(lines) and not lines[toc_end].strip():
        toc_end += 1
    toc_block = lines[toc_i:toc_end]
    rest = lines[:toc_i] + lines[toc_end:]
    title_i: int | None = None
    for idx, line in enumerate(rest):
        if line.startswith("# "):
            title_i = idx
            break
    if title_i is None:
        return lines
    insert_at = title_i + 1
    while insert_at < len(rest) and not rest[insert_at].strip():
        insert_at += 1
    return rest[:insert_at] + [""] + toc_block + [""] + rest[insert_at:]


def esc(s: str) -> str:
    from xml.sax.saxutils import escape

    return escape(s)


def fenced_code_body_xml(
    lines: list[str], cjk_body_font: str | None = None
) -> str:
    """
    Fenced code as one ReportLab Paragraph: line breaks + leading spaces.
    Normal spaces at line start would collapse; use NBSP for indentation (any2pdf esc_code pattern).
    When ``cjk_body_font`` is set and ``fenced_rl`` is importable, CJK / fullwidth runs use that
    font so they do not render as "tofu" in monospace.
    """
    parts: list[str] = []
    for raw in lines:
        line = raw.expandtabs(4)
        n_lead = len(line) - len(line.lstrip(" "))
        body = line.lstrip(" ")
        prefix = "\u00a0" * n_lead
        if cjk_body_font and fenced_rl is not None:
            try:
                body_x = fenced_rl.fenced_cjk_mixed_line_xml(body, cjk_body_font)  # type: ignore[union-attr]
            except Exception:
                body_x = esc(body)
        else:
            body_x = esc(body)
        parts.append(prefix + body_x)
    return "<br/>".join(parts)


def md_inline_to_xml(s: str) -> str:
    # Markdown links [text](url) → keep text only (no PDF anchors; TOC table avoids duplicate semantics)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


# ATX headings: 1–6 `#` + space + heading text (CommonMark)
_RE_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
# Title text contains a deeper ATX marker: "# Part## Chapter" → split before "## Chapter"
_RE_ATX_EMBED_IN_TITLE = re.compile(r"^(.+?)(#{2,6}\s+.+)$")


def normalize_merged_atx_headings(lines: list[str]) -> list[str]:
    """
    Split run-on ATX headings on one physical line (e.g. `# Part## Chapter B`) into two lines.
    Skips lines inside fenced code blocks (``` ... ```).
    """
    out: list[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        if not line.strip():
            out.append(line)
            continue
        indent = line[: len(line) - len(line.lstrip(" "))]
        ls = line.lstrip(" ")
        m = _RE_ATX_HEADING.match(ls)
        if m:
            title = m.group(2)
            em = _RE_ATX_EMBED_IN_TITLE.match(title)
            if em:
                first = em.group(1).rstrip()
                rest = em.group(2)
                if first:
                    out.append(f"{indent}{m.group(1)} {first}")
                    out.append(f"{indent}{rest}")
                    continue
        out.append(line)
    return out


def outline_plain_title(htext: str) -> str:
    """Plain text for bookmarks/outline (no XML / MD bold, etc.)."""
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", htext)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return t.strip()


class LeftRuleCodeBlock(Flowable):
    """
    Code block with a brand-colored left bar (any2pdf ``code_style: border`` / left-accent pattern).
    Inner flowable (usually Paragraph) is drawn to the right of the bar.
    """

    def __init__(self, inner: Flowable, *, rule_w_pt: float = 2.0, rule_color: colors.Color, gap_pt: float = 5.0):
        Flowable.__init__(self)
        self._inner = inner
        self._rule_w = rule_w_pt
        self._color = rule_color
        self._gap = gap_pt

    def wrap(self, availWidth, availHeight):
        inner_w = max(1.0, availWidth - self._rule_w - self._gap)
        w, h = self._inner.wrap(inner_w, availHeight)
        self.width = float(availWidth)
        self.height = float(h)
        return (self.width, self.height)

    def draw(self):
        self.canv.saveState()
        self.canv.setStrokeColor(self._color)
        self.canv.setLineWidth(self._rule_w)
        x = self._rule_w * 0.5
        self.canv.line(x, 0, x, self.height)
        self.canv.restoreState()
        self._inner.drawOn(self.canv, self._rule_w + self._gap, 0)


class FencedCodeCardTable(Flowable):
    """
    Three rows, one column: **pre-gap** (``Spacer``) + lang bar + body.

    The pre-gap is **inside** this flowable (not a separate ``story`` ``Spacer``) so
    ``MDPDF_FENCED_CARD_ABOVE_MM`` changes the **row-0** height in one layout object.
    A standalone ``Spacer`` before a ``KeepTogether`` can sit awkwardly with ReportLab
    ``overlapAttachedSpace`` vs the previous paragraph’s ``spaceAfter`` — users may see
    little difference when tuning mm **only** in that case.
    """

    def __init__(
        self,
        pre_pad_mm: float,
        hdr: Paragraph,
        make_row2: Callable[[float], Flowable],
        top_pad_body_pt: float,
    ) -> None:
        Flowable.__init__(self)
        self._pre_pad_mm = max(0.0, pre_pad_mm)
        self._hdr = hdr
        self._make_row2 = make_row2
        self._top_pad = top_pad_body_pt
        self._t: Table | None = None

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        r2 = self._make_row2(availWidth)
        pre_h = self._pre_pad_mm * mm
        gap = Spacer(1, pre_h) if pre_h > _FUZZ else Spacer(1, 0.0)
        t = Table([[gap], [self._hdr], [r2]], colWidths=[availWidth])
        t.hAlign = "LEFT"
        ts: list[tuple] = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 0),
            # Header row padding (replaces Paragraph borderPadding)
            ("LEFTPADDING", (0, 1), (0, 1), 8),
            ("RIGHTPADDING", (0, 1), (0, 1), 5),
            ("TOPPADDING", (0, 1), (0, 1), 3),
            ("BOTTOMPADDING", (0, 1), (0, 1), 4),
            # Body row padding (replaces Paragraph borderPadding); extra ``self._top_pad`` keeps seam breathable
            ("LEFTPADDING", (0, 2), (0, 2), 6),
            ("RIGHTPADDING", (0, 2), (0, 2), 6),
            ("TOPPADDING", (0, 2), (0, 2), 12 + self._top_pad),
            ("BOTTOMPADDING", (0, 2), (0, 2), 6),
            # Backgrounds + borders are owned by the table to avoid Paragraph backColor/border overlap artifacts
            ("BACKGROUND", (0, 1), (0, 1), _FENCED_GH_HDR_BG),
            ("BACKGROUND", (0, 2), (0, 2), _FENCED_GH_CODE_BG),
            ("BOX", (0, 1), (0, 2), 0.5, _FENCED_GH_BORDER),
            # Single seam between lang bar and code
            ("LINEBELOW", (0, 1), (0, 1), 0.5, _FENCED_GH_BORDER),
        ]
        if os.environ.get("MDPDF_DEBUG_FENCES", "").strip() == "1":
            # Make the pre-gap (row 0) visually obvious during debugging
            ts.extend(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#ffeef0")),
                    ("LINEBELOW", (0, 0), (0, 0), 0.75, colors.HexColor("#cf222e")),
                ]
            )
        t.setStyle(TableStyle(ts))
        w, h = t.wrap(availWidth, availHeight)
        self._t = t
        self.width = w
        self.height = h
        return w, h

    def draw(self) -> None:
        if self._t is not None:
            self._t.drawOn(self.canv, 0, 0)


class OutlineBookmarkFlowable(Flowable):
    """Zero-height flowable: register named destination and PDF outline entry at current frame position."""

    def __init__(self, title: str, level: int, key: str):
        Flowable.__init__(self)
        self._title = title
        self._level = level
        self._key = key

    def wrap(self, availWidth, availHeight):
        return (0, 0)

    def draw(self):
        self.canv.bookmarkPage(self._key)
        self.canv.addOutlineEntry(self._title, self._key, level=self._level, closed=False)


def consume_markdown_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    j = start
    while j < len(lines) and lines[j].strip().startswith("|"):
        raw = lines[j].strip()
        if re.match(r"^\|\s*:?-{3,}", raw):
            j += 1
            continue
        cells = [c.strip() for c in raw.strip("|").split("|")]
        rows.append(cells)
        j += 1
    return rows, j


def consume_fenced_code_block(lines: list[str], start: int) -> tuple[str, list[str], int]:
    """Returns (lang tag lowercased, body lines without fences, next line index). If unclosed, reads to EOF."""
    first = lines[start].strip()
    if not first.startswith("```"):
        return "", [], start
    lang = first[3:].strip().lower()
    body: list[str] = []
    i = start + 1
    while i < len(lines):
        if lines[i].strip() == "```":
            return lang, body, i + 1
        body.append(lines[i])
        i += 1
    return lang, body, i


def normalize_fence_lang(raw: str) -> str:
    """First fence language token, lowercased; strip ```mermaid{...}``-style brace suffix on the token."""
    s = (raw or "").strip().lower()
    if not s:
        return ""
    token = s.split(None, 1)[0]
    if "{" in token:
        token = token.split("{", 1)[0]
    return token.strip()


# Mermaid: optional YAML front matter with ``title:`` (Mermaid 9+)
_RE_MERMAID_TITLE_LINE = re.compile(r"^[\s\u200b\u200c]*title\s*:\s*(.*)$")


def extract_mermaid_frontmatter_title(mermaid_source: str) -> str | None:
    """If the diagram starts with ``---\n ... \n---`` and a ``title:`` line, return its value; else None."""
    lines = mermaid_source.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for k in range(1, len(lines)):
        if lines[k].strip() == "---":
            block = "\n".join(lines[1:k])
            for line in block.splitlines():
                m = _RE_MERMAID_TITLE_LINE.match(line)
                if m:
                    raw = m.group(1).strip()
                    if not raw or raw.startswith("#"):
                        continue
                    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
                        raw = raw[1:-1]
                    return raw.strip() or None
            return None
    return None


def find_preceding_atx_heading_for_fence(lines: list[str], open_fence_idx: int) -> str | None:
    """
    Nearest material ATX heading above a fence opening line: scan backward, skip blank lines
    and horizontal rules, take the first ``# ...`` title (plain text for caption).
    """
    j = open_fence_idx - 1
    while j >= 0:
        s = lines[j].strip()
        if not s:
            j -= 1
            continue
        if s == "---" and len(s) == 3:
            j -= 1
            continue
        m = _RE_ATX_HEADING.match(s)
        if m:
            return outline_plain_title(m.group(2))
        j -= 1
    return None


def resolve_mermaid_caption_text(lines: list[str], open_fence_idx: int, mermaid_source: str) -> str | None:
    """Caption when YAML ``title:`` in diagram, else last ATX heading above the fence; no fixed English placeholder."""
    t = extract_mermaid_frontmatter_title(mermaid_source)
    if t:
        return t
    t = find_preceding_atx_heading_for_fence(lines, open_fence_idx)
    return t if t else None


def _is_exe_file(p: Path) -> bool:
    return p.is_file() and os.access(p, os.X_OK)


def _nvm_node_bin_dirs() -> list[str]:
    base = Path.home() / ".nvm" / "versions" / "node"
    if not base.is_dir():
        return []
    bins: list[tuple[tuple[int, ...], str]] = []
    for child in base.iterdir():
        if not child.is_dir():
            continue
        b = child / "bin"
        if not b.is_dir():
            continue
        name = child.name
        key = (0,)
        if name.startswith("v"):
            try:
                segs = [int(x) for x in name[1:].split(".") if x.isdigit()]
                key = tuple(segs) if segs else (0,)
            except ValueError:
                key = (0,)
        bins.append((key, str(b)))
    bins.sort(key=lambda t: t[0], reverse=True)
    return [s for _, s in bins]


def _enriched_path() -> str:
    """Merge common npm global / nvm bins into PATH (Cursor/IDE child processes often miss them) for mmdc/npm/npx."""
    h = Path.home()
    extra: list[str] = []
    for d in (
        h / ".npm-global" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        h / ".volta" / "bin",
        h / ".local" / "share" / "fnm" / "aliases" / "default" / "bin",
    ):
        if d.is_dir():
            extra.append(str(d))
    extra.extend(_nvm_node_bin_dirs())
    if os.name == "nt":
        roaming = h / "AppData" / "Roaming" / "npm"
        if roaming.is_dir():
            extra.append(str(roaming))
    tail = os.environ.get("PATH", "")
    return os.pathsep.join([*extra, tail] if tail else extra)


def _which_on_path(executable: str, path_str: str) -> str | None:
    """Find executable on path_str without relying on shutil.which(path=) (Python 3.12+)."""
    ext = (".exe", ".bat", ".cmd") if os.name == "nt" else ("",)
    for d in path_str.split(os.pathsep):
        if not d.strip():
            continue
        for e in ext:
            name = executable + e if e else executable
            p = Path(d) / name
            if _is_exe_file(p):
                return str(p)
    return None


def resolve_mmdc_executable() -> str | None:
    """
    Resolve absolute mmdc path: enriched PATH, then common absolute paths, then npm prefix -g / npm bin -g
    (npm subprocess uses the same enriched PATH).
    """
    ep = _enriched_path()
    w = _which_on_path("mmdc", ep)
    if w:
        return w
    for p in (
        Path("/opt/homebrew/bin/mmdc"),
        Path("/usr/local/bin/mmdc"),
        Path.home() / ".npm-global" / "bin" / "mmdc",
    ):
        if _is_exe_file(p):
            return str(p)
    npm_exe = _which_on_path("npm", ep)
    if not npm_exe:
        return None
    env = os.environ.copy()
    env["PATH"] = ep
    try:
        r = subprocess.run(
            [npm_exe, "prefix", "-g"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        if r.returncode == 0 and r.stdout.strip():
            prefix = Path(r.stdout.strip().splitlines()[-1])
            cand = prefix / "bin" / "mmdc"
            if _is_exe_file(cand):
                return str(cand)
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        r = subprocess.run(
            [npm_exe, "bin", "-g"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
        if r.returncode == 0 and r.stdout.strip():
            bindir = Path(r.stdout.strip().splitlines()[-1])
            cand = bindir / "mmdc"
            if _is_exe_file(cand):
                return str(cand)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _mermaid_verbose_enabled() -> bool:
    v = os.environ.get("MDPDF_MERMAID_VERBOSE", "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _mermaid_verbose_log(message: str) -> None:
    if _mermaid_verbose_enabled():
        print(f"[mdpdf-mermaid] {message}", file=sys.stderr)


_mmdc_version_logged = False


def _mermaid_log_mmdc_version_once() -> None:
    """Log `mmdc --version` once per process when verbose (best-effort)."""
    global _mmdc_version_logged
    if not _mermaid_verbose_enabled() or _mmdc_version_logged:
        return
    _mmdc_version_logged = True
    exe = resolve_mmdc_executable()
    if not exe:
        _mermaid_verbose_log("mmdc --version: skipped (mmdc not resolved on PATH)")
        return
    env = os.environ.copy()
    env["PATH"] = _enriched_path()
    try:
        r = subprocess.run(
            [exe, "--version"],
            check=False,
            capture_output=True,
            timeout=15,
            env=env,
        )
        out = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", errors="replace").strip()[:240]
        _mermaid_verbose_log(f"mmdc --version: {out!r}")
    except (OSError, subprocess.TimeoutExpired) as e:
        _mermaid_verbose_log(f"mmdc --version failed: {e}")


def _ensure_mdpdf_puppeteer_cache_dir() -> Path | None:
    try:
        MDPDF_PUPPETEER_CACHE.mkdir(parents=True, exist_ok=True)
        return MDPDF_PUPPETEER_CACHE
    except OSError:
        try:
            fallback = Path.home() / ".cache" / "mdpdf-puppeteer"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
        except OSError:
            return None


def _darwin_puppeteer_cache_binaries() -> tuple[Path | None, Path | None]:
    """
    Newest ``chrome-headless-shell`` and newest ``Google Chrome for Testing`` under Puppeteer
    cache roots. Headless-shell is the preferred automation entrypoint on macOS. Full
    ``Google Chrome.app`` and often ``Chrome for Testing`` can ``SIGABRT`` when mmdc/Puppeteer
    launches them as a child of Cursor — see ``_apply_mermaid_puppeteer_env``.
    """
    roots = [
        MDPDF_PUPPETEER_CACHE,
        Path.home() / ".cache" / "puppeteer",
        Path.home() / ".cache" / "mdpdf-puppeteer",
    ]
    headless: list[Path] = []
    cft: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for p in root.rglob("chrome-headless-shell"):
                if p.is_file() and os.access(p, os.X_OK):
                    headless.append(p)
            for p in root.rglob("Google Chrome for Testing"):
                if p.is_file() and os.access(p, os.X_OK):
                    cft.append(p)
        except OSError:
            continue
    h: Path | None = None
    c: Path | None = None
    if headless:
        h = max(headless, key=lambda x: x.stat().st_mtime)
    if cft:
        c = max(cft, key=lambda x: x.stat().st_mtime)
    return h, c


def _windows_puppeteer_downloaded_browser() -> Path | None:
    """
    Windows: search %USERPROFILE%\\.cache\\puppeteer (and mdpdf-puppeteer) for
    chrome-headless-shell.exe / chrome.exe (chrome-win layout paths containing puppeteer).
    Prefer headless-shell; else newest chrome.exe by mtime.
    """
    roots = [
        MDPDF_PUPPETEER_CACHE,
        Path.home() / ".cache" / "puppeteer",
        Path.home() / ".cache" / "mdpdf-puppeteer",
    ]
    headless: list[Path] = []
    chrome: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for p in root.rglob("chrome-headless-shell.exe"):
                if p.is_file():
                    headless.append(p)
            for p in root.rglob("chrome.exe"):
                if not p.is_file():
                    continue
                low = str(p).replace("\\", "/").lower()
                if "puppeteer" not in low:
                    continue
                if "chrome-win" not in low and "win64" not in low:
                    continue
                chrome.append(p)
        except OSError:
            continue
    pick: list[Path] = sorted(headless, key=lambda x: x.stat().st_mtime, reverse=True)
    if not pick:
        pick = sorted(chrome, key=lambda x: x.stat().st_mtime, reverse=True)
    return pick[0] if pick else None


def _puppeteer_cache_dir_only(env: dict[str, str]) -> None:
    """
    If ``PUPPETEER_CACHE_DIR`` is empty or a Cursor sandbox path, set the repo mdpdf cache directory.
    Does not set ``PUPPETEER_EXECUTABLE_PATH``; used when cycling macOS browser binaries for mmdc.
    """
    _mermaid_verbose_log(
        "env (incoming): PUPPETEER_EXECUTABLE_PATH=%r PUPPETEER_CACHE_DIR=%r"
        % (env.get("PUPPETEER_EXECUTABLE_PATH"), env.get("PUPPETEER_CACHE_DIR"))
    )
    cache = env.get("PUPPETEER_CACHE_DIR", "")
    cache_norm = cache.replace("\\", "/").lower()
    reset_cache = (
        not cache.strip()
        or "cursor-sandbox" in cache_norm
        or "sandbox-cache" in cache_norm
    )
    if reset_cache:
        d = _ensure_mdpdf_puppeteer_cache_dir()
        if d is not None:
            env["PUPPETEER_CACHE_DIR"] = str(d)


def _darwin_mermaid_browser_candidates() -> list[Path]:
    """
    Ordered unique browser executables to try for mmdc on macOS (same priority as
    ``_apply_mermaid_puppeteer_env``; excludes stable Chrome unless allow-env is set).

    **No early return** of cache-only (e.g. only **Google Chrome for Testing**): that skipped
    system Edge/Chromium and was unreliable under Cursor. The list always follows full priority.
    """
    h_cache, cft_cache = _darwin_puppeteer_cache_binaries()
    _allow_darwin_stable_chrome = os.environ.get(
        "MDPDF_PUPPETEER_ALLOW_DARWIN_STABLE_CHROME", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    _skip_cft = _env_truthy("MDPDF_PUPPETEER_SKIP_CFT")
    d_edge = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
    d_chromium = Path("/Applications/Chromium.app/Contents/MacOS/Chromium")
    d_chrome_beta = Path(
        "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta"
    )
    d_chrome_stable = Path(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    # Headless first, then system installs, then CFT in cache; stable only if allow-env
    seq = (
        h_cache,
        d_edge,
        d_chromium,
        d_chrome_beta,
        cft_cache,
        d_chrome_stable if _allow_darwin_stable_chrome else None,
    )
    out2: list[Path] = []
    seen2: set[str] = set()
    for pick in seq:
        if pick is None:
            continue
        if _skip_cft and cft_cache is not None and pick == cft_cache:
            continue
        if not (pick.is_file() and os.access(pick, os.X_OK)):
            continue
        k2 = str(pick.resolve())
        if k2 in seen2:
            continue
        seen2.add(k2)
        out2.append(pick)
    return out2


def _apply_mermaid_puppeteer_env(env: dict[str, str]) -> None:
    """
    Cursor/CI sandboxes often point Puppeteer cache at a temp dir without Chromium, so mmdc fails with
    Could not find Chrome. Redirect cache to repo-local tools/.mdpdf-puppeteer-cache/ (gitignored, beside
    Playwright); fallback ~/.cache/mdpdf-puppeteer if that cannot be created.
    If PUPPETEER_EXECUTABLE_PATH is unset: **macOS** order is
    (1) ``chrome-headless-shell`` in the Puppeteer cache (best for mmdc + Cursor),
    (2) system Edge, Chromium, Chrome Beta,
    (3) ``Google Chrome for Testing`` in cache,
    (4) **/Applications/Google Chrome.app** only if ``MDPDF_PUPPETEER_ALLOW_DARWIN_STABLE_CHROME=1`` —
    the stable main bundle often **SIGABRT**s when launched for automation from a Cursor child process.
    ``MDPDF_PUPPETEER_CACHE_FIRST=1`` returns early **only** if **headless-shell** exists in cache; it
    does **not** fall back to Chrome for Testing alone (that skipped system Edge and was unstable).
    ``MDPDF_PUPPETEER_SKIP_CFT=1`` omits **Google Chrome for Testing** from the candidate list.
    **Windows:** Puppeteer cache, then Edge / Chrome. **Linux:** common chrome/chromium paths.
    """
    _puppeteer_cache_dir_only(env)
    if env.get("PUPPETEER_EXECUTABLE_PATH"):
        _mermaid_verbose_log("using existing PUPPETEER_EXECUTABLE_PATH (user or parent env)")
        return
    h_cache, cft_cache = (None, None)
    if sys.platform == "darwin":
        h_cache, cft_cache = _darwin_puppeteer_cache_binaries()
    _cache_first = os.environ.get("MDPDF_PUPPETEER_CACHE_FIRST", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    _allow_darwin_stable_chrome = os.environ.get(
        "MDPDF_PUPPETEER_ALLOW_DARWIN_STABLE_CHROME", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    d_edge = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
    d_chromium = Path("/Applications/Chromium.app/Contents/MacOS/Chromium")
    d_chrome_beta = Path(
        "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta"
    )
    d_chrome_stable = Path(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    _skip_cft = _env_truthy("MDPDF_PUPPETEER_SKIP_CFT")
    if sys.platform == "darwin":
        if _cache_first and h_cache is not None:
            env["PUPPETEER_EXECUTABLE_PATH"] = str(h_cache)
            _mermaid_verbose_log(
                f"PUPPETEER_EXECUTABLE_PATH (puppeteer headless-shell, macOS)={h_cache} "
                "[MDPDF_PUPPETEER_CACHE_FIRST]"
            )
            _mermaid_verbose_log(
                f"PUPPETEER_CACHE_DIR (effective)={env.get('PUPPETEER_CACHE_DIR')}"
            )
            return
        for pick in (
            h_cache,
            d_edge,
            d_chromium,
            d_chrome_beta,
            cft_cache,
            d_chrome_stable if _allow_darwin_stable_chrome else None,
        ):
            if pick is None:
                continue
            if _skip_cft and cft_cache is not None and pick == cft_cache:
                continue
            if pick.is_file() and os.access(pick, os.X_OK):
                env["PUPPETEER_EXECUTABLE_PATH"] = str(pick)
                if h_cache is not None and pick == h_cache:
                    _mermaid_verbose_log(
                        f"PUPPETEER_EXECUTABLE_PATH (puppeteer headless-shell, macOS)={pick}"
                    )
                elif cft_cache is not None and pick == cft_cache:
                    _mermaid_verbose_log(
                        f"PUPPETEER_EXECUTABLE_PATH (Google Chrome for Testing, macOS)={pick}"
                    )
                else:
                    _mermaid_verbose_log(
                        f"PUPPETEER_EXECUTABLE_PATH (application bundle binary, macOS)={pick}"
                    )
                break
    candidates: list[Path] = []
    if sys.platform.startswith("linux"):
        candidates = [
            Path("/usr/bin/google-chrome-stable"),
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
        ]
    elif os.name == "nt":
        _ppw = _windows_puppeteer_downloaded_browser()
        if _ppw is not None:
            env["PUPPETEER_EXECUTABLE_PATH"] = str(_ppw)
            _mermaid_verbose_log(f"PUPPETEER_EXECUTABLE_PATH (puppeteer cache, Windows)={_ppw}")
            _mermaid_verbose_log(f"PUPPETEER_CACHE_DIR (effective)={env.get('PUPPETEER_CACHE_DIR')}")
            return
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pfx86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(pfx86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ]
        if local.strip():
            candidates.append(
                Path(local) / "Microsoft" / "Edge SxS" / "Application" / "msedge.exe",
            )
        candidates.extend(
            [
                Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
                Path(pfx86) / "Google" / "Chrome" / "Application" / "chrome.exe",
            ]
        )
    for p in candidates:
        if p.is_file() and (os.name == "nt" or os.access(p, os.X_OK)):
            env["PUPPETEER_EXECUTABLE_PATH"] = str(p)
            _mermaid_verbose_log(f"PUPPETEER_EXECUTABLE_PATH (system candidate)={p}")
            break
    if not env.get("PUPPETEER_EXECUTABLE_PATH"):
        _mermaid_verbose_log(
            "PUPPETEER_EXECUTABLE_PATH still unset; mmdc / Puppeteer will use bundled or PATH defaults"
        )
    else:
        _mermaid_verbose_log(f"PUPPETEER_CACHE_DIR (effective)={env.get('PUPPETEER_CACHE_DIR')}")


def resolve_mermaid_preset(cli_value: str | None) -> str:
    """Effective preset E / S / H: CLI overrides env; getenv default S; invalid → S."""
    if cli_value is not None and str(cli_value).strip() != "":
        raw = str(cli_value).strip().upper()
        src = "cli"
    else:
        raw = os.getenv("MDPDF_MERMAID_PRESET", "S").strip().upper() or "S"
        src = "env"
    if raw not in MERMAID_PRESET_DIMENSIONS:
        if _mermaid_verbose_enabled():
            print(
                f"[mdpdf-mermaid] invalid mermaid preset {raw!r} (from {src}); using S",
                file=sys.stderr,
            )
        return "S"
    return raw


def ensure_mermaid_brand_css_file(workdir: Path) -> Path | None:
    """Write one mdpdf-mermaid.css per workdir with @font-face for bundled Noto; None if TTFs missing."""
    out = workdir / MERMAID_CSS_FILENAME
    if out.is_file():
        return out
    reg = FONTS_DIR / "NotoSansSC-Regular.ttf"
    bold = FONTS_DIR / "NotoSansSC-Bold.ttf"
    if not reg.is_file() or not bold.is_file():
        if _mermaid_verbose_enabled():
            _mermaid_verbose_log(
                "Mermaid Noto injection skipped: missing fonts/NotoSansSC-Regular.ttf or NotoSansSC-Bold.ttf"
            )
        return None
    try:
        reg_uri = reg.resolve().as_uri()
        bold_uri = bold.resolve().as_uri()
    except OSError:
        if _mermaid_verbose_enabled():
            _mermaid_verbose_log("Mermaid Noto injection skipped: could not build file URI for fonts")
        return None
    fam = MERMAID_NOTO_FAMILY
    css = (
        f"@font-face {{\n  font-family: '{fam}';\n  font-style: normal;\n  font-weight: 400;\n"
        f"  src: url('{reg_uri}') format('truetype');\n}}\n"
        f"@font-face {{\n  font-family: '{fam}';\n  font-style: normal;\n  font-weight: 700;\n"
        f"  src: url('{bold_uri}') format('truetype');\n}}\n"
        f"svg text, .nodeLabel, .nodeLabel span, .edgeLabel, .edgeLabel span,\n"
        f".messageText, .actor, .actor text, foreignObject, foreignObject p,\n"
        f".flowchartTitleText, .classTitleText, .stateLabel {{\n"
        f"  font-family: '{fam}', 'Noto Sans SC', sans-serif !important;\n}}\n"
    )
    try:
        out.write_text(css, encoding="utf-8")
    except OSError:
        return None
    return out


def _mermaid_mmdc_argv_tail(
    w: int,
    h: int,
    css_path: Path | None,
    config_path: Path | None,
) -> list[str]:
    tail: list[str] = ["-w", str(w), "-H", str(h)]
    if css_path is not None:
        tail.extend(["-C", str(css_path)])
    if config_path is not None:
        tail.extend(["-c", str(config_path)])
    return tail


def render_mermaid_to_png(
    source: str,
    workdir: Path,
    preset: str = "S",
) -> tuple[Path | None, str]:
    """
    Run mmdc to render Mermaid source to PNG.
    Returns (png_path | None, reason). reason: "" on success;
    "no_mmdc" | "cli_failed" | "no_png" | "too_large:…".
    """
    max_mc = _env_int("MDPDF_MERMAID_MAX_CHARS", _DEFAULT_MERMAID_MAX_CHARS)
    if len(source) > max_mc:
        return None, (
            f"too_large:Diagram source exceeds {max_mc} characters "
            "(MDPDF_MERMAID_MAX_CHARS). Shorten the diagram or raise the limit."
        )

    workdir.mkdir(parents=True, exist_ok=True)
    preset_u = preset.strip().upper() if preset.strip().upper() in MERMAID_PRESET_DIMENSIONS else "S"
    w, h = MERMAID_PRESET_DIMENSIONS[preset_u]
    timeout_sec = MERMAID_SUBPROCESS_TIMEOUT_HIGH if preset_u == "H" else MERMAID_SUBPROCESS_TIMEOUT_SHORT

    _mermaid_log_mmdc_version_once()

    uid = os.urandom(4).hex()
    mmd_path = workdir / f"mermaid_{uid}.mmd"
    png_path = workdir / f"mermaid_{uid}.png"
    mmd_path.write_text(source.strip() + "\n", encoding="utf-8")
    if png_path.exists():
        png_path.unlink()

    ep = _enriched_path()
    user_pe = (os.environ.get("PUPPETEER_EXECUTABLE_PATH") or "").strip()

    css_path = ensure_mermaid_brand_css_file(workdir)
    config_path: Path | None = None
    if css_path is not None and MERMAID_CONFIG_PATH.is_file():
        config_path = MERMAID_CONFIG_PATH.resolve()
    elif css_path is None and _mermaid_verbose_enabled():
        _mermaid_verbose_log(
            "Mermaid Noto CSS/config injection skipped (missing fonts/NotoSansSC-*.ttf); mmdc uses browser default fonts"
        )
    elif (
        css_path is not None
        and not MERMAID_CONFIG_PATH.is_file()
        and _mermaid_verbose_enabled()
    ):
        _mermaid_verbose_log(
            f"Mermaid theme JSON missing ({MERMAID_CONFIG_PATH}); mmdc runs with -C CSS only"
        )
    argv_tail = _mermaid_mmdc_argv_tail(w, h, css_path, config_path)
    if _mermaid_verbose_enabled():
        _mermaid_verbose_log(f"mmdc inject: -C={css_path!s} -c={config_path!s}")

    cmd_variants: list[list[str]] = []
    mmdc_exe = resolve_mmdc_executable()
    _mermaid_verbose_log(
        f"render_mermaid workdir={workdir} mmd={mmd_path.name} mmdc_exe={mmdc_exe!r} preset={preset_u} {w}x{h}"
    )
    if mmdc_exe:
        cmd_variants.append(
            [mmdc_exe, "-i", str(mmd_path), "-o", str(png_path), "-b", "white", *argv_tail]
        )
    _npx_flag = os.environ.get("MDPDF_MERMAID_NPX", "").strip().lower()
    npx_exe = _which_on_path("npx", ep)
    if _npx_flag in ("1", "true", "yes") and npx_exe:
        cmd_variants.append(
            [
                npx_exe,
                "--yes",
                "-p",
                "@mermaid-js/mermaid-cli",
                "mmdc",
                "-i",
                str(mmd_path),
                "-o",
                str(png_path),
                "-b",
                "white",
                *argv_tail,
            ]
        )

    if not cmd_variants:
        try:
            mmd_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None, "no_mmdc"

    def _run_mmdc_variants(effective_env: dict[str, str]) -> tuple[Path | None, str]:
        last: str = ""
        for cmd in cmd_variants:
            _mermaid_verbose_log("mmdc argv: " + " ".join(cmd))
            try:
                r = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    timeout=timeout_sec,
                    cwd=str(workdir),
                    env=effective_env,
                )
            except (subprocess.TimeoutExpired, OSError) as e:
                last = str(e)
                _mermaid_verbose_log(f"mmdc subprocess error: {last}")
                continue
            if r.returncode != 0:
                err = (r.stderr or b"") + (r.stdout or b"")
                try:
                    last = err.decode("utf-8", errors="replace")[:800]
                except Exception:
                    last = repr(err)[:400]
                _mermaid_verbose_log(
                    f"mmdc exit_code={r.returncode} stderr+stdout (truncated 400): {last[:400]!r}"
                )
                continue
            if png_path.is_file() and png_path.stat().st_size > 200:
                try:
                    mmd_path.unlink(missing_ok=True)
                except OSError:
                    pass
                _mermaid_verbose_log(
                    f"mmdc ok -> {png_path.name} size={png_path.stat().st_size} bytes"
                )
                return png_path, ""
            last = "mmdc exit 0 but PNG missing or smaller than 200 bytes"
            _mermaid_verbose_log(last)
        return None, last

    last_err: str = ""
    if user_pe:
        e_user = os.environ.copy()
        e_user["PATH"] = ep
        _puppeteer_cache_dir_only(e_user)
        png, last_err = _run_mmdc_variants(e_user)
        if png is not None:
            return png, ""
    else:
        cands: list[Path] = (
            _darwin_mermaid_browser_candidates() if sys.platform == "darwin" else []
        )
        if cands:
            n_c = len(cands)
            for b_idx, pex in enumerate(cands):
                e_try = os.environ.copy()
                e_try["PATH"] = ep
                _puppeteer_cache_dir_only(e_try)
                e_try["PUPPETEER_EXECUTABLE_PATH"] = str(pex)
                if _mermaid_verbose_enabled():
                    _mermaid_verbose_log(
                        f"mmdc browser try {b_idx + 1}/{n_c} PUPPETEER_EXECUTABLE_PATH={pex}"
                    )
                png, err1 = _run_mmdc_variants(e_try)
                if png is not None:
                    return png, ""
                last_err = err1
        else:
            e_fb = os.environ.copy()
            e_fb["PATH"] = ep
            _apply_mermaid_puppeteer_env(e_fb)
            png, last_err = _run_mmdc_variants(e_fb)
            if png is not None:
                return png, ""

    try:
        mmd_path.unlink(missing_ok=True)
    except OSError:
        pass
    if png_path.exists():
        try:
            png_path.unlink(missing_ok=True)
        except OSError:
            pass
    if mmdc_exe and last_err:
        return None, "cli_failed:" + last_err
    if mmdc_exe:
        return None, "no_png"
    return None, "no_mmdc"


def mermaid_png_scaled_dimensions(png_path: Path, max_width_pt: float) -> tuple[float, float]:
    """Scaled width/height in points for embedding (matches mermaid_png_to_flowable)."""
    ir = ImageReader(str(png_path))
    px_w, px_h = ir.getSize()
    if px_w <= 0 or px_h <= 0:
        px_w, px_h = 800, 600
    w_pt = px_w * (72.0 / 96.0)
    h_pt = px_h * (72.0 / 96.0)
    if w_pt > max_width_pt:
        s = max_width_pt / w_pt
        w_pt = max_width_pt
        h_pt = h_pt * s
    if h_pt > MERMAID_MAX_HEIGHT_PT:
        s = MERMAID_MAX_HEIGHT_PT / h_pt
        h_pt = MERMAID_MAX_HEIGHT_PT
        w_pt = w_pt * s
    return w_pt, h_pt


def mermaid_png_to_flowable(png_path: Path, max_width_pt: float) -> RLImage:
    """Scale to max text width; cap height at MERMAID_MAX_HEIGHT_PT."""
    w_pt, h_pt = mermaid_png_scaled_dimensions(png_path, max_width_pt)
    return RLImage(str(png_path), width=w_pt, height=h_pt)


def _table_strip_inline_md(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    return s.strip()


# Excel-style cell refs: # A1, A2, or #A1, B2
_RE_TAG_REF_PART = re.compile(r"^[A-Za-z]{1,3}\d{1,7}(?:[-_][A-Za-z0-9]+)?$")


def _is_tag_ref_cell(plain: str) -> bool:
    t = _table_strip_inline_md(plain)
    if not t or len(t) > 160:
        return False
    parts = re.split(r"[,，、]\s*", t)
    if not parts:
        return False
    for p in parts:
        p = re.sub(r"^\s*#\s*", "", p.strip())
        if not p or not _RE_TAG_REF_PART.match(p):
            return False
    return True


def _parse_financial_amount(plain: str) -> tuple[float, bool, bool] | None:
    """
    If the whole cell is an amount/financial number, return (value, is_negative, is_percent); else None.
    Percent cells: e.g. 12.34% → two decimal places and keep %.
    """
    raw = _table_strip_inline_md(plain)
    if not raw or len(raw) > 88:
        return None
    s = raw.replace("，", ",").replace("．", ".").strip()
    s = re.sub(r"\s+", "", s)
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    elif s and s[0] in "-−":
        neg = True
        s = s[1:]
    if not s:
        return None
    pct = False
    if s.endswith("%") or s.endswith("％"):
        pct = True
        s = s[:-1]
    s = re.sub(r"^[$€£￥¥]+", "", s)
    s = re.sub(r"[$€£￥¥]+$", "", s)
    s = s.replace(",", "")
    if not re.match(r"^\d+(?:\.\d+)?$", s):
        return None
    try:
        v = float(s)
        if pct:
            pass  # keep numeric part as percent body (e.g. 12.34)
        if neg:
            v = -abs(v)
        return (v, v < 0, pct)
    except ValueError:
        return None


def _format_financial_cell_xml(plain: str) -> str | None:
    """Amount cell → ReportLab Paragraph XML; None if not an amount."""
    parsed = _parse_financial_amount(plain)
    if parsed is None:
        return None
    v, is_neg, is_pct = parsed
    if is_pct:
        body = f"{abs(v):,.2f}%"
    else:
        body = f"{abs(v):,.2f}"
    if is_neg:
        body = "-" + body
    eb = esc(body)
    if is_neg:
        hx = _color_xml_hex(get_brand_pack().theme.color_table_fin_negative)
        return f'<font color="{hx}">{eb}</font>'
    return eb


_table_para_style_i = 0


def _next_table_para_style_name(prefix: str) -> str:
    global _table_para_style_i
    _table_para_style_i += 1
    return f"IDS-Tbl-{prefix}-{_table_para_style_i}"


def table_cell_paragraph(
    cell: str,
    font: str,
    font_bold: str,
    fs: float,
    ld: float,
    *,
    header: bool,
) -> Paragraph:
    """Header: centered + bold. Body: L/R/C per amount and cell-ref rules."""
    th = get_brand_pack().theme
    if header:
        st = ParagraphStyle(
            _next_table_para_style_name("H"),
            fontName=font_bold if font_bold != font else font,
            fontSize=fs,
            leading=ld,
            alignment=TA_CENTER,
            textColor=th.color_brand,
            wordWrap="CJK",
        )
        return Paragraph(md_inline_to_xml(cell), st)

    plain = cell
    if _is_tag_ref_cell(plain):
        st = ParagraphStyle(
            _next_table_para_style_name("C"),
            fontName=font,
            fontSize=fs,
            leading=ld,
            alignment=TA_CENTER,
            textColor=th.color_body,
            wordWrap="CJK",
        )
        return Paragraph(md_inline_to_xml(cell), st)

    fin_xml = _format_financial_cell_xml(plain)
    if fin_xml is not None:
        st = ParagraphStyle(
            _next_table_para_style_name("R"),
            fontName=font,
            fontSize=fs,
            leading=ld,
            alignment=TA_RIGHT,
            textColor=th.color_body,
            wordWrap="CJK",
        )
        return Paragraph(fin_xml, st)

    st = ParagraphStyle(
        _next_table_para_style_name("L"),
        fontName=font,
        fontSize=fs,
        leading=ld,
        alignment=TA_LEFT,
        textColor=th.color_body,
        wordWrap="CJK",
    )
    return Paragraph(md_inline_to_xml(cell), st)


def _table_cell_table_align(cell: str, header: bool) -> str:
    """ReportLab TableStyle ALIGN matching Paragraph alignment."""
    if header:
        return "CENTER"
    if _is_tag_ref_cell(cell):
        return "CENTER"
    if _format_financial_cell_xml(cell) is not None:
        return "RIGHT"
    return "LEFT"


def collect_bookmark_plain_to_key(lines: list[str]) -> dict[str, str]:
    """
    Pre-scan: same i-advance as build_story (outline keys) so we can build TOC row internal links
    to bookmarkPage names. First match wins for duplicate plain titles. Keys match ids-h-{n} order
    in the final PDF.
    """
    out: dict[str, str] = {}
    outline_key_i = 0
    outline_last_ol = -1

    def next_outline_key() -> str:
        nonlocal outline_key_i
        outline_key_i += 1
        return f"ids-h-{outline_key_i}"

    def effective_outline_level(md_lvl: int) -> int:
        nonlocal outline_last_ol
        want = md_lvl - 1
        if outline_last_ol < 0:
            ol = want
        elif want > outline_last_ol + 1:
            ol = outline_last_ol + 1
        else:
            ol = want
        outline_last_ol = ol
        return ol

    def reg_heading_with_key(raw_title: str, md_lvl: int) -> None:
        plain = outline_plain_title(raw_title).strip() or raw_title.strip() or "(untitled)"
        _ = effective_outline_level(md_lvl)
        key = next_outline_key()
        out.setdefault(plain, key)

    i = 0
    n = len(lines)
    doc_title = ""
    while i < n:
        stripped = lines[i].strip()

        if stripped == "## Version History":
            i += 1
            while i < n and not lines[i].strip():
                i += 1
            _vh_plain = outline_plain_title("Version History") or "Version History"
            _ = effective_outline_level(2)
            vhk = next_outline_key()
            out.setdefault(_vh_plain, vhk)
            if i < n and lines[i].strip().startswith("|"):
                _, i = consume_markdown_table(lines, i)
            continue

        toc_h2 = stripped[3:].strip() if stripped.startswith("## ") else ""
        if toc_h2 == "目录" or toc_h2.lower() == "table of contents":
            toc_display_title = "Table of Contents" if toc_h2 == "目录" else toc_h2
            _toc_plain = outline_plain_title(toc_display_title) or toc_display_title
            _ = effective_outline_level(2)
            tock = next_outline_key()
            out.setdefault(_toc_plain, tock)
            i += 1
            while i < n and not lines[i].strip():
                i += 1
            if i < n and lines[i].strip().startswith("|"):
                _, i = consume_markdown_table(lines, i)
            continue

        m = _RE_ATX_HEADING.match(stripped)
        if m:
            lvl = len(m.group(1))
            htxt = m.group(2).strip()
            if lvl == 1 and not doc_title:
                doc_title = htxt
                reg_heading_with_key(htxt, 1)
                i += 1
                continue
            if lvl == 1:
                reg_heading_with_key(htxt, 1)
                i += 1
                continue
            if lvl == 2:
                reg_heading_with_key(htxt, 2)
                i += 1
                continue
            if lvl == 3:
                reg_heading_with_key(htxt, 3)
                i += 1
                continue
            if lvl == 4:
                reg_heading_with_key(htxt, 4)
                i += 1
                continue
            if lvl == 5:
                reg_heading_with_key(htxt, 5)
                i += 1
                continue
            if lvl == 6:
                reg_heading_with_key(htxt, 6)
                i += 1
                continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            _, i = consume_markdown_table(lines, i)
            continue
        if stripped.startswith("> "):
            i += 1
            continue
        if stripped.startswith("- **") or (stripped.startswith("- ") and not stripped.startswith("---")):
            i += 1
            continue
        if stripped == "---":
            i += 1
            continue
        if stripped.startswith("**致**") or stripped.startswith("**日期**"):
            i += 1
            continue
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            _, _, next_i = consume_fenced_code_block(lines, i)
            i = next_i
            continue
        if re.match(r"^\d+\.\s", stripped):
            i += 1
            while i < n:
                s = lines[i].strip()
                if not s:
                    break
                if s.startswith(("#", "|", ">", "-", "---", "```")):
                    break
                if re.match(r"^\d+\.\s", s):
                    break
                i += 1
            continue

        buf: list[str] = []
        while i < n and lines[i].strip():
            s = lines[i].strip()
            if s.startswith(("#", "|", ">", "-", "---", "```")):
                break
            if re.match(r"^\d+\.\s", s):
                break
            buf.append(s)
            i += 1
        if not buf:
            i += 1
        continue

    return out


def lookup_toc_row_bookmark_key(usable: list[str], plain_to_key: dict[str, str]) -> str | None:
    """Match TOC pipe row to first heading in whole-doc map: try joined cells, then each cell."""
    cells = [c.strip() for c in usable if c and c.strip()]
    if not cells:
        return None
    for probe in (" · ".join(cells),) + tuple(cells):
        plain = outline_plain_title(probe).strip() or probe
        if plain in plain_to_key:
            return plain_to_key[plain]
    return None


def build_story(
    lines: list[str],
    font: str,
    font_bold: str,
    *,
    mermaid_workdir: Path | None = None,
    mermaid_preset: str = "S",
    code_font: str = "Courier",
) -> list:
    story: list = []
    bookmark_plain_to_key = collect_bookmark_plain_to_key(lines)
    th = get_brand_pack().theme
    frame_w_pt = A4[0] - 2 * PAGE_H_MARGIN_MM * mm

    title_style = ParagraphStyle(
        name="Title",
        fontName=font_bold if font_bold != font else font,
        fontSize=22,
        leading=28,
        textColor=th.color_brand,
        spaceAfter=6 * mm,
        alignment=TA_LEFT,
    )
    h2_style = ParagraphStyle(
        name="H2",
        fontName=font_bold if font_bold != font else font,
        fontSize=15,
        leading=20,
        textColor=th.color_brand,
        spaceBefore=4 * mm,
        spaceAfter=4 * mm,
        alignment=TA_LEFT,
    )
    h3_style = ParagraphStyle(
        name="H3",
        fontName=font_bold if font_bold != font else font,
        fontSize=11,
        leading=15,
        textColor=th.color_brand,
        spaceBefore=2 * mm,
        spaceAfter=2 * mm,
        alignment=TA_LEFT,
    )
    h4_style = ParagraphStyle(
        name="H4",
        fontName=font_bold if font_bold != font else font,
        fontSize=10,
        leading=14,
        textColor=th.color_brand,
        spaceBefore=1.5 * mm,
        spaceAfter=1.5 * mm,
        alignment=TA_LEFT,
    )
    h5_style = ParagraphStyle(
        name="H5",
        fontName=font_bold if font_bold != font else font,
        fontSize=9.5,
        leading=13,
        textColor=th.color_brand,
        spaceBefore=1 * mm,
        spaceAfter=1 * mm,
        alignment=TA_LEFT,
    )
    h6_style = ParagraphStyle(
        name="H6",
        fontName=font_bold if font_bold != font else font,
        fontSize=9,
        leading=12,
        textColor=th.color_body,
        spaceBefore=1 * mm,
        spaceAfter=1 * mm,
        alignment=TA_LEFT,
    )
    body_style = ParagraphStyle(
        name="Body",
        fontName=font,
        fontSize=12,
        leading=17,
        textColor=th.color_body,
        alignment=TA_LEFT,
        leftIndent=0,
        firstLineIndent=0,
        wordWrap="CJK",
        spaceAfter=3 * mm,
    )
    mermaid_caption_style = ParagraphStyle(
        name="MermaidCaption",
        fontName=font,
        fontSize=body_style.fontSize * 0.5,
        leading=body_style.leading * 0.5,
        textColor=th.color_muted,
        alignment=TA_CENTER,
        leftIndent=0,
        firstLineIndent=0,
        rightIndent=0,
        spaceBefore=0,
        spaceAfter=0,
        wordWrap="CJK",
    )
    olist_style = ParagraphStyle(
        name="OrderedList",
        parent=body_style,
        leftIndent=0,
        firstLineIndent=0,
        bulletIndent=0,
        wordWrap="CJK",
        alignment=TA_LEFT,
    )
    # Tight spaceAfter when the next material line is a ``` fence (not ``MDPDF_FENCED_CARD_ABOVE_MM``).
    _fence_gap = 0.5 * mm
    title_style_fence = ParagraphStyle(
        name="TitleFence", parent=title_style, spaceAfter=_fence_gap
    )
    h2_style_fence = ParagraphStyle(name="H2Fence", parent=h2_style, spaceAfter=_fence_gap)
    h3_style_fence = ParagraphStyle(name="H3Fence", parent=h3_style, spaceAfter=_fence_gap)
    h4_style_fence = ParagraphStyle(name="H4Fence", parent=h4_style, spaceAfter=_fence_gap)
    h5_style_fence = ParagraphStyle(name="H5Fence", parent=h5_style, spaceAfter=_fence_gap)
    h6_style_fence = ParagraphStyle(name="H6Fence", parent=h6_style, spaceAfter=_fence_gap)
    body_style_fence = ParagraphStyle(
        name="BodyFence", parent=body_style, spaceAfter=_fence_gap
    )
    olist_style_fence = ParagraphStyle(
        name="OrderedListFence", parent=olist_style, spaceAfter=_fence_gap
    )
    meta_style = ParagraphStyle(
        name="Meta",
        fontName=font,
        fontSize=10,
        leading=14,
        textColor=th.color_muted,
        alignment=TA_LEFT,
        spaceAfter=1 * mm,
    )
    quote_style = ParagraphStyle(
        name="Quote",
        parent=body_style,
        leftIndent=6 * mm,
        backColor=th.color_issuer_card_bg,
        borderPadding=6,
        spaceBefore=2 * mm,
        spaceAfter=2 * mm,
        alignment=TA_LEFT,
    )
    # Version history table: 20% smaller than body (9.6pt / 13.6 leading @ 12pt body)
    version_history_style = ParagraphStyle(
        name="VersionHistory",
        fontName=font,
        fontSize=body_style.fontSize * 0.8,
        leading=body_style.leading * 0.8,
        textColor=th.color_muted,
        alignment=TA_LEFT,
        spaceAfter=0.8 * mm,
    )

    avail_body_h_pt = A4[1] - _BODY_STACK_TOP_MM * mm - BODY_BOTTOM_MARGIN_MM * mm
    mermaid_lead_mm = _env_float_mm("MDPDF_MERMAID_LEAD_MM", 0.5, hi=5.0)
    fenced_style_idx = [0]

    def append_generic_fenced_block(raw_lang: str, body_lines: list[str]) -> None:
        if not any(s.strip() for s in body_lines):
            _above_emp = _env_float_mm("MDPDF_FENCED_CARD_ABOVE_MM", _DEFAULT_FENCED_CARD_ABOVE_MM) * mm
            story.append(Spacer(1, _above_emp + 1 * mm))
            story.append(
                Paragraph(esc("[Code] Empty fenced block."), meta_style),
            )
            story.append(Spacer(1, 2 * mm))
            return
        max_c = _env_int("MDPDF_FENCED_MAX_CHARS", _DEFAULT_FENCED_MAX_CHARS)
        max_l = _env_int("MDPDF_FENCED_MAX_LINES", _DEFAULT_FENCED_MAX_LINES)
        tlines, trunc = _fence_truncate(body_lines, max_l, max_c)
        # Pre-gap is inside ``FencedCodeCardTable`` row 0 (not a separate story ``Spacer``), so
        # ``MDPDF_FENCED_CARD_ABOVE_MM`` reliably changes visible space above the lang bar.
        _card_above_mm = _env_float_mm("MDPDF_FENCED_CARD_ABOVE_MM", _DEFAULT_FENCED_CARD_ABOVE_MM)
        if os.environ.get("MDPDF_DEBUG_FENCES", "").strip() == "1":
            print(
                f"[md-to-pdf][debug] MDPDF_FENCED_CARD_ABOVE_MM={os.environ.get('MDPDF_FENCED_CARD_ABOVE_MM')!r} -> card_above_mm={_card_above_mm}",
                file=sys.stderr,
            )
        fenced_style_idx[0] += 1
        ky = fenced_style_idx[0]
        label = normalize_fence_lang(raw_lang)
        if not label and raw_lang.strip():
            label = raw_lang.strip().split()[0].lower()
        if not label:
            label = "text"
        badge = re.sub(r"[^a-z0-9._+-]+", " ", label, flags=re.I).strip().upper() or "TEXT"
        if len(badge) > 32:
            badge = badge[:29] + "…"
        if trunc:
            badge += " · TRUNC"

        use_py = _env_fenced_pygments() and fenced_rl is not None
        use_line_nums = _env_truthy("MDPDF_FENCED_LINE_NUMBERS")

        # ReportLab: ``borderPadding`` 4-tuple is **(Top, Right, Bottom, Left)** (see ``normalizeTRBL`` / paragraph draw).
        code_hdr_style = ParagraphStyle(
            name=f"CodeHdr{ky}",
            fontName=font,
            fontSize=7.0,
            leading=9.0,
            textColor=_FENCED_GH_HDR_TXT,
            backColor=None,
            borderWidth=0,
            spaceBefore=0,
            # No spaceAfter here: inside ``FencedCodeCardTable`` it can stack oddly with row-2 padding;
            # seam is ``Table`` ``LINEBELOW`` + body ``borderTopWidth=0``.
            spaceAfter=0,
            alignment=TA_LEFT,
        )
        code_body_style = ParagraphStyle(
            name=f"FencedCode{ky}",
            fontName=code_font,
            fontSize=8.5,
            leading=12.0,
            textColor=_FENCED_GH_CODE_INK,
            alignment=TA_LEFT,
            leftIndent=0,
            rightIndent=0,
            backColor=None,
            borderWidth=0,
            spaceBefore=0,
            spaceAfter=0,
            wordWrap="CJK",
        )
        line_num_style = ParagraphStyle(
            name=f"CodeLineNum{ky}",
            fontName=code_font,
            fontSize=8.0,
            leading=12.0,
            textColor=th.color_muted,
            alignment=TA_RIGHT,
            rightIndent=1.5 * mm,
            backColor=_FENCED_GH_CODE_BG,
            borderWidth=0,
            borderPadding=(5, 3, 5, 4),
            spaceBefore=0,
            spaceAfter=0,
        )

        cjk_sans = font  # body Noto: CJK in code uses same family for mixed rendering

        def _body_xml_for_chunk(chunk: list[str]) -> str:
            if not use_py:
                return fenced_code_body_xml(chunk, cjk_body_font=cjk_sans)
            try:
                return fenced_rl.pygments_to_reportlab_paragraph_xml(  # type: ignore[union-attr]
                    "\n".join(chunk),
                    raw_lang,
                    cjk_body_font=cjk_sans,
                )
            except Exception:
                return fenced_code_body_xml(chunk, cjk_body_font=cjk_sans)

        n = len(tlines)
        step = _FENCED_CODE_LINES_PER_CHUNK
        for off in range(0, n, step):
            chunk = tlines[off : off + step]
            body_xml = _body_xml_for_chunk(chunk)
            accent = th.color_brand
            if fenced_rl is not None:
                try:
                    accent = colors.HexColor(fenced_rl.lang_accent_hex(label))  # type: ignore[union-attr]
                except Exception:
                    pass
            # Tight ``gap`` so monospaced text column stays close to the body left edge (the rule is 2pt).
            inner = LeftRuleCodeBlock(
                Paragraph(body_xml, code_body_style),
                rule_color=accent,
                gap_pt=0.0,
            )
            p_num: Paragraph | None = None
            num_w = 0.0
            if use_line_nums:
                start0 = off + 1
                nums = "<br/>".join(str(start0 + j) for j in range(len(chunk)))
                last_no = str(start0 + len(chunk) - 1)
                num_w = max(5.5 * mm, 2.0 * mm * max(1, len(last_no)) + 2.5 * mm)
                p_num = Paragraph(nums, line_num_style)

            if off == 0:
                hdr = Paragraph(esc(badge), code_hdr_style)
                def _make_r2(aW: float) -> Flowable:
                    if use_line_nums and p_num is not None:
                        w2 = max(1.0, float(aW) - float(num_w))
                        tln = Table(
                            [[p_num, inner]],
                            colWidths=[float(num_w), w2],
                        )
                        tln.hAlign = "LEFT"
                        tln.setStyle(
                            TableStyle(
                                [
                                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                    ("LINEAFTER", (0, 0), (0, 0), 0.5, th.color_table_grid),
                                ]
                            )
                        )
                        return tln
                    return inner

                card = FencedCodeCardTable(_card_above_mm, hdr, _make_r2, _FENCED_TABLE_BODY_TOP_PAD_PT)
                story.append(KeepTogether([card]))
            else:
                if use_line_nums and p_num is not None:
                    body_cont = Table(
                        [[p_num, inner]],
                        colWidths=[float(num_w), float(frame_w_pt - num_w)],
                    )
                    body_cont.hAlign = "LEFT"
                    body_cont.setStyle(
                        TableStyle(
                            [
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                ("LINEAFTER", (0, 0), (0, 0), 0.5, th.color_table_grid),
                            ]
                        )
                    )
                    story.append(body_cont)
                else:
                    story.append(inner)
        story.append(Spacer(1, 2 * mm))

    outline_key_i = 0
    outline_last_ol = -1

    def next_outline_key() -> str:
        nonlocal outline_key_i
        outline_key_i += 1
        return f"ids-h-{outline_key_i}"

    def effective_outline_level(md_lvl: int) -> int:
        """ReportLab allows at most +1 between adjacent outline levels; clamp MD skips to last+1."""
        nonlocal outline_last_ol
        want = md_lvl - 1
        if outline_last_ol < 0:
            ol = want
        elif want > outline_last_ol + 1:
            ol = outline_last_ol + 1
        else:
            ol = want
        outline_last_ol = ol
        return ol

    def append_heading_with_outline(
        md_lvl: int,
        raw_title: str,
        para_style: ParagraphStyle,
        *,
        lead_spacer_mm: float | None = None,
    ) -> None:
        if lead_spacer_mm is not None:
            story.append(Spacer(1, lead_spacer_mm * mm))
        plain = outline_plain_title(raw_title).strip() or raw_title.strip() or "(untitled)"
        ol = effective_outline_level(md_lvl)
        key = next_outline_key()
        story.append(OutlineBookmarkFlowable(plain, ol, key))
        story.append(Paragraph(md_inline_to_xml(raw_title), para_style))

    i = 0
    doc_title = ""
    while i < len(lines):
        stripped = lines[i].strip()

        if stripped == "## Version History":
            vh_h2_style = ParagraphStyle(
                name="VH2",
                parent=h2_style,
                spaceBefore=0,
                spaceAfter=1.5 * mm,
            )
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            _vh_plain = outline_plain_title("Version History") or "Version History"
            _vh_ol = effective_outline_level(2)
            _vh_key = next_outline_key()
            vh_flow: list = [
                Spacer(1, 0.5 * mm),
                OutlineBookmarkFlowable(_vh_plain, _vh_ol, _vh_key),
                Paragraph(md_inline_to_xml("Version History"), vh_h2_style),
            ]
            if i < len(lines) and lines[i].strip().startswith("|"):
                rows, next_i = consume_markdown_table(lines, i)
                i = next_i
                if len(rows) > 1:
                    for row in rows[1:]:
                        if not any(c.strip() for c in row):
                            continue
                        line = "- " + " · ".join(c.strip() for c in row)
                        vh_flow.append(Paragraph(md_inline_to_xml(line), version_history_style))
            vh_flow.append(Spacer(1, 2 * mm))
            story.append(KeepTogether(vh_flow))
            continue

        toc_h2 = stripped[3:].strip() if stripped.startswith("## ") else ""
        if toc_h2 == "目录" or toc_h2.lower() == "table of contents":
            toc_display_title = "Table of Contents" if toc_h2 == "目录" else toc_h2
            story.append(Spacer(1, 1 * mm))
            _toc_plain = outline_plain_title(toc_display_title) or toc_display_title
            _toc_ol = effective_outline_level(2)
            _toc_key = next_outline_key()
            story.append(OutlineBookmarkFlowable(_toc_plain, _toc_ol, _toc_key))
            story.append(Paragraph(md_inline_to_xml(toc_display_title), h2_style))
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            toc_style = ParagraphStyle(
                name="TocLine",
                fontName=font_bold if font_bold != font else font,
                fontSize=11,
                leading=15,
                textColor=th.color_body,
                spaceAfter=1.5 * mm,
                alignment=TA_LEFT,
                leftIndent=0,
                firstLineIndent=0,
                wordWrap="CJK",
            )
            if i < len(lines) and lines[i].strip().startswith("|"):
                rows, next_i = consume_markdown_table(lines, i)
                i = next_i
                for row in rows[1:]:
                    if not any(c.strip() for c in row):
                        continue
                    usable = [c.strip() for c in row]
                    line_xml = " · ".join(md_inline_to_xml(c) for c in usable)
                    dest = lookup_toc_row_bookmark_key(usable, bookmark_plain_to_key)
                    if dest:
                        # Internal PDF link to named destination (bookmarkPage); must match key string only
                        story.append(
                            Paragraph(
                                f'<link href="{dest}" color="blue">{line_xml}</link>',
                                toc_style,
                            )
                        )
                    else:
                        story.append(Paragraph(line_xml, toc_style))
            story.append(Spacer(1, 1 * mm))
            continue

        _hm = _RE_ATX_HEADING.match(stripped)
        if _hm:
            lvl = len(_hm.group(1))
            htxt = _hm.group(2).strip()
            _tight_h = _fenced_starts_soon_after(lines, i + 1)
            if lvl == 1 and not doc_title:
                doc_title = htxt
                append_heading_with_outline(
                    1, htxt, title_style_fence if _tight_h else title_style
                )
                if not _tight_h:
                    story.append(Spacer(1, 2 * mm))
                i += 1
                continue
            if lvl == 1:
                append_heading_with_outline(
                    1,
                    htxt,
                    h2_style_fence if _tight_h else h2_style,
                    lead_spacer_mm=1.0,
                )
                i += 1
                continue
            if lvl == 2:
                append_heading_with_outline(
                    2,
                    htxt,
                    h2_style_fence if _tight_h else h2_style,
                    lead_spacer_mm=1.0,
                )
                i += 1
                continue
            if lvl == 3:
                append_heading_with_outline(3, htxt, h3_style_fence if _tight_h else h3_style)
                i += 1
                continue
            if lvl == 4:
                append_heading_with_outline(4, htxt, h4_style_fence if _tight_h else h4_style)
                i += 1
                continue
            if lvl == 5:
                append_heading_with_outline(5, htxt, h5_style_fence if _tight_h else h5_style)
                i += 1
                continue
            if lvl == 6:
                append_heading_with_outline(6, htxt, h6_style_fence if _tight_h else h6_style)
                i += 1
                continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            rows, next_i = consume_markdown_table(lines, i)
            i = next_i
            if not rows:
                continue
            usable = min(len(r) for r in rows)
            rows = [r[:usable] for r in rows]
            ncols = len(rows[0])
            frame_w_pt = A4[0] - 2 * PAGE_H_MARGIN_MM * mm
            fs = 9 if ncols > 5 else 10
            ld = 12 if ncols > 5 else 13
            col_widths = compute_table_col_widths_pt(rows, frame_w_pt, font, fs)
            data = [
                [
                    table_cell_paragraph(c, font, font_bold, fs, ld, header=(ri == 0))
                    for c in row
                ]
                for ri, row in enumerate(rows)
            ]
            rr = 1 if len(rows) > 1 else 0
            pad = TABLE_CELL_PAD_PT
            tbl_cmds: list = [
                ("BACKGROUND", (0, 0), (-1, 0), th.color_table_header_bg),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, th.color_table_grid),
                ("LEFTPADDING", (0, 0), (-1, -1), pad),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad),
                ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
            ]
            for ri, row in enumerate(rows):
                for cj, cell in enumerate(row):
                    tbl_cmds.append(
                        ("ALIGN", (cj, ri), (cj, ri), _table_cell_table_align(cell, ri == 0))
                    )
            t = Table(data, colWidths=col_widths, repeatRows=rr)
            t.setStyle(TableStyle(tbl_cmds))
            story.append(t)
            story.append(Spacer(1, 2 * mm))
            continue

        if stripped.startswith("> "):
            story.append(Paragraph(md_inline_to_xml(stripped[2:]), quote_style))
            i += 1
            continue

        if stripped.startswith("- **") or (stripped.startswith("- ") and not stripped.startswith("---")):
            _tight_b = _fenced_starts_soon_after(lines, i + 1)
            story.append(
                Paragraph(
                    "• " + md_inline_to_xml(stripped[2:].strip()),
                    body_style_fence if _tight_b else body_style,
                )
            )
            i += 1
            continue

        if stripped == "---":
            story.append(Spacer(1, 2 * mm))
            i += 1
            continue

        if stripped.startswith("**致**") or stripped.startswith("**日期**"):
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            lang_raw, body_lines, next_i = consume_fenced_code_block(lines, i)
            lang_norm = normalize_fence_lang(lang_raw)
            is_mermaid = lang_norm in ("mermaid", "mmd")
            body_nonempty = any(line.strip() for line in body_lines)

            if is_mermaid and not body_nonempty:
                story.append(Spacer(1, 2 * mm))
                story.append(
                    Paragraph(
                        esc("[Mermaid] Empty diagram block; nothing to render."),
                        meta_style,
                    )
                )
                story.append(Spacer(1, 3 * mm))
            elif is_mermaid and body_nonempty and mermaid_workdir is None:
                append_generic_fenced_block(lang_raw, body_lines)
            elif is_mermaid and body_nonempty and mermaid_workdir is not None:
                src = "\n".join(body_lines)
                lead_sp = Spacer(1, mermaid_lead_mm * mm)
                png, m_err = render_mermaid_to_png(src, mermaid_workdir, preset=mermaid_preset)
                if png is not None:
                    try:
                        _, img_h = mermaid_png_scaled_dimensions(png, frame_w_pt)
                        cap_txt = resolve_mermaid_caption_text(lines, i, src)
                        cap_h = (
                            (mermaid_caption_style.leading + 1 * mm) if cap_txt else 0.0
                        )
                        total_h = float(mermaid_lead_mm * mm + img_h + cap_h)
                        img_flow = mermaid_png_to_flowable(png, frame_w_pt)
                        if total_h < MERMAID_KEEP_TOGETHER_FRAC * avail_body_h_pt:
                            kt_parts: list = [lead_sp, img_flow]
                            if cap_txt:
                                kt_parts.append(Paragraph(md_inline_to_xml(cap_txt), mermaid_caption_style))
                            story.append(KeepTogether(kt_parts))
                        else:
                            story.append(lead_sp)
                            story.append(img_flow)
                            if cap_txt:
                                story.append(
                                    Paragraph(md_inline_to_xml(cap_txt), mermaid_caption_style)
                                )
                    except OSError:
                        story.append(lead_sp)
                        story.append(
                            Paragraph(
                                esc("[Mermaid] Could not embed PNG in the PDF."),
                                meta_style,
                            )
                        )
                elif m_err.startswith("too_large:"):
                    detail = m_err.split(":", 1)[-1].strip()
                    story.append(lead_sp)
                    story.append(
                        Paragraph(esc("[Mermaid] " + detail), meta_style),
                    )
                elif m_err.startswith("cli_failed:"):
                    detail = m_err.split(":", 1)[-1].strip()
                    if len(detail) > 420:
                        detail = detail[:417] + "..."
                    story.append(lead_sp)
                    story.append(
                        Paragraph(
                            esc(
                                "[Mermaid] mmdc was found but failed (often Chromium/Puppeteer not ready). Summary: "
                                + detail
                                + " On macOS the tool tries several browsers in order (Puppeteer cache, Edge, Chromium, …). "
                                "If all fail, add --no-mermaid to keep the mermaid source as a fenced code block, "
                                "or install a browser bundle (npx puppeteer browsers install chrome) and set "
                                "PUPPETEER_EXECUTABLE_PATH. Set MDPDF_MERMAID_VERBOSE=1 to log each attempt."
                            ),
                            meta_style,
                        )
                    )
                elif m_err == "no_png":
                    story.append(lead_sp)
                    story.append(
                        Paragraph(
                            esc(
                                "[Mermaid] mmdc ran but did not produce a valid PNG "
                                "(check output path and permissions)."
                            ),
                            meta_style,
                        )
                    )
                else:
                    npx_hint = (
                        " Install with npm i -g @mermaid-js/mermaid-cli, or run which mmdc in a terminal; "
                        "if mmdc is not global, export MDPDF_MERMAID_NPX=1 to use npx (requires network)."
                    )
                    story.append(lead_sp)
                    story.append(
                        Paragraph(
                            esc(
                                "[Mermaid] mmdc not found: still unresolved after merging "
                                "nvm/Volta/Homebrew/global npm paths."
                            )
                            + esc(npx_hint),
                            meta_style,
                        )
                    )
                story.append(Spacer(1, 3 * mm))
            elif not is_mermaid:
                append_generic_fenced_block(lang_raw, body_lines)
            i = next_i
            continue

        if re.match(r"^\d+\.\s", stripped):
            parts: list[str] = [stripped]
            i += 1
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    break
                if s.startswith(("#", "|", ">", "-", "---", "```")):
                    break
                if re.match(r"^\d+\.\s", s):
                    break
                parts.append(s)
                i += 1
            _tight_o = _fenced_starts_soon_after(lines, i)
            story.append(
                Paragraph(
                    md_inline_to_xml(" ".join(parts)),
                    olist_style_fence if _tight_o else olist_style,
                )
            )
            continue

        buf: list[str] = []
        while i < len(lines) and lines[i].strip():
            s = lines[i].strip()
            if s.startswith(("#", "|", ">", "-", "---", "```")):
                break
            if re.match(r"^\d+\.\s", s):
                break
            buf.append(s)
            i += 1
        if buf:
            _tight_p = _fenced_starts_soon_after(lines, i)
            story.append(
                Paragraph(
                    md_inline_to_xml(" ".join(buf)),
                    body_style_fence if _tight_p else body_style,
                )
            )
        else:
            i += 1

    return story


def build_issuer_outer_table(font: str, font_bold: str, qr_path: Path | None, pack: BrandPack):
    """
    Single Flowable: boxed issuer row (width = tw = frame * ISSUER_BOX_WIDTH_FRAC).
    Icon | text | gap | QR — extra column avoids QR touching right border.
    """
    th = pack.theme
    lines_src = pack.compliance.issuer_lines
    fw = A4[0] - 2 * PAGE_H_MARGIN_MM * mm
    tw = fw * ISSUER_BOX_WIDTH_FRAC
    gap_icon = 6
    gap_txt_qr = 10
    pad_box = 12
    w_icon = ICON_SZ_PT
    w_qr = QR_SZ_PT
    # Column width must cover L/R cell padding + image width or RLImage overflows the rule
    w_qr_col = ISSUER_QR_LEFT_PAD_PT + w_qr + ISSUER_QR_RIGHT_PAD_PT
    w_mid = tw - w_icon - gap_icon - gap_txt_qr - w_qr_col

    title_style = ParagraphStyle(
        name="IssTitle",
        fontName=font_bold if font_bold != font else font,
        fontSize=th.issuer_title_pt,
        leading=th.issuer_title_pt + 3,
        textColor=th.color_issuer_title,
        alignment=TA_LEFT,
        spaceAfter=2,
    )
    body_style_i = ParagraphStyle(
        name="IssBody",
        fontName=font,
        fontSize=th.issuer_body_pt,
        leading=th.issuer_body_pt + 2.5,
        textColor=th.color_issuer_body,
        alignment=TA_LEFT,
        spaceAfter=2,
    )
    body_last = ParagraphStyle(
        name="IssBodyLast",
        parent=body_style_i,
        spaceAfter=0,
    )

    inner_rows: list = []
    nlines = len(lines_src)
    for idx, (is_title, text) in enumerate(lines_src):
        st = title_style if is_title else (body_style_i if idx < nlines - 1 else body_last)
        inner_rows.append([Paragraph(md_inline_to_xml(text), st)])
    inner = Table(inner_rows, colWidths=[w_mid])
    inner.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    # Inner table must wrap first or outer Table.wrap height is too small (overlay / LayoutError)
    inner.wrap(w_mid, 10**6)

    if pack.icon_path.is_file():
        icon_cell = RLImage(str(pack.icon_path), width=w_icon, height=w_icon)
    else:
        icon_cell = Spacer(w_icon, w_icon)
    if qr_path is not None and qr_path.is_file():
        qr_cell = RLImage(str(qr_path), width=w_qr, height=w_qr)
    else:
        qr_cell = Spacer(w_qr, w_qr)

    gap_cell = ""  # colWidths already include gap_txt_qr; empty cell avoids Spacer fighting right border
    row = Table(
        [[icon_cell, inner, gap_cell, qr_cell]],
        colWidths=[w_icon + gap_icon, w_mid, gap_txt_qr, w_qr_col],
    )
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), pad_box),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad_box),
                ("TOPPADDING", (0, 0), (-1, -1), pad_box),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad_box),
                ("RIGHTPADDING", (2, 0), (2, 0), 0),
                ("LEFTPADDING", (3, 0), (3, 0), ISSUER_QR_LEFT_PAD_PT),
                ("RIGHTPADDING", (3, 0), (3, 0), ISSUER_QR_RIGHT_PAD_PT),
                ("BACKGROUND", (0, 0), (-1, -1), th.color_issuer_card_bg),
                ("BOX", (0, 0), (-1, -1), 0.75, th.color_issuer_card_border),
            ]
        )
    )
    return row


def write_issuer_fragment_pdf(path: Path, font: str, font_bold: str, qr_path: Path | None) -> None:
    """
    Single-page PDF: width tw, height = measured Table.wrap. Avoid SimpleDocTemplate — small page height
    collapses its frame (~56pt) and triggers LayoutError on page 2; Canvas drawOn matches media box to card.
    """
    row = build_issuer_outer_table(font, font_bold, qr_path, get_brand_pack())
    fw = A4[0] - 2 * PAGE_H_MARGIN_MM * mm
    tw = fw * ISSUER_BOX_WIDTH_FRAC
    _w, frag_h = row.wrap(tw, 10**6)
    frag_h = float(frag_h) if frag_h and frag_h > 0.5 else ISSUER_FRAGMENT_HEIGHT_FALLBACK_PT
    c = rl_canvas.Canvas(str(path), pagesize=(tw, frag_h))
    row.drawOn(c, 0, 0)
    c.showPage()
    c.save()


def draw_footer_stamp_canvas(
    c: rl_canvas.Canvas,
    page_num: int,
    page_count: int,
    pack: BrandPack,
) -> None:
    """Footer text only (full A4 canvas); merged last so it sits above issuer on the last page."""
    th = pack.theme
    H = float(A4[1])
    W = float(A4[0])
    pad = PAGE_H_MARGIN_MM * mm
    y_row1_top, y_row1_bot = footer_strip_y_bounds(H)
    y_top_pm = y_row1_top - FOOTER_DRAW_RECT_TOP_PAD_PT
    y_bot_pm = y_row1_bot + 4
    y_low_rl = H - y_bot_pm
    y_high_rl = H - y_top_pm
    y_mid = (y_low_rl + y_high_rl) / 2.0
    y_conf = y_mid - th.footer_confidential_pt * 0.15
    y_pn = y_mid - th.footer_page_num_pt * 0.15
    c.saveState()
    c.setFillColor(th.color_muted)
    c.setFont(th.font_footer, th.footer_confidential_pt)
    c.drawString(pad, y_conf, pack.compliance.footer_confidential)
    c.setFont(th.font_footer, th.footer_page_num_pt)
    c.drawRightString(W - pad, y_pn, f"Page {page_num} / {page_count}")
    c.restoreState()


def write_footer_stamp_pdf(path: Path, page_num: int, page_count: int, pack: BrandPack) -> None:
    c = rl_canvas.Canvas(str(path), pagesize=A4)
    draw_footer_stamp_canvas(c, page_num, page_count, pack)
    c.showPage()
    c.save()


def add_footer_overlay_pypdf(pdf_path: Path, pack: BrandPack) -> None:
    """Stamp confidential + page numbers on every page (after issuer merge on last page)."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    writer = PdfWriter()
    out_tmp = pdf_path.with_suffix(".tmp_footer_pypdf.pdf")
    try:
        for i in range(n):
            fd, frag_name = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            frag = Path(frag_name)
            try:
                write_footer_stamp_pdf(frag, i + 1, n, pack)
                fr = PdfReader(str(frag))
                page = reader.pages[i]
                page.merge_translated_page(fr.pages[0], 0, 0, over=True, expand=False)
                writer.add_page(page)
            finally:
                frag.unlink(missing_ok=True)
        with open(out_tmp, "wb") as f:
            writer.write(f)
        shutil.move(str(out_tmp), str(pdf_path))
    except Exception:
        if out_tmp.exists():
            out_tmp.unlink(missing_ok=True)
        raise


def add_watermark_pypdf(pdf_path: Path, text: str) -> None:
    """
    Tiled diagonal light-gray text covering the full page (after footer stamp), like a
    “斜纹” fill: same string repeated; row spacing ``WATERMARK_ROW_SPACING_PT``; merged
    with over=False so the watermark sits *under* body/footer (not on top of text). Long
    text is truncated for each tile.
    """
    from pypdf import PdfReader, PdfWriter

    th = get_brand_pack().theme
    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    if n == 0:
        return
    writer = PdfWriter()
    out_tmp = pdf_path.with_suffix(".tmp_wmark_pypdf.pdf")
    tshow = (text if len(text) <= 120 else text[:117] + "…").strip() or " "
    try:
        for i in range(n):
            page = reader.pages[i]
            page_w = float(page.mediabox.width)
            page_h = float(page.mediabox.height)
            fd, name = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            frag = Path(name)
            try:
                c = rl_canvas.Canvas(str(frag), pagesize=(page_w, page_h))
                c.saveState()
                c.setFillColorRGB(
                    WATERMARK_FILL_RGB[0], WATERMARK_FILL_RGB[1], WATERMARK_FILL_RGB[2]
                )
                font = FONT_NOTO_R
                fs = WATERMARK_FONT_SIZE_PT
                try:
                    c.setFont(font, fs)
                except Exception:  # noqa: BLE001
                    try:
                        font = th.font_footer
                        c.setFont(font, fs)
                    except Exception:  # noqa: BLE001
                        font = "Helvetica"
                        c.setFont(font, fs)
                tw = c.stringWidth(tshow, font, fs)
                h_step = max(tw + WATERMARK_COL_GAP_PT, 12.0)
                v_step = WATERMARK_ROW_SPACING_PT
                R = max(page_w, page_h) * WATERMARK_PAGE_EXTENT_MULT
                c.translate(page_w * 0.5, page_h * 0.5)
                c.rotate(WATERMARK_TILE_ANGLE_DEG)
                y = -R
                while y <= R:
                    x = -R
                    while x <= R + tw:
                        c.drawString(x, y, tshow)
                        x += h_step
                    y += v_step
                c.restoreState()
                c.showPage()
                c.save()
                wr = PdfReader(str(frag))
                # over=False: page2 (watermark) is drawn *under* existing page content
                page.merge_translated_page(wr.pages[0], 0, 0, over=False, expand=False)
                writer.add_page(page)
            finally:
                frag.unlink(missing_ok=True)
        with open(out_tmp, "wb") as f:
            writer.write(f)
        shutil.move(str(out_tmp), str(pdf_path))
    except Exception:
        if out_tmp.exists():
            out_tmp.unlink(missing_ok=True)
        raise


def resolve_watermark_text() -> str | None:
    """
    Company / brand: **only** from active brand pack ``compliance.md`` (``## brand profiles`` / Issuer).
    User: ``MD_PDF_WATERMARK_USER``, else getpass / ``USER`` / ``USERNAME`` — **required**; if
    no user, watermark is skipped (``None``).

    * Company present, user present → ``company//user`` (literal ``//`` separator)
    * Company empty, user present → ``user`` only (no env ``MD_PDF_COMPANY``)
    * User empty → ``None`` (``--watermark`` produces no overlay)
    """
    company = (watermark_company_name(get_brand_pack()) or "").strip()
    u = os.environ.get("MD_PDF_WATERMARK_USER", "").strip()
    if not u:
        try:
            u = getpass.getuser()
        except Exception:  # noqa: BLE001
            u = ""
    if not (u or "").strip():
        u = os.environ.get("USER", "").strip() or os.environ.get("USERNAME", "").strip()
    u = (u or "").strip()
    if not u:
        return None
    if company:
        return f"{company}//{u}"
    return u


def overlay_issuer_on_last_page(main_pdf: Path, issuer_pdf: Path) -> None:
    """
    Align issuer block bottom: footer draw top minus GAP_ISSUER_ABOVE_FOOTER_DRAW_TOP_PT.
    Uses pypdf merge (PDF user space: origin bottom-left).
    """
    from pypdf import PdfReader, PdfWriter

    reader_m = PdfReader(str(main_pdf))
    reader_i = PdfReader(str(issuer_pdf))
    if not reader_m.pages or not reader_i.pages:
        return
    iss = reader_i.pages[0]
    iw = float(iss.mediabox.width)
    ih = float(iss.mediabox.height)

    writer = PdfWriter()
    n = len(reader_m.pages)
    for idx in range(n - 1):
        writer.add_page(reader_m.pages[idx])
    last = reader_m.pages[n - 1]
    w = float(last.mediabox.width)
    h = float(last.mediabox.height)
    x0 = (w - iw) / 2.0
    y1_pm = issuer_bottom_y_for_page(h)
    tx = x0
    ty = h - y1_pm
    last.merge_translated_page(iss, tx, ty, over=True, expand=False)
    writer.add_page(last)
    out_tmp = main_pdf.with_suffix(".tmp_iss_pypdf.pdf")
    try:
        with open(out_tmp, "wb") as f:
            writer.write(f)
        shutil.move(str(out_tmp), str(main_pdf))
    except Exception:
        if out_tmp.exists():
            out_tmp.unlink(missing_ok=True)
        raise


def make_on_page(ts_iso: str, pack: BrandPack):
    """Draw branded header only (logo + rule + Generated). Footer is a later pypdf stamp."""

    th = pack.theme

    def on_page(canvas, doc):
        w, h = A4
        mx = PAGE_H_MARGIN_MM * mm
        rule_y = h - 26 * mm

        canvas.saveState()
        canvas.setStrokeColor(th.color_brand)
        canvas.setLineWidth(3)
        canvas.line(mx, rule_y, w - mx, rule_y)

        logo_h = float(th.logo_header_height_pt)
        logo_bottom_y = h - 12 * mm - logo_h
        gen_font = float(th.header_generated_pt)
        gen_y = logo_bottom_y + logo_h / 2 - 0.35 * gen_font

        if pack.logo_path.is_file():
            canvas.drawImage(
                ImageReader(str(pack.logo_path)),
                mx,
                logo_bottom_y,
                width=logo_h * float(th.logo_header_width_scale),
                height=logo_h,
                preserveAspectRatio=True,
                mask="auto",
            )

        canvas.setFillColor(th.color_body)
        canvas.setFont(th.font_header_generated, gen_font)
        canvas.drawRightString(w - mx, gen_y, f"Generated: {ts_iso}")
        canvas.restoreState()

    return on_page


def _whatsapp_qr_png_temp(url: str, px: int = 200) -> Path | None:
    """Render invite URL as square PNG; caller must unlink. None if qrcode/PIL missing."""
    try:
        import qrcode
        from PIL import Image
    except ImportError:
        return None
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=3,
        border=0,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS
    img = img.resize((px, px), resample)
    fd, name = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    p = Path(name)
    img.save(p, format="PNG")
    return p


def main() -> None:
    global _mmdc_version_logged
    _mmdc_version_logged = False
    ap = argparse.ArgumentParser(description="Markdown → PDF (md-to-pdf skill).")
    ap.add_argument("markdown", type=Path, help="Input .md path")
    ap.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Output .pdf path. Relative paths are resolved from the current working directory. "
            f"Default: {DEFAULT_FIXTURES_OUT_DIR.name}/ under this skill's fixtures/ "
            "(i.e. …/md-to-pdf/fixtures/out/<INPUT stem>.pdf)."
        ),
    )
    ap.add_argument(
        "--no-filter",
        action="store_true",
        help="Include metadata and Contributor Roles (default: strip for PDF)",
    )
    ap.add_argument(
        "--no-page-numbers",
        action="store_true",
        help="Skip pypdf footer stamp (confidential + page numbers; issuer merge unchanged)",
    )
    ap.add_argument(
        "--watermark",
        action="store_true",
        help=(
            "Background diagonal gray watermark on all pages (after footer), under text. "
            "Company from compliance.md only; user required (user-only if no company). "
            "Skipped if no user. MD_PDF_COMPANY is not used for watermark text."
        ),
    )
    ap.add_argument(
        "--brand-pack",
        type=Path,
        default=None,
        help="Brand directory (theme.yaml + compliance.md + logo/icon). Overrides MDPDF_BRAND_PACK; default: skill brand_kits/",
    )
    ap.add_argument(
        "--no-company-footer",
        action="store_true",
        help="Omit ReportLab issuer box (icon + HK lines + QR); footer overlay unchanged unless --no-page-numbers",
    )
    ap.add_argument(
        "--no-mermaid",
        action="store_true",
        help="Do not run mmdc/Puppeteer; mermaid blocks render as fenced code (source preserved), not PNG",
    )
    mermaid_presets = ap.add_mutually_exclusive_group()
    mermaid_presets.add_argument(
        "--mermaid-E",
        action="store_true",
        help="Mermaid export viewport 800×600; overrides MDPDF_MERMAID_PRESET",
    )
    mermaid_presets.add_argument(
        "--mermaid-S",
        action="store_true",
        help="Mermaid export viewport 1024×768 (default when no preset flag); overrides MDPDF_MERMAID_PRESET",
    )
    mermaid_presets.add_argument(
        "--mermaid-H",
        action="store_true",
        help="Mermaid export viewport 1920×1080; overrides MDPDF_MERMAID_PRESET",
    )
    args = ap.parse_args()
    md_path = args.markdown.expanduser().resolve()
    if not md_path.is_file():
        print("Missing:", md_path, file=sys.stderr)
        sys.exit(1)
    out_pdf = resolve_output_pdf(md_path, args.output)

    env_pack = os.environ.get("MDPDF_BRAND_PACK", "").strip()
    if args.brand_pack is not None:
        pack_dir = args.brand_pack.expanduser().resolve()
    elif env_pack:
        pack_dir = Path(env_pack).expanduser().resolve()
    else:
        pack_dir = DEFAULT_BRAND_PACK_DIR.resolve()
    set_brand_pack(load_brand_pack(pack_dir))
    pack = get_brand_pack()

    # utf-8-sig strips a leading UTF-8 BOM so the first line is not "\ufeff# Title"
    raw_lines = md_path.read_text(encoding="utf-8-sig").splitlines()
    raw_lines = strip_yaml_frontmatter(raw_lines)
    raw_lines = normalize_merged_atx_headings(raw_lines)
    if args.no_filter:
        lines = raw_lines
    else:
        lines = filter_md_for_branded_pdf(raw_lines)
        lines = move_toc_after_title(lines)

    font, font_bold = register_fonts()
    code_font = register_mono_font()
    ts_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    on_page = make_on_page(ts_iso, pack)
    qr_tmp: Path | None = None
    issuer_frag: Path | None = None
    if not args.no_company_footer:
        qr_tmp = _whatsapp_qr_png_temp(pack.compliance.whatsapp_url)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    skip_mermaid = args.no_mermaid or os.environ.get("MDPDF_SKIP_MERMAID", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    mermaid_workdir: Path | None = None if skip_mermaid else Path(tempfile.mkdtemp(prefix="mdpdf_mermaid_"))
    mermaid_cli: str | None = (
        "E" if args.mermaid_E  # --mermaid-E
        else "S" if args.mermaid_S
        else "H" if args.mermaid_H
        else None
    )
    mermaid_preset_eff = resolve_mermaid_preset(mermaid_cli)
    try:
        bottom_margin_pt = BODY_BOTTOM_MARGIN_MM * mm
        if not args.no_company_footer:
            issuer_h = measure_issuer_fragment_height_pt(font, font_bold, qr_tmp)
            bottom_margin_pt = required_bottom_margin_for_issuer_pt(issuer_h)
        doc = SimpleDocTemplate(
            str(tmp_path),
            pagesize=A4,
            leftMargin=PAGE_H_MARGIN_MM * mm,
            rightMargin=PAGE_H_MARGIN_MM * mm,
            topMargin=34 * mm,
            bottomMargin=bottom_margin_pt,
            title=md_path.stem,
            author="IDIMSUM",
        )
        story = build_story(
            lines,
            font,
            font_bold,
            mermaid_workdir=mermaid_workdir,
            mermaid_preset=mermaid_preset_eff,
            code_font=code_font,
        )
        doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
        shutil.move(str(tmp_path), str(out_pdf))
    finally:
        if mermaid_workdir is not None:
            shutil.rmtree(mermaid_workdir, ignore_errors=True)
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    if not args.no_company_footer:
        try:
            fd, frag_name = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            issuer_frag = Path(frag_name)
            write_issuer_fragment_pdf(issuer_frag, font, font_bold, qr_tmp)
            overlay_issuer_on_last_page(out_pdf, issuer_frag)
        finally:
            if issuer_frag is not None:
                try:
                    issuer_frag.unlink(missing_ok=True)
                except OSError:
                    pass
            if qr_tmp is not None:
                try:
                    qr_tmp.unlink(missing_ok=True)
                except OSError:
                    pass

    if not args.no_page_numbers:
        add_footer_overlay_pypdf(out_pdf, pack)

    if args.watermark:
        wtxt = resolve_watermark_text()
        if wtxt:
            add_watermark_pypdf(out_pdf, wtxt)

    print(f"Wrote: {wrote_path_display(out_pdf)}")


if __name__ == "__main__":
    main()
