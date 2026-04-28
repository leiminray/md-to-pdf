"""Puppeteer (mmdc) Mermaid renderer.

Invokes the Node-side `mmdc` binary. Bootstrapping `mmdc` itself is the
user's responsibility (or 's `scripts/ensure_mermaid_deps.py` for
existing users); this renderer only verifies it's on PATH and shells out.

Sandboxing: `--puppeteerConfigFile` blocks network + extensions. `mmdc`
honours the file via Puppeteer launch args.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mdpdf.cache.disk import DiskCache
from mdpdf.cache.tempfiles import TempContext
from mdpdf.errors import RendererError
from mdpdf.renderers.base import RenderContext, Renderer
from mdpdf.renderers.mermaid_lint import lint_mermaid_source

_TIMEOUT_S = 30.0
_RENDERER_VERSION = "mmdc-v1"
_THEME = "default"  # Wires brand.compliance.mermaid_theme here

_PUPPETEER_CONFIG = {
    "args": [
        "--no-sandbox",
        "--disable-features=NetworkService,Extensions",
        "--disable-extensions",
    ],
}


def _find_mmdc() -> str | None:
    return shutil.which("mmdc")


@dataclass
class PuppeteerMermaidRenderer(Renderer[str, Path]):
    name: str = "mermaid-puppeteer"

    def render(self, source: str, ctx: RenderContext) -> Path:
        lint_mermaid_source(source)
        cache = DiskCache(root=ctx.cache_root / "mermaid", suffix=".png")
        cache_key = f"{_RENDERER_VERSION}|{_THEME}|{source}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        mmdc = _find_mmdc()
        if mmdc is None:
            raise RendererError(
                code="MERMAID_RENDERER_UNAVAILABLE",
                user_message=(
                    "mmdc not found on PATH. Install with `npm install -g @mermaid-js/mermaid-cli` "
                    "or use --mermaid-renderer kroki / pure."
                ),
            )

        with TempContext(prefix="mdpdf-mmdc-") as tmp:
            in_path = tmp.path / "diagram.mmd"
            out_path = tmp.path / "diagram.png"
            cfg_path = tmp.path / "puppeteer.json"
            in_path.write_text(source, encoding="utf-8")
            cfg_path.write_text(json.dumps(_PUPPETEER_CONFIG), encoding="utf-8")
            try:
                proc = subprocess.run(  # noqa: S603  # mmdc resolved via shutil.which; temp-path args
                    [mmdc, "-i", str(in_path), "-o", str(out_path), "-p", str(cfg_path)],
                    capture_output=True,
                    timeout=_TIMEOUT_S,
                    check=False,
                )
            except subprocess.TimeoutExpired as e:
                raise RendererError(
                    code="MERMAID_TIMEOUT",
                    user_message=f"mmdc timed out after {_TIMEOUT_S}s",
                ) from e
            if proc.returncode != 0:
                stderr_raw = proc.stderr
                stderr = (
                    stderr_raw.decode("utf-8", errors="replace")
                    if isinstance(stderr_raw, bytes)
                    else str(stderr_raw)
                )
                raise RendererError(
                    code="MERMAID_INVALID_SYNTAX",
                    user_message=f"mmdc failed (exit {proc.returncode}): {stderr.strip()[:200]}",
                )
            if not out_path.exists():
                raise RendererError(
                    code="MERMAID_TIMEOUT",
                    user_message="mmdc exited 0 but did not produce a PNG",
                )
            png_bytes = out_path.read_bytes()

        if len(png_bytes) > 10 * 1024 * 1024:
            raise RendererError(
                code="MERMAID_RESOURCE_LIMIT",
                user_message=f"mmdc PNG > 10MB ({len(png_bytes)} bytes)",
            )
        return cache.put(cache_key, png_bytes)
