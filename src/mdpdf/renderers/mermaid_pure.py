"""Pure-Python Mermaid renderer via the optional `mermaid-py` package.

Lower fidelity than mmdc/Kroki. Always rejected when `--deterministic`
is set (spec §2.3) because the pure-Python implementation is not
guaranteed to produce bit-identical output across releases.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mdpdf.cache.disk import DiskCache
from mdpdf.errors import RendererError
from mdpdf.renderers.base import RenderContext, Renderer
from mdpdf.renderers.mermaid_lint import lint_mermaid_source

_RENDERER_VERSION = "mermaid-py-v1"
_THEME = "default"  # Plan 4 will wire brand.compliance.mermaid_theme here


def _import_mermaid() -> Any | None:
    try:
        import mermaid  # type: ignore[import-not-found]
        return mermaid
    except ImportError:
        return None


@dataclass
class PureMermaidRenderer(Renderer[str, Path]):
    name: str = "mermaid-pure"

    def render(self, source: str, ctx: RenderContext) -> Path:
        if ctx.deterministic:
            raise RendererError(
                code="RENDERER_NON_DETERMINISTIC",
                user_message=(
                    "pure-Python mermaid renderer is not deterministic; "
                    "use --mermaid-renderer kroki or puppeteer in --deterministic mode"
                ),
            )
        lint_mermaid_source(source)
        cache = DiskCache(root=ctx.cache_root / "mermaid", suffix=".png")
        cache_key = f"{_RENDERER_VERSION}|{_THEME}|{source}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        mermaid_mod = _import_mermaid()
        if mermaid_mod is None:
            raise RendererError(
                code="MERMAID_RENDERER_UNAVAILABLE",
                user_message=(
                    "mermaid-py not installed. Install with "
                    "`pip install \"md-to-pdf[mermaid-pure]\"` or use "
                    "--mermaid-renderer kroki/puppeteer."
                ),
            )

        png_bytes = mermaid_mod.to_png(source)
        if len(png_bytes) > 10 * 1024 * 1024:
            raise RendererError(
                code="MERMAID_RESOURCE_LIMIT",
                user_message=f"mermaid-py PNG > 10MB ({len(png_bytes)} bytes)",
            )
        return cache.put(cache_key, png_bytes)
