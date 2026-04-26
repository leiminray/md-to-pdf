"""Brand pack v2 pydantic schema (spec §3.2-3.4).

Loads `brand.yaml` + `theme.yaml` + `compliance.yaml` from a brand pack
directory, validates structure, and returns a `BrandPack` object.

Locale overlays (spec §3.1) are loaded by `registry.py` after schema
validation, since they're optional and merge over the base.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from mdpdf.errors import BrandError

_SUPPORTED_SCHEMA_MAJOR = 2


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Colors(_Frozen):
    primary: str
    text: str
    muted: str
    accent: str
    background: str


class FontSpec(_Frozen):
    family: str
    size: int = 11
    leading: int = 16
    weights: list[int] = Field(default_factory=lambda: [400])


class HeadingFontSpec(_Frozen):
    family: str
    weights: list[int] = Field(default_factory=lambda: [700])


class Typography(_Frozen):
    body: FontSpec
    heading: HeadingFontSpec
    code: FontSpec


class Margins(_Frozen):
    top: int
    right: int
    bottom: int
    left: int


class Layout(_Frozen):
    page_size: Literal["A4", "Letter", "B5", "Legal"] = "A4"
    margins: Margins
    header_height: int
    footer_height: int


class Assets(_Frozen):
    logo: str
    logo_dark: str | None = None
    icon: str
    qr: str | None = None
    fonts_dir: str | None = None


class ThemeConfig(_Frozen):
    colors: Colors
    typography: Typography
    layout: Layout
    assets: Assets


class FooterConfig(_Frozen):
    text: str
    show_page_numbers: bool = True
    show_render_date: bool = True


class IssuerQR(_Frozen):
    type: Literal["url", "vcard"] = "url"
    value: str


class IssuerConfig(_Frozen):
    name: str
    lines: list[str]
    qr: IssuerQR | None = None


class WatermarkConfig(_Frozen):
    default_text: str
    template: str


class ComplianceConfig(_Frozen):
    footer: FooterConfig
    issuer: IssuerConfig
    watermark: WatermarkConfig
    disclaimer: str


class SecurityConfig(_Frozen):
    watermark_min_level: Literal["L0", "L1", "L1+L2"] = "L1+L2"
    allow_remote_assets: bool = False


class AuditConfig(_Frozen):
    retain_render_log: bool = True


class BrandPack(_Frozen):
    schema_version: str
    id: str
    name: str
    version: str
    maintainer: str | None = None
    default_locale: str = "en"
    allows_inline_override: bool = True
    allowed_override_fields: list[str] = Field(default_factory=list)
    forbidden_override_fields: list[str] = Field(default_factory=list)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    theme: ThemeConfig
    compliance: ComplianceConfig
    pack_root: Path
    locales: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @property
    def schema_major(self) -> int:
        return int(self.schema_version.split(".")[0])


def load_brand_pack(pack_root: Path) -> BrandPack:
    """Load + validate a v2 brand pack from a directory."""
    pack_root = Path(pack_root).resolve()
    if not (pack_root / "brand.yaml").exists():
        raise BrandError(
            code="BRAND_NOT_FOUND",
            user_message=f"no brand.yaml in {pack_root}",
        )
    if not (pack_root / "LICENSE").exists():
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=f"brand pack at {pack_root} missing required LICENSE file (spec §3.1)",
        )
    brand_yaml = _load_yaml(pack_root / "brand.yaml")
    schema_major = int(str(brand_yaml.get("schema_version", "0")).split(".")[0])
    if schema_major != _SUPPORTED_SCHEMA_MAJOR:
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=(
                f"brand schema version {brand_yaml.get('schema_version')} not supported; "
                f"v2.0 supports schema major {_SUPPORTED_SCHEMA_MAJOR}.x"
            ),
        )
    if brand_yaml.get("id") != pack_root.name:
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=(
                f"brand id '{brand_yaml.get('id')}' does not match directory "
                f"name '{pack_root.name}' (spec §3.2)"
            ),
        )
    theme_path = pack_root / brand_yaml.get("theme", "./theme.yaml").lstrip("./")
    compliance_path = pack_root / brand_yaml.get("compliance", "./compliance.yaml").lstrip("./")
    if not theme_path.exists():
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=f"theme file not found: {theme_path}",
        )
    if not compliance_path.exists():
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=f"compliance file not found: {compliance_path}",
        )
    theme_yaml = _load_yaml(theme_path)
    compliance_yaml = _load_yaml(compliance_path)

    payload: dict[str, Any] = {
        **brand_yaml,
        "theme": theme_yaml,
        "compliance": compliance_yaml,
        "pack_root": pack_root,
    }
    locales: dict[str, dict[str, Any]] = {}
    for locale_id, locale_rel in (brand_yaml.get("locales") or {}).items():
        locale_path = pack_root / locale_rel.lstrip("./")
        if not locale_path.exists():
            raise BrandError(
                code="BRAND_VALIDATION_FAILED",
                user_message=f"locale file not found: {locale_path}",
            )
        locales[locale_id] = _load_yaml(locale_path)
    payload["locales"] = locales
    try:
        return BrandPack(**payload)
    except ValidationError as ve:
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=f"brand schema validation failed for {pack_root}: {ve.errors()[0]['msg']}",
            technical_details=str(ve),
        ) from ve


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        result = yaml.safe_load(f) or {}
    if not isinstance(result, dict):
        raise BrandError(
            code="BRAND_VALIDATION_FAILED",
            user_message=f"YAML file {path} must contain a mapping at top level",
        )
    return result
