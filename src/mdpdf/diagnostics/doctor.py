"""md-to-pdf doctor — structured environment health report (spec §6.3).

Returns a dict suitable for JSON serialisation. Every probe is wrapped in
try/except so ``run_doctor()`` never raises. All imports live at module top
per the no-inline-imports convention (P2-006 / P5-006).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

import mdpdf
from mdpdf.brand.registry import BrandRegistry
from mdpdf.security.audit import _resolve_default_path

_FONTS_DIR = Path(__file__).resolve().parents[3] / "fonts"
_USER_FONTS_DIR = Path.home() / ".md-to-pdf" / "fonts"


def _probe_python() -> dict[str, Any]:
    return {
        "version": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
    }


def _probe_mdpdf() -> dict[str, Any]:
    return {
        "version": mdpdf.__version__,
        "install_location": str(Path(mdpdf.__file__).parent),
    }


def _probe_fonts() -> dict[str, Any]:
    bundled_count = 0
    cjk_available = False
    for font_dir in (_FONTS_DIR, _USER_FONTS_DIR):
        if not font_dir.is_dir():
            continue
        for f in font_dir.iterdir():
            if f.suffix.lower() not in {".ttf", ".otf"}:
                continue
            bundled_count += 1
            name = f.name.lower()
            if "noto" in name or "cjk" in name or "sc" in name:
                cjk_available = True
    return {
        "bundled_count": bundled_count,
        "system_cjk_available": cjk_available,
    }


def _probe_mermaid() -> dict[str, Any]:
    kroki_url = os.environ.get("KROKI_URL", "http://localhost:8000")
    kroki_available = False
    try:
        resp = httpx.get(f"{kroki_url}/health", timeout=2.0)
        kroki_available = resp.status_code == 200
    except Exception:  # noqa: BLE001 — health probe must never raise
        kroki_available = False

    mmdc_path = shutil.which("mmdc")
    return {
        "kroki_available": kroki_available,
        "kroki_url": kroki_url,
        "puppeteer_available": mmdc_path is not None,
        "mmdc_path": mmdc_path,
        "mermaid_py_available": importlib.util.find_spec("mermaid") is not None,
    }


def _probe_brand_registry() -> dict[str, Any]:
    registry = BrandRegistry()
    brands = registry.list_brands()
    return {"count": len(brands), "brands": [b.id for b in brands]}


def _probe_audit_log() -> dict[str, Any]:
    path = _resolve_default_path()
    exists = path.exists()
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "parent_writable": (
            os.access(path.parent, os.W_OK) if path.parent.exists() else False
        ),
    }


def _probe_temp_paths() -> dict[str, Any]:
    tmpdir = tempfile.gettempdir()
    return {
        "tmpdir": tmpdir,
        "writable": os.access(tmpdir, os.W_OK),
    }


def run_doctor() -> dict[str, Any]:
    """Return a structured health-check report. Never raises."""
    probes: dict[str, Any] = {}
    for section, fn in (
        ("python", _probe_python),
        ("mdpdf", _probe_mdpdf),
        ("fonts", _probe_fonts),
        ("mermaid", _probe_mermaid),
        ("brand_registry", _probe_brand_registry),
        ("audit_log", _probe_audit_log),
        ("temp_paths", _probe_temp_paths),
    ):
        try:
            probes[section] = fn()
        except Exception as exc:  # noqa: BLE001 — doctor must never crash
            probes[section] = {"error": str(exc)}
    return probes
