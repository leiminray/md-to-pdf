"""Tests for fonts.installer — install_font() with mocked httpx."""
from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mdpdf.errors import FontError
from mdpdf.fonts.installer import _KNOWN_FONTS, install_font


def test_known_fonts_has_noto_sans_sc() -> None:
    assert "noto-sans-sc" in _KNOWN_FONTS


def test_known_fonts_entry_has_required_keys() -> None:
    for name, entry in _KNOWN_FONTS.items():
        assert "url" in entry, f"missing 'url' in {name}"
        assert "sha256" in entry, f"missing 'sha256' in {name}"
        assert "filename" in entry, f"missing 'filename' in {name}"


def test_install_font_unknown_name_raises(tmp_path: Path) -> None:
    with pytest.raises(FontError) as ei:
        install_font("no-such-font", target_dir=tmp_path)
    assert ei.value.code == "FONT_NOT_FOUND"


def test_install_font_success(tmp_path: Path) -> None:
    fake_content = b"fake-font-data"
    fake_sha = hashlib.sha256(fake_content).hexdigest()
    fake_entry = {
        "url": "https://example.com/NotoSansSC-Regular.ttf",
        "sha256": fake_sha,
        "filename": "NotoSansSC-Regular.ttf",
    }

    response = MagicMock()
    response.content = fake_content
    response.raise_for_status = MagicMock()

    with (
        patch("mdpdf.fonts.installer._KNOWN_FONTS", {"noto-sans-sc": fake_entry}),
        patch("mdpdf.fonts.installer.httpx") as mock_httpx,
    ):
        mock_httpx.get.return_value = response
        result = install_font("noto-sans-sc", target_dir=tmp_path)

    assert result == tmp_path / "NotoSansSC-Regular.ttf"
    assert result.read_bytes() == fake_content


def test_install_font_sha256_mismatch_raises(tmp_path: Path) -> None:
    fake_entry = {
        "url": "https://example.com/x.ttf",
        "sha256": "a" * 64,
        "filename": "NotoSansSC-Regular.ttf",
    }
    response = MagicMock()
    response.content = b"corrupted"
    response.raise_for_status = MagicMock()

    with (
        patch("mdpdf.fonts.installer._KNOWN_FONTS", {"noto-sans-sc": fake_entry}),
        patch("mdpdf.fonts.installer.httpx") as mock_httpx,
    ):
        mock_httpx.get.return_value = response
        with pytest.raises(FontError) as ei:
            install_font("noto-sans-sc", target_dir=tmp_path)

    assert ei.value.code == "FONT_SHA256_MISMATCH"
    # Tempfile must not linger after a mismatch.
    assert not list(tmp_path.glob("*.tmp"))


def test_install_font_network_error_raises(tmp_path: Path) -> None:
    fake_entry = {
        "url": "https://example.com/x.ttf",
        "sha256": "a" * 64,
        "filename": "NotoSansSC-Regular.ttf",
    }

    with (
        patch("mdpdf.fonts.installer._KNOWN_FONTS", {"noto-sans-sc": fake_entry}),
        patch("mdpdf.fonts.installer.httpx") as mock_httpx,
    ):
        mock_httpx.get.side_effect = httpx.ConnectError("connection refused")
        with pytest.raises(FontError) as ei:
            install_font("noto-sans-sc", target_dir=tmp_path)

    assert ei.value.code == "FONT_DOWNLOAD_FAILED"
