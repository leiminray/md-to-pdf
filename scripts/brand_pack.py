"""
Load a brand kit directory — theme.yaml + compliance.md + asset paths (`--brand-pack` / `MDPDF_BRAND_PACK`; default: skill `brand_kits/`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from reportlab.lib import colors


@dataclass(frozen=True)
class BrandCompliance:
    footer_confidential: str
    issuer_lines: list[tuple[bool, str]]
    whatsapp_url: str
    # Optional: first list item under ## brand profiles (watermark / display name SSOT)
    brand_profiles_company: str | None


@dataclass(frozen=True)
class BrandTheme:
    color_brand: colors.Color
    color_body: colors.Color
    color_muted: colors.Color
    color_table_header_bg: colors.Color
    color_table_grid: colors.Color
    color_table_fin_negative: colors.Color
    color_issuer_title: colors.Color
    color_issuer_body: colors.Color
    color_issuer_card_bg: colors.Color
    color_issuer_card_border: colors.Color
    footer_confidential_pt: float
    footer_page_num_pt: float
    header_generated_pt: float
    issuer_title_pt: float
    issuer_body_pt: float
    font_footer: str
    font_header_generated: str
    logo_filename: str
    icon_filename: str
    logo_header_height_pt: float
    logo_header_width_scale: float


@dataclass(frozen=True)
class BrandPack:
    root: Path
    theme: BrandTheme
    compliance: BrandCompliance
    logo_path: Path
    icon_path: Path


def _hex_color(s: str) -> colors.Color:
    return colors.HexColor(s.strip())


def load_theme_yaml(path: Path) -> BrandTheme:
    if not path.is_file():
        raise SystemExit(f"Brand pack missing theme.yaml: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"Invalid theme.yaml (expected mapping): {path}")

    c = raw.get("colors") or {}
    t = raw.get("typography") or {}
    f = raw.get("fonts") or {}
    a = raw.get("assets") or {}
    lo = raw.get("layout") or {}

    try:
        return BrandTheme(
            color_brand=_hex_color(c["brand"]),
            color_body=_hex_color(c["body"]),
            color_muted=_hex_color(c["muted"]),
            color_table_header_bg=_hex_color(c["table_header_bg"]),
            color_table_grid=_hex_color(c["table_grid"]),
            color_table_fin_negative=_hex_color(c["table_fin_negative"]),
            color_issuer_title=_hex_color(c["issuer_title"]),
            color_issuer_body=_hex_color(c["issuer_body"]),
            color_issuer_card_bg=_hex_color(c["issuer_card_bg"]),
            color_issuer_card_border=_hex_color(c["issuer_card_border"]),
            footer_confidential_pt=float(t["footer_confidential_pt"]),
            footer_page_num_pt=float(t["footer_page_num_pt"]),
            header_generated_pt=float(t["header_generated_pt"]),
            issuer_title_pt=float(t["issuer_title_pt"]),
            issuer_body_pt=float(t["issuer_body_pt"]),
            font_footer=str(f["footer_face"]),
            font_header_generated=str(f["header_generated_face"]),
            logo_filename=str(a["logo"]),
            icon_filename=str(a["icon"]),
            logo_header_height_pt=float(lo["logo_header_height_pt"]),
            logo_header_width_scale=float(lo["logo_header_width_scale"]),
        )
    except KeyError as e:
        raise SystemExit(f"theme.yaml missing key {e!s} in {path}") from e


def parse_compliance_md(text: str) -> BrandCompliance:
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current, buf
        if current is not None:
            sections[current] = "\n".join(buf).strip()
        current = None
        buf = []

    for line in text.splitlines():
        m = re.match(r"^##\s+(.+)\s*$", line)
        if m:
            flush()
            current = m.group(1).strip().lower()
            continue
        if current is not None:
            buf.append(line)
    flush()

    def need(name: str) -> str:
        key = name.lower()
        for k, v in sections.items():
            if k.lower() == key:
                return v
        raise SystemExit(f"compliance.md missing '## {name}' section")

    def optional_section(*aliases: str) -> str | None:
        for want in aliases:
            w = want.lower()
            for k, v in sections.items():
                if k.lower() == w:
                    return v
        return None

    footer = need("Footer confidential").strip()
    whats_block = need("WhatsApp invite").strip()
    whats_lines = [ln.strip() for ln in whats_block.splitlines() if ln.strip()]
    if not whats_lines:
        raise SystemExit("compliance.md: WhatsApp invite section empty")
    whats_url = whats_lines[0]

    iss_raw = need("Issuer lines")
    issuer_lines: list[tuple[bool, str]] = []
    for ln in iss_raw.splitlines():
        s = ln.strip()
        m = re.match(r"^[-*]\s+\*\*(.+)\*\*\s*$", s)
        if m:
            issuer_lines.append((True, m.group(1).strip()))
            continue
        m2 = re.match(r"^[-*]\s+(.+)$", s)
        if m2:
            issuer_lines.append((False, m2.group(1).strip()))
    if not issuer_lines:
        raise SystemExit("compliance.md: Issuer lines: no bullet items")

    def first_bullet_company(block: str) -> str | None:
        for ln in block.splitlines():
            s = ln.strip()
            m = re.match(r"^[-*]\s*(.+)$", s)
            if m:
                raw = m.group(1).strip()
                m_b = re.match(r"^\*\*(.+)\*\*\s*$", raw)
                t = m_b.group(1).strip() if m_b else raw
                if t:
                    return t
        return None

    brand_profiles_company: str | None = None
    bp = optional_section("brand profiles", "brand profile", "watermark company")
    if bp:
        brand_profiles_company = first_bullet_company(bp)

    return BrandCompliance(
        footer_confidential=footer,
        issuer_lines=issuer_lines,
        whatsapp_url=whats_url,
        brand_profiles_company=brand_profiles_company,
    )


def load_brand_pack(pack_dir: Path) -> BrandPack:
    root = pack_dir.resolve()
    if not root.is_dir():
        raise SystemExit(f"Brand pack is not a directory: {root}")
    comp_path = root / "compliance.md"
    if not comp_path.is_file():
        raise SystemExit(f"Brand pack missing compliance.md: {comp_path}")
    compliance = parse_compliance_md(comp_path.read_text(encoding="utf-8"))
    theme = load_theme_yaml(root / "theme.yaml")
    logo = root / theme.logo_filename
    icon = root / theme.icon_filename
    if not logo.is_file():
        raise SystemExit(f"Brand pack missing logo {theme.logo_filename!r} under {root}")
    if not icon.is_file():
        raise SystemExit(f"Brand pack missing icon {theme.icon_filename!r} under {root}")
    return BrandPack(
        root=root,
        theme=theme,
        compliance=compliance,
        logo_path=logo,
        icon_path=icon,
    )


def watermark_company_name(pack: BrandPack) -> str | None:
    """
    Company string for --watermark (SSOT order):
    1) First list item under optional ## brand profiles (or ``## watermark company``)
    2) Else first **bold** line under ## Issuer lines (issuer card)
    3) Else first non-empty Issuer bullet
    """
    c = pack.compliance
    if c.brand_profiles_company and (t := c.brand_profiles_company.strip()):
        return t
    for is_bold, text in c.issuer_lines:
        if is_bold and (t := (text or "").strip()):
            return t
    for _is_bold, text in c.issuer_lines:
        if (t := (text or "").strip()):
            return t
    return None
