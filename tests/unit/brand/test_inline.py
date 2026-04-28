"""Tests for inline brand loading."""
from pathlib import Path

import pytest

from mdpdf.brand.inline import load_inline_brand
from mdpdf.errors import BrandError

_THEME_BLOCK = (
    'theme:\n'
    '  colors:\n'
    '    primary: "#000"\n'
    '    text: "#000"\n'
    '    muted: "#000"\n'
    '    accent: "#000"\n'
    '    background: "#fff"\n'
    '  typography:\n'
    '    body: {family: F, size: 10, leading: 12}\n'
    '    heading: {family: F, weights: [700]}\n'
    '    code: {family: F, size: 9, leading: 12}\n'
    '  layout:\n'
    '    page_size: A4\n'
    '    margins: {top: 10, right: 10, bottom: 10, left: 10}\n'
    '    header_height: 10\n'
    '    footer_height: 10\n'
    '  assets:\n'
    '    logo: ./logo.png\n'
    '    icon: ./icon.png\n'
)

_COMPLIANCE_BLOCK = (
    'compliance:\n'
    '  footer: {text: x, show_page_numbers: true, show_render_date: true}\n'
    '  issuer: {name: X, lines: [a]}\n'
    '  watermark: {default_text: x, template: x}\n'
    '  disclaimer: x\n'
)


def test_load_inline_brand_from_file(tmp_path: Path):
    """An inline brand is a single YAML containing brand+theme+compliance inline."""
    inline_yaml = tmp_path / "inline.yaml"
    inline_yaml.write_text(
        'schema_version: "2.0"\n'
        'id: inline-brand\n'
        'name: Inline\n'
        'version: "1.0.0"\n'
        + _THEME_BLOCK
        + _COMPLIANCE_BLOCK
    )
    bp = load_inline_brand(inline_yaml)
    assert bp.id == "inline-brand"
    assert bp.theme.colors.primary == "#000"
    assert bp.compliance.footer.text == "x"


def test_load_inline_brand_uses_yaml_dir_as_pack_root(tmp_path: Path):
    inline = tmp_path / "ib.yaml"
    inline.write_text(
        'schema_version: "2.0"\nid: ib\nname: I\nversion: "1.0"\n'
        + _THEME_BLOCK
        + _COMPLIANCE_BLOCK
    )
    bp = load_inline_brand(inline)
    assert bp.pack_root == tmp_path.resolve()


def test_inline_brand_missing_file_raises(tmp_path: Path):
    with pytest.raises(BrandError) as ei:
        load_inline_brand(tmp_path / "nonexistent.yaml")
    assert ei.value.code == "BRAND_NOT_FOUND"


def test_inline_brand_invalid_yaml_raises(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 2.0\nid: bad\n")  # missing required fields
    with pytest.raises(BrandError) as ei:
        load_inline_brand(bad)
    assert ei.value.code == "BRAND_VALIDATION_FAILED"
