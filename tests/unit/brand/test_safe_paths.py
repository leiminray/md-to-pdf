"""Tests for safe_paths (path-sandbox spec §3, §5.4)."""
from pathlib import Path

import pytest

from mdpdf.brand.safe_paths import safe_join
from mdpdf.errors import SecurityError


def test_safe_join_resolves_relative_path(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    (root / "logo.png").write_bytes(b"x")
    out = safe_join(root, "logo.png")
    assert out == (root / "logo.png").resolve()


def test_safe_join_rejects_parent_traversal(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    with pytest.raises(SecurityError) as ei:
        safe_join(root, "../etc/passwd")
    assert ei.value.code == "PATH_ESCAPE"


def test_safe_join_rejects_absolute_path_outside_root(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    with pytest.raises(SecurityError) as ei:
        safe_join(root, "/etc/passwd")
    assert ei.value.code == "PATH_ESCAPE"


def test_safe_join_accepts_absolute_path_inside_root(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    inside = root / "assets" / "logo.png"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"x")
    out = safe_join(root, str(inside))
    assert out == inside.resolve()


def test_safe_join_rejects_file_url(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    with pytest.raises(SecurityError) as ei:
        safe_join(root, "file:///etc/passwd")
    assert ei.value.code == "PATH_ESCAPE"


def test_safe_join_rejects_remote_url(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    with pytest.raises(SecurityError) as ei:
        safe_join(root, "http://evil.example/logo.png")
    assert ei.value.code == "REMOTE_ASSET_DENIED"


def test_safe_join_rejects_https_url(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    with pytest.raises(SecurityError) as ei:
        safe_join(root, "https://evil.example/logo.png")
    assert ei.value.code == "REMOTE_ASSET_DENIED"


def test_safe_join_resolves_symlinks_within_root(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    real = root / "real.png"
    real.write_bytes(b"x")
    link = root / "link.png"
    link.symlink_to(real)
    out = safe_join(root, "link.png")
    assert out == real.resolve()


def test_safe_join_rejects_symlink_pointing_outside_root(tmp_path: Path):
    root = tmp_path / "brand"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_bytes(b"x")
    link = root / "link.png"
    link.symlink_to(outside)
    with pytest.raises(SecurityError) as ei:
        safe_join(root, "link.png")
    assert ei.value.code == "PATH_ESCAPE"
