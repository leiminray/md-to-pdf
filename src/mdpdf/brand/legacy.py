"""v1 brand_kits/ layout adapter (--legacy-brand).

Reads the legacy v1.8.9 layout (theme.yaml + compliance.md + flat assets)
and returns a synthesised v2 BrandPack. Emits a deprecation message that
the caller surfaces to stderr.

The legacy layout is documented by the existing repo's `brand_kits/`:
- theme.yaml — colours/typography/assets in a different schema than v2
- compliance.md — `## brand profiles`, `## Footer confidential`,
  `## Issuer lines` sections parsed regex-style by v1.8.9's brand_pack.py

This adapter is removed in v3.0 (per Plan 1 §8.4); v2.1 adds a deprecation
warning when used.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from mdpdf.brand.schema import BrandPack
from mdpdf.errors import BrandError


def load_legacy_brand_pack(pack_root: Path) -> tuple[BrandPack, str]:
    """Return (BrandPack, deprecation_message)."""
    pack_root = Path(pack_root).resolve()
    theme_yaml_path = pack_root / "theme.yaml"
    compliance_md_path = pack_root / "compliance.md"
    if not theme_yaml_path.exists():
        raise BrandError(
            code="BRAND_NOT_FOUND",
            user_message=f"v1 layout requires theme.yaml at {pack_root}",
        )
    v1_theme: dict[str, Any] = yaml.safe_load(theme_yaml_path.read_text(encoding="utf-8")) or {}
    v1_compliance = (
        compliance_md_path.read_text(encoding="utf-8") if compliance_md_path.exists() else ""
    )

    issuer_name = _parse_md_section_first_bullet(v1_compliance, "brand profiles")
    issuer_lines = _parse_md_section_bullets(v1_compliance, "Issuer lines")
    footer_text = _parse_md_section_paragraph(v1_compliance, "Footer confidential")

    payload: dict[str, Any] = {
        "schema_version": "2.0",
        "id": pack_root.name,
        "name": (issuer_name or pack_root.name.replace("_", " ").title()),
        "version": "1.0.0-legacy",
        "default_locale": "en",
        "allows_inline_override": False,
        "theme": _v1_theme_to_v2(v1_theme),
        "compliance": {
            "footer": {
                "text": footer_text or "Confidential",
                "show_page_numbers": True,
                "show_render_date": True,
            },
            "issuer": {
                "name": issuer_name or pack_root.name,
                "lines": issuer_lines or ["(no issuer lines parsed)"],
            },
            "watermark": {
                "default_text": "Confidential",
                "template": "{brand_name} // {user}",
            },
            "disclaimer": "Legacy brand — limited compliance metadata.",
        },
        "pack_root": pack_root,
        "locales": {},
    }
    bp = BrandPack(**payload)
    deprecation = (
        f"warning: --legacy-brand loaded v1 layout at {pack_root}; "
        "this flag is deprecated. Run "
        f"`md-to-pdf brand migrate {pack_root} <v2-output>` to upgrade. "
        "Removed in v3.0."
    )
    return bp, deprecation


def _v1_theme_to_v2(v1: dict[str, Any]) -> dict[str, Any]:
    """Map v1 theme.yaml schema to v2 schema (best effort)."""
    v1_colors: dict[str, Any] = v1.get("colors", {})
    return {
        "colors": {
            "primary": v1_colors.get("brand", "#0f4c81"),
            "text": v1_colors.get("body", "#1f2937"),
            "muted": v1_colors.get("muted", "#6b7280"),
            "accent": v1_colors.get("brand", "#0f4c81"),
            "background": "#FFFFFF",
        },
        "typography": {
            "body": {"family": v1.get("fonts", {}).get("footer_face", "Noto Sans SC"),
                     "size": 11, "leading": 16},
            "heading": {"family": v1.get("fonts", {}).get("footer_face", "Noto Sans SC"),
                        "weights": [700]},
            "code": {"family": "Noto Sans Mono", "size": 9, "leading": 12},
        },
        "layout": {
            "page_size": "A4",
            "margins": {"top": 22, "right": 18, "bottom": 32, "left": 18},
            "header_height": 14,
            "footer_height": 18,
        },
        "assets": {
            "logo": "./" + v1.get("assets", {}).get("logo", "logo.png"),
            "icon": "./" + v1.get("assets", {}).get("icon", "icon.png"),
        },
    }


def _parse_md_section_first_bullet(md: str, heading: str) -> str | None:
    section = _md_section(md, heading)
    if not section:
        return None
    for line in section.splitlines():
        if line.lstrip().startswith("-"):
            return line.lstrip("- ").strip()
    return None


def _parse_md_section_bullets(md: str, heading: str) -> list[str]:
    section = _md_section(md, heading)
    if not section:
        return []
    out: list[str] = []
    for line in section.splitlines():
        if line.lstrip().startswith("-"):
            out.append(line.lstrip("- ").strip().strip("*"))
    return out


def _parse_md_section_paragraph(md: str, heading: str) -> str | None:
    section = _md_section(md, heading)
    if not section:
        return None
    paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
    return paragraphs[0] if paragraphs else None


def _md_section(md: str, heading: str) -> str:
    """Extract the body of the first `## <heading>` section (case-insensitive)."""
    lines = md.splitlines()
    out: list[str] = []
    in_section = False
    pat = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.IGNORECASE)
    for line in lines:
        if pat.match(line):
            in_section = True
            continue
        if in_section and line.startswith("##"):
            break
        if in_section:
            out.append(line)
    return "\n".join(out).strip()
