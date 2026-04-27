"""Pipeline contracts and orchestrator (RenderRequest, RenderResult, Pipeline).

See spec §2.1.1, §2.1.7.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import structlog

from mdpdf.brand.inline import load_inline_brand
from mdpdf.brand.legacy import load_legacy_brand_pack
from mdpdf.brand.overrides import apply_overrides
from mdpdf.brand.registry import BrandRegistry, resolve_brand
from mdpdf.brand.schema import BrandPack, load_brand_pack
from mdpdf.brand.styles import build_brand_styles
from mdpdf.errors import PipelineError, RendererError, TemplateError
from mdpdf.fonts.manager import FontManager
from mdpdf.markdown.ast import Document, MermaidBlock
from mdpdf.markdown.ast import Image as ASTImage
from mdpdf.markdown.parser import parse_markdown
from mdpdf.markdown.transformers import run_transformers
from mdpdf.markdown.transformers.collect_outline import collect_outline
from mdpdf.markdown.transformers.filter_metadata_blocks import filter_metadata_blocks
from mdpdf.markdown.transformers.normalize_merged_atx_headings import (
    normalize_merged_atx_headings,
)
from mdpdf.markdown.transformers.promote_toc import promote_toc
from mdpdf.markdown.transformers.strip_yaml_frontmatter import strip_yaml_frontmatter
from mdpdf.render.engine_base import RenderEngine
from mdpdf.render.engine_reportlab import ReportLabEngine
from mdpdf.renderers.base import RenderContext
from mdpdf.renderers.image import ImageRenderer
from mdpdf.renderers.mermaid_chain import select_mermaid_renderer

_log = structlog.get_logger("mdpdf.pipeline")

# v2.0 allowlist; replaced by template registry in v2.1.
_TEMPLATE_ALLOWLIST = frozenset({"generic"})


@dataclass(frozen=True)
class WatermarkOptions:
    """Watermark configuration (Plan 1: stored only; applied in Plan 4).

    `level` is a literal string per spec §2.4 — values: 'L0', 'L1', 'L1+L2'.
    L3-L5 land in v2.3.
    """

    user: str | None = None
    level: Literal["L0", "L1", "L1+L2"] = "L1+L2"
    custom_text: str | None = None


@dataclass(frozen=True)
class RenderRequest:
    """Unified input contract for CLI and Python API (spec §2.1.1)."""

    source: str | Path
    source_type: Literal["content", "path"]
    output: Path
    brand: str | None = None                       # brand id
    brand_pack_dir: Path | None = None             # explicit --brand-pack-dir
    brand_config: Path | None = None               # --brand-config (inline YAML)
    brand_overrides: list[tuple[str, str]] = field(default_factory=list)
    legacy_brand: bool = False                     # accept v1 layout
    template: str = "generic"
    watermark: WatermarkOptions = field(default_factory=WatermarkOptions)
    deterministic: bool = False
    locale: str = "en"
    audit_enabled: bool = True
    mermaid_renderer: Literal["auto", "kroki", "puppeteer", "pure"] = "auto"
    kroki_url: str | None = None
    allow_remote_assets: bool = False


@dataclass(frozen=True)
class RenderMetrics:
    """Per-phase timing in milliseconds (spec §2.1.7)."""

    parse_ms: int
    asset_resolve_ms: int
    render_ms: int
    post_process_ms: int
    total_ms: int


@dataclass(frozen=True)
class RenderResult:
    """Pipeline.render() return value (spec §2.1.7)."""

    output_path: Path
    render_id: str
    pages: int
    bytes: int
    sha256: str
    warnings: list[str]
    metrics: RenderMetrics


class Pipeline:
    """Top-level orchestrator (spec §2.1).

    Plan 1 implements: validate (template allowlist only) → parse → render →
    output (atomic write) → metrics. AST transformers, brand resolution,
    asset resolution, watermark/audit post-processing land in plans 2–4.
    """

    def __init__(self, engine: RenderEngine) -> None:
        self._engine = engine

    @classmethod
    def from_env(cls) -> Pipeline:
        """Construct with default engine and config."""
        return cls(engine=ReportLabEngine())

    def render(self, request: RenderRequest) -> RenderResult:
        render_id = str(uuid.uuid4())
        t0 = time.perf_counter()

        # Validate phase: template allowlist
        if request.template not in _TEMPLATE_ALLOWLIST:
            raise TemplateError(
                code="TEMPLATE_NOT_FOUND",
                user_message=(
                    f"template '{request.template}' not found; "
                    "v2.0 supports only 'generic'. "
                    "See release notes for v2.1 template-pack system."
                ),
                render_id=render_id,
            )

        # Validate phase: brand resolution (None / id / pack-dir / inline / legacy)
        brand_pack = self._resolve_brand(request)

        # Apply overrides if any (via inline-payload mutation + reload)
        if request.brand_overrides and brand_pack is not None:
            payload = brand_pack.model_dump()
            apply_overrides(payload, request.brand_overrides)
            brand_pack = BrandPack(**payload)

        # Build styles + prepare font manager
        styles = build_brand_styles(brand_pack) if brand_pack else None
        bundled_fonts = Path(__file__).resolve().parents[2] / "fonts"
        brand_fonts_dir: Path | None = None
        if brand_pack and brand_pack.theme.assets.fonts_dir:
            from mdpdf.brand.safe_paths import safe_join
            try:
                brand_fonts_dir = safe_join(
                    brand_pack.pack_root, brand_pack.theme.assets.fonts_dir
                )
            except Exception:  # noqa: BLE001
                brand_fonts_dir = None
        fm = FontManager(bundled_dir=bundled_fonts, brand_fonts_dir=brand_fonts_dir)

        # Read the source once
        if request.source_type == "path":
            source_text = Path(request.source).read_text(encoding="utf-8")
        else:
            assert isinstance(request.source, str)  # noqa: S101 — type narrow for mypy
            source_text = request.source

        # Replace Plan 1 byte-level CJK guard with font-availability check
        fm.register_for_text(source_text)

        _log.info(
            "render.start",
            render_id=render_id,
            brand=brand_pack.id if brand_pack else None,
            template=request.template,
            output=str(request.output),
        )

        # Parse phase
        t_parse_start = time.perf_counter()
        document = parse_markdown(source_text)
        document = run_transformers(
            document,
            [
                strip_yaml_frontmatter,
                normalize_merged_atx_headings,
                filter_metadata_blocks,
                promote_toc,
                collect_outline,
            ],
        )
        parse_ms = int((time.perf_counter() - t_parse_start) * 1000)

        # Asset Resolution phase: pre-walk AST and resolve external assets
        # (Mermaid + image) so they're cached before the render phase. This
        # populates the cache and makes asset_resolve_ms a meaningful metric.
        t_assets_start = time.perf_counter()
        self._prerender_assets(document, request, render_id)
        asset_resolve_ms = int((time.perf_counter() - t_assets_start) * 1000)

        # Render phase: instantiate engine with brand styles if any
        engine = self._engine if styles is None else ReportLabEngine(brand_styles=styles)
        t_render_start = time.perf_counter()
        try:
            pages = engine.render(document, request.output)
        except Exception as exc:  # noqa: BLE001 — wrap in PipelineError
            raise PipelineError(
                code="RENDER_FAILED",
                user_message=f"engine '{engine.name}' failed during render",
                technical_details=repr(exc),
                render_id=render_id,
            ) from exc
        render_ms = int((time.perf_counter() - t_render_start) * 1000)

        # Output phase metrics
        size_bytes = request.output.stat().st_size
        sha = hashlib.sha256(request.output.read_bytes()).hexdigest()
        total_ms = int((time.perf_counter() - t0) * 1000)

        result = RenderResult(
            output_path=request.output,
            render_id=render_id,
            pages=pages,
            bytes=size_bytes,
            sha256=sha,
            warnings=[],
            metrics=RenderMetrics(
                parse_ms=parse_ms,
                asset_resolve_ms=asset_resolve_ms,
                render_ms=render_ms,
                post_process_ms=0,
                total_ms=total_ms,
            ),
        )

        _log.info(
            "render.complete",
            render_id=render_id,
            pages=pages,
            bytes=size_bytes,
            sha256=sha,
            duration_ms=total_ms,
        )

        return result

    def _resolve_brand(self, request: RenderRequest) -> BrandPack | None:
        if request.brand_config:
            return load_inline_brand(request.brand_config)
        if request.brand_pack_dir:
            if request.legacy_brand:
                bp, dep = load_legacy_brand_pack(request.brand_pack_dir)
                _log.warning("brand.legacy_loaded", deprecation=dep)
                return bp
            return load_brand_pack(request.brand_pack_dir)
        if request.brand:
            return resolve_brand(BrandRegistry(brand_id=request.brand))
        return None

    def _prerender_assets(
        self, document: Document, request: RenderRequest, render_id: str,
    ) -> None:
        """Walk AST, eagerly render Mermaid and Image assets to populate cache."""
        ctx = RenderContext(
            cache_root=Path.home() / ".md-to-pdf" / "cache",
            brand_pack=None,  # populated when we wire brand into RenderContext (Plan 4)
            allow_remote_assets=request.allow_remote_assets,
            deterministic=request.deterministic,
        )

        for node in document.children:
            try:
                if isinstance(node, MermaidBlock):
                    renderer = select_mermaid_renderer(
                        preference=request.mermaid_renderer,
                        ctx=ctx,
                        kroki_url_override=request.kroki_url,
                    )
                    renderer.render(node.source, ctx)
                elif isinstance(node, ASTImage):
                    ImageRenderer().render(node, ctx)
            except RendererError as e:
                if e.render_id is None:
                    e.render_id = render_id
                raise
