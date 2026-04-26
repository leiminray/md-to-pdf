"""Tests for v1 → v2 brand migrator (spec §3.8)."""
from pathlib import Path

import pytest

from mdpdf.brand.migrate import migrate_v1_to_v2
from mdpdf.brand.schema import load_brand_pack
from mdpdf.errors import BrandError


def _v1_brand_kits(at: Path) -> Path:
    bk = at / "brand_kits"
    bk.mkdir()
    (bk / "theme.yaml").write_text(
        'colors:\n  brand: "#0f4c81"\n  body: "#1f2937"\n  muted: "#6b7280"\n'
        '  table_header_bg: "#f3f4f6"\n  table_grid: "#d1d5db"\n  table_fin_negative: "#dc2626"\n'
        '  issuer_title: "#374151"\n  issuer_body: "#6b7280"\n'
        '  issuer_card_bg: "#f8fafc"\n  issuer_card_border: "#dbe3ea"\n'
        'typography:\n  footer_confidential_pt: 7\n  footer_page_num_pt: 8\n'
        'fonts:\n  footer_face: "IDS-Noto-Regular"\n  header_generated_face: "IDS-Noto-Regular"\n'
        'assets:\n  logo: "logo.png"\n  icon: "icon.png"\n'
        'layout:\n  logo_header_height_pt: 34\n  logo_header_width_scale: 4.0\n'
    )
    (bk / "compliance.md").write_text(
        '## brand profiles\n- ACME Corp\n\n'
        '## Footer confidential\n\nConfidential\n\n'
        '## Issuer lines\n- **ACME Corp**\n- www.acme.example\n'
    )
    (bk / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (bk / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return bk


def test_migrate_produces_v2_layout(tmp_path: Path):
    v1 = _v1_brand_kits(tmp_path)
    v2 = tmp_path / "out-v2"
    migrate_v1_to_v2(v1, v2, target_id="acme")
    assert (v2 / "brand.yaml").exists()
    assert (v2 / "theme.yaml").exists()
    assert (v2 / "compliance.yaml").exists()
    assert (v2 / "LICENSE").exists()
    assert (v2 / "assets" / "logo.png").exists()
    assert (v2 / "assets" / "icon.png").exists()


def test_migrate_round_trips_through_validation(tmp_path: Path):
    v1 = _v1_brand_kits(tmp_path)
    v2 = tmp_path / "acme"
    migrate_v1_to_v2(v1, v2, target_id="acme")
    bp = load_brand_pack(v2)
    assert bp.id == "acme"
    assert bp.compliance.issuer.name == "ACME Corp"


def test_migrate_refuses_to_overwrite_unless_force(tmp_path: Path):
    v1 = _v1_brand_kits(tmp_path)
    v2 = tmp_path / "out-v2"
    v2.mkdir()
    (v2 / "preexisting.txt").write_text("x")
    with pytest.raises(BrandError):
        migrate_v1_to_v2(v1, v2, target_id="acme")
    # With force=True it succeeds
    migrate_v1_to_v2(v1, v2, target_id="acme", force=True)
    assert (v2 / "brand.yaml").exists()


def test_migrate_emits_default_locale_if_compliance_md_has_chinese(tmp_path: Path):
    """If compliance.md contains CJK, mark the default locale as zh-CN heuristically."""
    bk = _v1_brand_kits(tmp_path)
    (bk / "compliance.md").write_text(
        '## brand profiles\n- 测试公司\n## Footer confidential\n\n机密\n\n## Issuer lines\n- 测试\n'
    )
    v2 = tmp_path / "testcn"
    migrate_v1_to_v2(bk, v2, target_id="testcn")
    bp = load_brand_pack(v2)
    assert bp.default_locale == "zh-CN"
