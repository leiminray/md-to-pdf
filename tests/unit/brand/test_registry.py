"""Tests for brand registry — 3-layer overlay (spec §3.5)."""
from pathlib import Path

import pytest

from mdpdf.brand.registry import (
    BrandRegistry,
    resolve_brand,
)
from mdpdf.errors import BrandError


def _make_brand(at: Path, brand_id: str) -> Path:
    """Minimal valid v2 brand pack at `at/<brand_id>/`."""
    pack = at / brand_id
    pack.mkdir(parents=True, exist_ok=True)
    (pack / "brand.yaml").write_text(
        f'schema_version: "2.0"\nid: {brand_id}\nname: {brand_id.title()}\n'
        f'version: "1.0.0"\ntheme: ./theme.yaml\ncompliance: ./compliance.yaml\n'
    )
    (pack / "theme.yaml").write_text(
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
    (pack / "compliance.yaml").write_text(
        'footer: {text: x, show_page_numbers: true, show_render_date: true}\n'
        'issuer: {name: X, lines: [a]}\n'
        'watermark: {default_text: x, template: x}\n'
        'disclaimer: x\n'
    )
    (pack / "LICENSE").write_text("test")
    return pack


def test_resolve_finds_in_explicit_path(tmp_path: Path):
    pack = _make_brand(tmp_path, "alpha")
    bp = resolve_brand(BrandRegistry(explicit_path=pack))
    assert bp.id == "alpha"


def test_resolve_finds_in_project_local(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)
    pack = _make_brand(project / ".md-to-pdf" / "brands", "alpha")
    bp = resolve_brand(BrandRegistry(brand_id="alpha", project_root=project))
    assert bp.id == "alpha"
    assert pack in bp.pack_root.parents or pack == bp.pack_root


def test_resolve_finds_in_user_dir(tmp_path: Path, monkeypatch):
    user_home = tmp_path / "home"
    user_home.mkdir()
    _make_brand(user_home / ".md-to-pdf" / "brands", "alpha")
    bp = resolve_brand(BrandRegistry(
        brand_id="alpha",
        user_home=user_home,
        project_root=tmp_path / "noproject",  # ensures project lookup misses
    ))
    assert bp.id == "alpha"


def test_explicit_path_wins_over_project(tmp_path: Path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    _make_brand(project / ".md-to-pdf" / "brands", "alpha")
    explicit = _make_brand(tmp_path / "explicit", "alpha")
    bp = resolve_brand(BrandRegistry(
        brand_id="alpha",
        explicit_path=explicit,
        project_root=project,
    ))
    assert bp.pack_root == explicit


def test_project_wins_over_user(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    user_home = tmp_path / "home"
    user_home.mkdir()
    _make_brand(user_home / ".md-to-pdf" / "brands", "alpha")
    project_pack = _make_brand(project / ".md-to-pdf" / "brands", "alpha")
    bp = resolve_brand(BrandRegistry(
        brand_id="alpha",
        user_home=user_home,
        project_root=project,
    ))
    assert bp.pack_root == project_pack


def test_resolve_brand_not_found_raises(tmp_path: Path):
    with pytest.raises(BrandError) as ei:
        resolve_brand(BrandRegistry(
            brand_id="missing",
            user_home=tmp_path,
            project_root=tmp_path,
            builtin_root=tmp_path,
        ))
    assert ei.value.code == "BRAND_NOT_FOUND"


def test_list_brands_dedupes_across_layers(tmp_path: Path):
    user_home = tmp_path / "home"
    project = tmp_path / "proj"
    user_home.mkdir()
    project.mkdir()
    _make_brand(user_home / ".md-to-pdf" / "brands", "alpha")
    _make_brand(project / ".md-to-pdf" / "brands", "alpha")
    _make_brand(user_home / ".md-to-pdf" / "brands", "beta")
    reg = BrandRegistry(user_home=user_home, project_root=project, builtin_root=tmp_path / "noop")
    listed = reg.list_brands()
    ids = sorted({b.id for b in listed})
    assert ids == ["alpha", "beta"]
    # alpha resolved from project layer (highest priority)
    alpha = next(b for b in listed if b.id == "alpha")
    assert "proj" in str(alpha.pack_root)
