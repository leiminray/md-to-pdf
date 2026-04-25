"""Tests for atomic_write + TempContext (spec §5.6, §2.1.7)."""
from pathlib import Path

import pytest

from mdpdf.cache.tempfiles import TempContext, atomic_write


def test_atomic_write_creates_file(tmp_path: Path):
    target = tmp_path / "out.bin"
    with atomic_write(target) as f:
        f.write(b"hello")
    assert target.read_bytes() == b"hello"


def test_atomic_write_no_partial_file_on_error(tmp_path: Path):
    target = tmp_path / "out.bin"
    with pytest.raises(RuntimeError, match="boom"):
        with atomic_write(target) as f:
            f.write(b"partial")
            raise RuntimeError("boom")
    assert not target.exists()
    # tmp file from atomic_write should be cleaned up
    leftovers = list(tmp_path.glob("out.bin.tmp.*"))
    assert leftovers == []


def test_atomic_write_overwrites(tmp_path: Path):
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")
    with atomic_write(target) as f:
        f.write(b"new")
    assert target.read_bytes() == b"new"


def test_temp_context_creates_and_cleans(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    with TempContext(prefix="test-") as ctx:
        d = ctx.path
        assert d.exists()
        assert d.is_dir()
        # Write a file inside
        (d / "a.txt").write_text("x")
    assert not d.exists()


def test_temp_context_cleans_on_exception(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    saved: dict[str, Path] = {}
    with pytest.raises(RuntimeError):
        with TempContext(prefix="test-") as ctx:
            saved["path"] = ctx.path
            raise RuntimeError("failure during work")
    assert not saved["path"].exists()
