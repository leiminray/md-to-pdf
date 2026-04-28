"""Kroki HTTP-based Mermaid renderer."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from mdpdf.cache.disk import DiskCache
from mdpdf.errors import RendererError
from mdpdf.renderers.base import RenderContext, Renderer
from mdpdf.renderers.mermaid_lint import lint_mermaid_source

_TIMEOUT_S = 30.0
_RENDERER_VERSION = "kroki-v1"
_THEME = "default"  # Wires brand.compliance.mermaid_theme here


@dataclass
class KrokiMermaidRenderer(Renderer[str, Path]):
    """POST mermaid source to a Kroki server, receive SVG, convert to PNG."""

    base_url: str
    name: str = "mermaid-kroki"

    def render(self, source: str, ctx: RenderContext) -> Path:
        lint_mermaid_source(source)
        cache = DiskCache(root=ctx.cache_root / "mermaid", suffix=".png")
        cache_key = f"{_RENDERER_VERSION}|{_THEME}|{self.base_url}|{source}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            resp = httpx.post(
                f"{self.base_url.rstrip('/')}/mermaid/svg",
                content=source.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
                timeout=_TIMEOUT_S,
            )
            resp.raise_for_status()
        except httpx.TimeoutException as e:
            raise RendererError(
                code="MERMAID_TIMEOUT",
                user_message=f"kroki request timed out after {_TIMEOUT_S}s",
            ) from e
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise RendererError(
                code="MERMAID_RENDERER_UNAVAILABLE",
                user_message=f"kroki unreachable at {self.base_url}: {e}",
            ) from e
        except httpx.HTTPError as e:
            raise RendererError(
                code="MERMAID_TIMEOUT",
                user_message=f"kroki HTTP error: {e}",
            ) from e

        import cairosvg  # type: ignore[import-untyped]  # lazy: no stubs published

        png_bytes = cairosvg.svg2png(bytestring=resp.content)
        if len(png_bytes) > 10 * 1024 * 1024:
            raise RendererError(
                code="MERMAID_RESOURCE_LIMIT",
                user_message=f"kroki returned PNG > 10MB ({len(png_bytes)} bytes)",
            )
        return cache.put(cache_key, png_bytes)
