"""Tests for v1 brand layout adapter (--legacy-brand)."""
from pathlib import Path

import pytest

from mdpdf.brand.legacy import load_legacy_brand_pack
from mdpdf.errors import BrandError


def _v1_brand_kits(at: Path) -> Path:
    """Recreate a minimal v1 brand_kits/-style layout."""
    bk = at / "brand_kits"
    bk.mkdir()
    (bk / "theme.yaml").write_text(
        'colors:\n  brand: "#0f4c81"\n  body: "#1f2937"\n  muted: "#6b7280"\n'
        '  table_header_bg: "#f3f4f6"\n  table_grid: "#d1d5db"\n'
        '  table_fin_negative: "#dc2626"\n  issuer_title: "#374151"\n'
        '  issuer_body: "#6b7280"\n  issuer_card_bg: "#f8fafc"\n'
        '  issuer_card_border: "#dbe3ea"\n'
        'typography:\n  footer_confidential_pt: 7\n  footer_page_num_pt: 8\n'
        '  header_generated_pt: 8\n  issuer_title_pt: 9\n  issuer_body_pt: 8\n'
        'fonts:\n  footer_face: "IDS-Noto-Regular"\n  header_generated_face: "IDS-Noto-Regular"\n'
        'assets:\n  logo: "logo.png"\n  icon: "icon.png"\n'
        'layout:\n  logo_header_height_pt: 34\n  logo_header_width_scale: 4.0\n'
    )
    (bk / "compliance.md").write_text(
        '# Brand compliance copy\n\n'
        '## brand profiles\n\n- HEXCLOUD (Hong Kong) Technology Company Limited\n\n'
        '## Footer confidential\n\nConfidential · No distribution\n\n'
        '## Issuer lines\n- **HEXCLOUD (Hong Kong) Technology Company Limited**\n'
        '- www.idimsum.com\n'
    )
    (bk / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal stub
    (bk / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return bk


def test_legacy_v1_brand_loads(tmp_path: Path):
    pack = _v1_brand_kits(tmp_path)
    bp, deprecation = load_legacy_brand_pack(pack)
    assert bp.id == "brand_kits"
    assert bp.name  # non-empty
    assert "deprecated" in deprecation.lower() or "legacy" in deprecation.lower()


def test_legacy_brand_extracts_issuer_from_compliance_md(tmp_path: Path):
    pack = _v1_brand_kits(tmp_path)
    bp, _ = load_legacy_brand_pack(pack)
    assert "HEXCLOUD" in bp.compliance.issuer.name


def test_legacy_brand_extracts_footer_text(tmp_path: Path):
    pack = _v1_brand_kits(tmp_path)
    bp, _ = load_legacy_brand_pack(pack)
    assert "Confidential" in bp.compliance.footer.text


def test_legacy_brand_missing_theme_raises(tmp_path: Path):
    bad = tmp_path / "no-theme"
    bad.mkdir()
    with pytest.raises(BrandError) as ei:
        load_legacy_brand_pack(bad)
    assert ei.value.code == "BRAND_NOT_FOUND"
