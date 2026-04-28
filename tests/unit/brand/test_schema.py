"""Tests for brand pydantic schema."""
from pathlib import Path

import pytest

from mdpdf.brand.schema import (
    ComplianceConfig,
    ThemeConfig,
    load_brand_pack,
)
from mdpdf.errors import BrandError

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_valid_brand_pack():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    assert bp.id == "valid-brand"
    assert bp.name == "Valid Brand"
    assert bp.version == "1.0.0"
    assert bp.schema_version == "2.0"


def test_brand_pack_includes_theme_and_compliance():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    assert isinstance(bp.theme, ThemeConfig)
    assert isinstance(bp.compliance, ComplianceConfig)
    assert bp.theme.colors.primary == "#0066CC"
    assert bp.compliance.footer.text == "CONFIDENTIAL"


def test_typography_body_keys():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    assert bp.theme.typography.body.family == "Noto Sans SC"
    assert bp.theme.typography.body.size == 11
    assert bp.theme.typography.body.leading == 16


def test_layout_margins():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    assert bp.theme.layout.margins.top == 22
    assert bp.theme.layout.margins.bottom == 32


def test_security_min_watermark():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    assert bp.security.watermark_min_level == "L1+L2"
    assert bp.security.allow_remote_assets is False


def test_overrides_whitelist_and_blacklist():
    bp = load_brand_pack(FIXTURES / "valid-brand")
    assert "theme.colors.accent" in bp.allowed_override_fields
    assert "compliance.issuer" in bp.forbidden_override_fields


_MINIMAL_THEME_YAML = (
    'colors:\n'
    '  primary: "#000"\n'
    '  text: "#000"\n'
    '  muted: "#000"\n'
    '  accent: "#000"\n'
    '  background: "#fff"\n'
    'typography:\n'
    '  body: {family: F, size: 10, leading: 12}\n'
    '  heading: {family: F, weights: [700]}\n'
    '  code: {family: F, size: 9, leading: 12}\n'
    'layout:\n'
    '  page_size: A4\n'
    '  margins: {top: 10, right: 10, bottom: 10, left: 10}\n'
    '  header_height: 10\n'
    '  footer_height: 10\n'
    'assets:\n'
    '  logo: ./logo.png\n'
    '  icon: ./icon.png\n'
    '  fonts_dir: ./fonts\n'
)

_MINIMAL_COMPLIANCE_YAML = (
    'footer: {text: x, show_page_numbers: true, show_render_date: true}\n'
    'issuer: {name: X, lines: [a]}\n'
    'watermark: {default_text: x, template: x}\n'
    'disclaimer: x\n'
)


def test_id_must_match_directory_name(tmp_path: Path):
    """If brand.yaml id != dir name, BrandError."""
    brand_dir = tmp_path / "wrongname"
    brand_dir.mkdir()
    (brand_dir / "brand.yaml").write_text(
        'schema_version: "2.0"\nid: rightname\nname: X\nversion: "1.0"\n'
        'theme: ./theme.yaml\ncompliance: ./compliance.yaml\n'
    )
    (brand_dir / "theme.yaml").write_text(_MINIMAL_THEME_YAML)
    (brand_dir / "compliance.yaml").write_text(_MINIMAL_COMPLIANCE_YAML)
    (brand_dir / "LICENSE").write_text("test")
    with pytest.raises(BrandError) as ei:
        load_brand_pack(brand_dir)
    assert ei.value.code == "BRAND_VALIDATION_FAILED"
    assert "id" in ei.value.user_message.lower()


def test_missing_brand_yaml_raises(tmp_path: Path):
    with pytest.raises(BrandError) as ei:
        load_brand_pack(tmp_path)
    assert ei.value.code == "BRAND_NOT_FOUND"


def test_missing_license_raises(tmp_path: Path):
    """LICENSE file is required."""
    brand_dir = tmp_path / "no-license"
    brand_dir.mkdir()
    (brand_dir / "brand.yaml").write_text(
        'schema_version: "2.0"\nid: no-license\nname: X\nversion: "1.0"\n'
        'theme: ./theme.yaml\ncompliance: ./compliance.yaml\n'
    )
    (brand_dir / "theme.yaml").write_text(_MINIMAL_THEME_YAML)
    (brand_dir / "compliance.yaml").write_text(_MINIMAL_COMPLIANCE_YAML)
    with pytest.raises(BrandError) as ei:
        load_brand_pack(brand_dir)
    assert ei.value.code == "BRAND_VALIDATION_FAILED"
    assert "license" in ei.value.user_message.lower()


def test_invalid_schema_version_raises(tmp_path: Path):
    brand_dir = tmp_path / "bad-schema"
    brand_dir.mkdir()
    (brand_dir / "brand.yaml").write_text(
        'schema_version: "0.1"\nid: bad-schema\nname: X\nversion: "1.0"\n'
        'theme: ./theme.yaml\ncompliance: ./compliance.yaml\n'
    )
    (brand_dir / "LICENSE").write_text("x")
    with pytest.raises(BrandError) as ei:
        load_brand_pack(brand_dir)
    assert ei.value.code == "BRAND_VALIDATION_FAILED"
