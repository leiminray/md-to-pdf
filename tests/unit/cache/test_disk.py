"""Tests for the sha256-keyed on-disk cache."""
from pathlib import Path

from mdpdf.cache.disk import DiskCache


def test_cache_miss_returns_none(tmp_path: Path):
    cache = DiskCache(root=tmp_path / "c", suffix=".png")
    out = cache.get("any-key")
    assert out is None


def test_put_then_get_round_trips(tmp_path: Path):
    cache = DiskCache(root=tmp_path / "c", suffix=".png")
    saved = cache.put("k1", b"PAYLOAD")
    fetched = cache.get("k1")
    assert fetched == saved
    assert fetched is not None
    assert fetched.read_bytes() == b"PAYLOAD"
    assert fetched.suffix == ".png"


def test_keys_normalised_to_sha256_hex(tmp_path: Path):
    cache = DiskCache(root=tmp_path / "c", suffix=".png")
    saved = cache.put("k1", b"PAYLOAD")
    # File name should be a 64-char hex (sha256 of "k1") + ".png"
    stem = saved.stem
    assert len(stem) == 64
    assert all(c in "0123456789abcdef" for c in stem)


def test_root_created_on_first_put(tmp_path: Path):
    root = tmp_path / "deep" / "root"
    cache = DiskCache(root=root, suffix=".png")
    cache.put("k", b"x")
    assert root.is_dir()


def test_path_for_returns_target_without_writing(tmp_path: Path):
    cache = DiskCache(root=tmp_path / "c", suffix=".svg")
    p = cache.path_for("z")
    assert not p.exists()
    assert p.suffix == ".svg"


def test_clear_removes_all(tmp_path: Path):
    cache = DiskCache(root=tmp_path / "c", suffix=".png")
    cache.put("a", b"1")
    cache.put("b", b"2")
    assert (tmp_path / "c").is_dir()
    cache.clear()
    assert not any((tmp_path / "c").iterdir())
