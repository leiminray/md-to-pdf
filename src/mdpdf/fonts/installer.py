"""Font downloader — install_font() downloads and verifies known fonts.

Public API: ``install_font(name, target_dir=None) -> Path``. The known-font
registry (_KNOWN_FONTS) ships with ``noto-sans-sc`` only in v2.0; future
plans may extend it via config.

P5-002: FontError uses `user_message=` not `message=`.
P5-010: FontError already exists in mdpdf.errors — do NOT re-declare it here.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
from pathlib import Path

import httpx

from mdpdf.errors import FontError

# Replace PLACEHOLDER_SHA256 with the real digest before tagging v2.0.0.
# Until the placeholder is replaced, install_font() will always fail with
# FONT_SHA256_MISMATCH — verify download flow with `mdpdf doctor` instead.
_KNOWN_FONTS: dict[str, dict[str, str]] = {
    "noto-sans-sc": {
        "url": (
            "https://github.com/googlefonts/noto-cjk/raw/main/"
            "Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
        ),
        "sha256": "PLACEHOLDER_SHA256_REPLACE_BEFORE_RELEASE",
        "filename": "NotoSansSC-Regular.otf",
    },
}

_DEFAULT_TARGET_DIR = Path.home() / ".md-to-pdf" / "fonts"


def install_font(name: str, target_dir: Path | None = None) -> Path:
    """Download, verify (sha256), and atomically save a known font."""
    if name not in _KNOWN_FONTS:
        raise FontError(
            code="FONT_NOT_FOUND",
            user_message=(
                f"Unknown font '{name}'. Available: {sorted(_KNOWN_FONTS)}"
            ),
        )

    entry = _KNOWN_FONTS[name]
    dest_dir = target_dir if target_dir is not None else _DEFAULT_TARGET_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / entry["filename"]
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

    try:
        response = httpx.get(entry["url"], follow_redirects=True, timeout=60.0)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — wrap any httpx error uniformly
        raise FontError(
            code="FONT_DOWNLOAD_FAILED",
            user_message=f"Failed to download font '{name}': {exc}",
        ) from exc

    content = response.content
    actual_sha = hashlib.sha256(content).hexdigest()
    if actual_sha != entry["sha256"]:
        raise FontError(
            code="FONT_SHA256_MISMATCH",
            user_message=(
                f"sha256 mismatch for font '{name}'. "
                f"Expected {entry['sha256']}, got {actual_sha}. "
                "The downloaded file may be corrupted or the registry entry is stale."
            ),
        )

    try:
        tmp_path.write_bytes(content)
        os.replace(tmp_path, dest_path)
    except OSError as exc:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise FontError(
            code="FONT_DOWNLOAD_FAILED",
            user_message=f"Failed to write font file '{dest_path}': {exc}",
        ) from exc

    return dest_path
