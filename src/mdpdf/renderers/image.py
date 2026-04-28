"""Image renderer: raster auto-downsample + SVG via cairosvg.

Local file paths are resolved relative to the markdown document's
directory (the caller passes an absolute path). Remote URLs (http/https)
are rejected unless `ctx.allow_remote_assets` is True.

Auto-downsample threshold: any side >= 2400 px is resampled to 300 dpi
(approximately 2400 px max edge for an 8 inch printable area).
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image as PILImage

from mdpdf.cache.tempfiles import atomic_write
from mdpdf.errors import RendererError, SecurityError
from mdpdf.markdown.ast import Image as ASTImage
from mdpdf.renderers.base import RenderContext, Renderer

_DOWNSAMPLE_THRESHOLD_PX = 2400


@dataclass(frozen=True)
class ImageRenderResult:
    path: Path
    width_px: int
    height_px: int


class ImageRenderer(Renderer[ASTImage, ImageRenderResult]):
    name = "image"

    def render(self, source: ASTImage, ctx: RenderContext) -> ImageRenderResult:
        src_path = self._resolve(source.src, ctx)
        if src_path.suffix.lower() == ".svg":
            return self._render_svg(src_path, ctx)
        return self._render_raster(src_path, ctx)

    def _resolve(self, src: str, ctx: RenderContext) -> Path:
        if src.startswith(("http://", "https://")):
            if not ctx.allow_remote_assets:
                raise SecurityError(
                    code="REMOTE_ASSET_DENIED",
                    user_message=f"remote URL not allowed: {src}",
                )
            # Fetch into the cache root.
            ctx.cache_root.mkdir(parents=True, exist_ok=True)
            local = ctx.cache_root / Path(src).name
            resp = httpx.get(src, timeout=10.0)
            resp.raise_for_status()
            local.write_bytes(resp.content)
            return local
        p = Path(src)
        if not p.exists():
            raise FileNotFoundError(f"image not found: {p}")
        return p

    def _render_raster(self, p: Path, ctx: RenderContext) -> ImageRenderResult:
        ctx.cache_root.mkdir(parents=True, exist_ok=True)
        with PILImage.open(p) as img:
            w, h = img.size
            if max(w, h) > _DOWNSAMPLE_THRESHOLD_PX:
                ratio = _DOWNSAMPLE_THRESHOLD_PX / max(w, h)
                new_size = (int(w * ratio), int(h * ratio))
                resized = img.resize(new_size, PILImage.Resampling.LANCZOS)
                w, h = resized.size
                out = ctx.cache_root / f"{p.stem}.downsampled.png"
                with atomic_write(out) as fp:
                    buf = io.BytesIO()
                    resized.save(buf, "PNG")
                    fp.write(buf.getvalue())
                return ImageRenderResult(path=out, width_px=w, height_px=h)
        # No resize needed; return the original path.
        return ImageRenderResult(path=p, width_px=w, height_px=h)

    def _render_svg(self, p: Path, ctx: RenderContext) -> ImageRenderResult:
        import cairosvg  # type: ignore[import-untyped]  # lazy: no stubs published

        ctx.cache_root.mkdir(parents=True, exist_ok=True)
        out = ctx.cache_root / f"{p.stem}.svg.png"
        try:
            png_bytes = cairosvg.svg2png(url=str(p))
        except OSError as e:
            # cairosvg loads libcairo via ctypes; missing native library raises
            # OSError. Wrap as a structured renderer error so the CLI maps it
            # to the right exit code instead of the generic INTERNAL_ERROR path.
            raise RendererError(
                code="IMAGE_RENDERER_UNAVAILABLE",
                user_message=(
                    f"failed to rasterise SVG '{p.name}': libcairo unavailable. "
                    "Install via `brew install cairo` (macOS) or `apt-get install libcairo2`."
                ),
                technical_details=str(e),
            ) from e
        with atomic_write(out) as fp:
            fp.write(png_bytes)
        with PILImage.open(out) as img:
            w, h = img.size
        return ImageRenderResult(path=out, width_px=w, height_px=h)
