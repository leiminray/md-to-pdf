"""Tests for locale overlay loading."""
from pathlib import Path

from mdpdf.brand.schema import load_brand_pack

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
)

_MINIMAL_COMPLIANCE_YAML = (
    'footer: {text: x, show_page_numbers: true, show_render_date: true}\n'
    'issuer: {name: X, lines: [a]}\n'
    'watermark: {default_text: x, template: x}\n'
    'disclaimer: x\n'
)


def _make_brand_with_locales(at: Path) -> Path:
    pack = at / "lbrand"
    pack.mkdir(parents=True)
    (pack / "brand.yaml").write_text(
        'schema_version: "2.0"\nid: lbrand\nname: L\nversion: "1.0.0"\n'
        'theme: ./theme.yaml\ncompliance: ./compliance.yaml\n'
        'default_locale: en\n'
        'locales:\n  zh-CN: ./locales/zh-CN.yaml\n  en: ./locales/en.yaml\n'
    )
    (pack / "theme.yaml").write_text(_MINIMAL_THEME_YAML)
    (pack / "compliance.yaml").write_text(_MINIMAL_COMPLIANCE_YAML)
    (pack / "locales").mkdir()
    (pack / "locales" / "en.yaml").write_text(
        'compliance:\n  footer: {text: "CONFIDENTIAL"}\n'
    )
    (pack / "locales" / "zh-CN.yaml").write_text(
        'compliance:\n  footer: {text: "机密"}\n'
    )
    (pack / "LICENSE").write_text("test")
    return pack


def test_locales_loaded_into_brand(tmp_path: Path):
    pack = _make_brand_with_locales(tmp_path)
    bp = load_brand_pack(pack)
    assert "en" in bp.locales
    assert "zh-CN" in bp.locales
    assert bp.locales["zh-CN"]["compliance"]["footer"]["text"] == "机密"


def test_default_locale_resolved(tmp_path: Path):
    pack = _make_brand_with_locales(tmp_path)
    bp = load_brand_pack(pack)
    assert bp.default_locale == "en"


def test_no_locales_section_means_empty_dict(tmp_path: Path):
    pack = tmp_path / "nolocales"
    pack.mkdir()
    (pack / "brand.yaml").write_text(
        'schema_version: "2.0"\nid: nolocales\nname: N\nversion: "1.0.0"\n'
        'theme: ./theme.yaml\ncompliance: ./compliance.yaml\n'
    )
    (pack / "theme.yaml").write_text(_MINIMAL_THEME_YAML)
    (pack / "compliance.yaml").write_text(_MINIMAL_COMPLIANCE_YAML)
    (pack / "LICENSE").write_text("test")
    bp = load_brand_pack(pack)
    assert bp.locales == {}
