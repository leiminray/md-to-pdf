"""Pipeline contracts and orchestrator (RenderRequest, RenderResult, Pipeline).

Render request/result data classes.
"""
from __future__ import annotations

import hashlib
import os
import socket
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

import structlog

from mdpdf.brand.inline import load_inline_brand
from mdpdf.brand.legacy import load_legacy_brand_pack
from mdpdf.brand.overrides import apply_overrides
from mdpdf.brand.registry import BrandRegistry, resolve_brand
from mdpdf.brand.schema import BrandPack, load_brand_pack
from mdpdf.brand.styles import build_brand_styles
from mdpdf.errors import (
    MdpdfError,
    PipelineError,
    RendererError,
    SecurityError,
    TemplateError,
)
from mdpdf.fonts.manager import FontManager
from mdpdf.markdown.ast import Block, Document, Heading, MermaidBlock, Paragraph
from mdpdf.markdown.ast import Image as ASTImage
from mdpdf.markdown.parser import parse_markdown
from mdpdf.markdown.transformers import run_transformers
from mdpdf.markdown.transformers.collect_outline import (
    _inline_to_plain,
    collect_outline,
)
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
from mdpdf.security.audit import AuditLogger
from mdpdf.security.deterministic import (
    derive_render_id,
    frozen_create_date,
    serialise_options,
)

_log = structlog.get_logger("mdpdf.pipeline")

# v0.2.1 allowlist; replaced by template registry in v2.1.
_TEMPLATE_ALLOWLIST = frozenset({"generic"})


@dataclass(frozen=True)
class WatermarkOptions:
    """Watermark configuration. `level` is one of 'L0', 'L1', 'L2', or 'L1+L2'."""

    user: str | None = None
    level: Literal["L0", "L1", "L2", "L1+L2"] = "L0"
    force_disabled: bool = False  # True when user passed --no-watermark explicitly
    custom_text: str | None = None


@dataclass(frozen=True)
class RenderRequest:
    """Unified input contract for CLI and Python API."""

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
    """Per-phase timing in milliseconds."""

    parse_ms: int
    asset_resolve_ms: int
    render_ms: int
    post_process_ms: int
    total_ms: int


@dataclass(frozen=True)
class RenderResult:
    """Pipeline.render() return value."""

    output_path: Path
    render_id: str
    pages: int
    bytes: int
    sha256: str
    warnings: list[str]
    metrics: RenderMetrics


class Pipeline:
    """Top-level orchestrator.

    Pipeline phases: validate (template allowlist only) → parse → render →
    output (atomic write) → metrics. AST transformers, brand resolution,
    asset resolution, watermark/audit post-processing land in plans 2–4.
    """

    def __init__(
        self,
        engine: RenderEngine,
        audit: AuditLogger | None = None,
    ) -> None:
        self._engine = engine
        self._audit = audit if audit is not None else AuditLogger()

    @classmethod
    def from_env(cls) -> Pipeline:
        """Construct with default engine and config."""
        return cls(engine=ReportLabEngine())

    def render(self, request: RenderRequest) -> RenderResult:
        t0 = time.perf_counter()

        # Read source first so we have its bytes for hashing and (in
        # deterministic mode) the input to derive_render_id.
        if request.source_type == "path":
            source_text = Path(request.source).read_text(encoding="utf-8")
        else:
            assert isinstance(request.source, str)  # noqa: S101
            source_text = request.source
        source_bytes = source_text.encode("utf-8")
        input_hash = hashlib.sha256(source_bytes).hexdigest()

        # SOURCE_DATE_EPOCH is the cross-tool standard for deterministic builds;
        # parse it once and thread through both render-id derivation and date
        # freeze in the post-process pipeline.
        source_date_epoch: int | None = None
        sde_raw = os.environ.get("SOURCE_DATE_EPOCH")
        if sde_raw:
            try:
                source_date_epoch = int(sde_raw)
            except ValueError:
                source_date_epoch = None

        deterministic_mode = request.deterministic or source_date_epoch is not None
        render_date = frozen_create_date(source_date_epoch)

        if deterministic_mode:
            options_serialised = serialise_options(
                template=request.template,
                locale=request.locale,
                watermark_level=request.watermark.level,
                watermark_custom_text=request.watermark.custom_text,
                brand_overrides=dict(request.brand_overrides) if request.brand_overrides else None,
            )
            render_id = derive_render_id(
                input_bytes=source_bytes,
                brand_id=request.brand or "",
                brand_version="",  # filled in after brand resolution
                options_serialised=options_serialised,
                watermark_user=request.watermark.user,
            )
        else:
            render_id = str(uuid.uuid4())

        host_hash = hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest()[:16]

        audit_active = request.audit_enabled and self._audit is not None
        audit_input_path = (
            Path(request.source) if request.source_type == "path" else None
        )

        try:
            return self._render_inner(
                request,
                render_id=render_id,
                source_text=source_text,
                source_bytes=source_bytes,
                input_hash=input_hash,
                host_hash=host_hash,
                render_date=render_date,
                deterministic_mode=deterministic_mode,
                source_date_epoch=source_date_epoch,
                audit_active=audit_active,
                audit_input_path=audit_input_path,
                t0=t0,
            )
        except MdpdfError as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if audit_active:
                self._audit.log_error(
                    render_id=render_id,
                    duration_ms=duration_ms,
                    code=exc.code,
                    message=exc.user_message,
                )
            raise
        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if audit_active:
                self._audit.log_error(
                    render_id=render_id,
                    duration_ms=duration_ms,
                    code="UNEXPECTED",
                    message=str(exc),
                )
            raise

    def _render_inner(
        self,
        request: RenderRequest,
        *,
        render_id: str,
        source_text: str,
        source_bytes: bytes,
        input_hash: str,
        host_hash: str,
        render_date: str,
        deterministic_mode: bool,
        source_date_epoch: int | None,
        audit_active: bool,
        audit_input_path: Path | None,
        t0: float,
    ) -> RenderResult:

        # Validate phase: template allowlist
        if request.template not in _TEMPLATE_ALLOWLIST:
            raise TemplateError(
                code="TEMPLATE_NOT_FOUND",
                user_message=(
                    f"template '{request.template}' not found; "
                    "supports only 'generic'. "
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

        # Validate phase: brand SecurityConfig.watermark_min_level gates the
        # request's watermark level. If the user did NOT explicitly pass
        # --no-watermark, a brand requiring watermarks silently auto-upgrades
        # the level. If the user explicitly disabled, the brand policy errors.
        request = self._resolve_watermark_level(brand_pack, request, render_id)

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

        # source_text was already read in render() and passed in; just register
        # the fonts for it.
        fm.register_for_text(source_text)

        # Audit: emit render.start once we know the brand id (and after font
        # registration so a CJK-font failure raises before the audit start).
        if audit_active:
            self._audit.log_start(
                render_id=render_id,
                user=request.watermark.user,
                host_hash=host_hash,
                brand_id=brand_pack.id if brand_pack else "",
                brand_version=str(brand_pack.version) if brand_pack else "",
                template=request.template,
                input_path=audit_input_path,
                input_size=len(source_bytes),
                input_sha256=input_hash,
                watermark_level=request.watermark.level,
                deterministic=deterministic_mode,
                locale=request.locale,
            )

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

        # Post-process phase : footer + issuer card + watermarks +
        # deterministic date freeze. Runs in-place on the output PDF.
        from mdpdf.post_process.pipeline import (
            PostProcessOptions,
            PostProcessPipeline,
        )

        document_title = _document_title(document)
        t_pp_start = time.perf_counter()
        pp_opts = PostProcessOptions(
            brand_pack=brand_pack,
            watermark=request.watermark,
            render_id=render_id,
            render_user=request.watermark.user,
            render_date=render_date,
            render_host_hash=host_hash,
            input_hash=input_hash,
            document_title=document_title,
            locale=request.locale,
            deterministic=deterministic_mode,
            source_date_epoch=source_date_epoch,
        )
        try:
            PostProcessPipeline().run(request.output, pp_opts)
        except MdpdfError:
            raise
        except Exception as exc:
            raise PipelineError(
                code="POST_PROCESS_FAILED",
                user_message="post-process pipeline failed",
                technical_details=repr(exc),
                render_id=render_id,
            ) from exc
        post_process_ms = int((time.perf_counter() - t_pp_start) * 1000)

        # Output phase metrics — read AFTER post-process so the sha256 covers
        # the final on-disk file (including watermarks + footer).
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
                post_process_ms=post_process_ms,
                total_ms=total_ms,
            ),
        )

        if audit_active:
            self._audit.log_complete(
                render_id=render_id,
                duration_ms=total_ms,
                output_path=request.output,
                output_size=size_bytes,
                output_sha256=sha,
                pages=pages,
                renderers_used={},
                warnings=result.warnings,
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

    @staticmethod
    def _resolve_watermark_level(
        brand: BrandPack | None, request: RenderRequest, render_id: str
    ) -> RenderRequest:
        """Reconcile the requested watermark level with the brand's required
        minimum. Returns the (possibly upgraded) RenderRequest.

        Behaviour:
        - No brand, or brand min == "L0": leave request as-is.
        - Requested >= brand min: leave as-is.
        - Requested < brand min, force_disabled=False: silently upgrade to brand min.
        - Requested < brand min, force_disabled=True: raise SecurityError.
        """
        if brand is None:
            return request
        rank = {"L0": 0, "L1": 1, "L2": 1, "L1+L2": 2}
        min_level = brand.security.watermark_min_level
        if rank.get(request.watermark.level, 0) >= rank.get(min_level, 0):
            return request
        if request.watermark.force_disabled:
            raise SecurityError(
                code="WATERMARK_DENIED",
                user_message=(
                    f"brand '{brand.id}' requires watermark level "
                    f"'{min_level}' or stronger; --no-watermark was passed"
                ),
                render_id=render_id,
            )
        upgraded = WatermarkOptions(
            user=request.watermark.user,
            level=min_level,
            custom_text=request.watermark.custom_text,
            force_disabled=False,
        )
        return replace(request, watermark=upgraded)

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
        """Resolve relative image paths against the source dir, then eagerly
        render Mermaid and Image assets in parallel so they populate the disk
        cache before the engine pass.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        source_dir = (
            request.source.parent
            if request.source_type == "path" and isinstance(request.source, Path)
            else Path.cwd()
        )
        self._resolve_image_paths(document, source_dir)

        ctx = RenderContext(
            cache_root=Path.home() / ".md-to-pdf" / "cache",
            brand_pack=None,
            allow_remote_assets=request.allow_remote_assets,
            deterministic=request.deterministic,
        )

        # Collect renderable assets and dispatch them in parallel. Mermaid
        # via mmdc spawns Chromium per call (~5-10s each); a sequential
        # for-loop on a 6-diagram document costs minutes. ThreadPoolExecutor
        # boots Chromium concurrently.
        def _make_mermaid_task(r: object, s: str) -> object:
            return lambda: r.render(s, ctx)  # type: ignore[attr-defined]

        def _make_image_task(r: ImageRenderer, i: ASTImage) -> object:
            return lambda: r.render(i, ctx)

        tasks: list[object] = []
        for node, image in self._iter_renderable_assets(document):
            if isinstance(node, MermaidBlock):
                renderer = select_mermaid_renderer(
                    preference=request.mermaid_renderer,
                    ctx=ctx,
                    kroki_url_override=request.kroki_url,
                )
                tasks.append(_make_mermaid_task(renderer, node.source))
            elif image is not None:
                tasks.append(_make_image_task(ImageRenderer(), image))

        if not tasks:
            return

        # Cap concurrency: max 4 concurrent Mermaid renders.
        max_workers = min(4, len(tasks))
        first_error: RendererError | None = None
        from concurrent.futures import Future

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures: list[Future[object]] = [
                ex.submit(t) for t in tasks  # type: ignore[arg-type]
            ]
            for fut in as_completed(futures):
                try:
                    fut.result()
                except RendererError as e:
                    if e.render_id is None:
                        e.render_id = render_id
                    if first_error is None:
                        first_error = e
        if first_error is not None:
            raise first_error

    @staticmethod
    def _resolve_image_paths(document: Document, source_dir: Path) -> None:
        """Rewrite relative ASTImage.src to absolute paths against source_dir.
        Remote URLs (http/https) and already-absolute paths are left alone.
        """
        for image in Pipeline._iter_images(document):
            src = image.src
            if src.startswith(("http://", "https://")):
                continue
            p = Path(src)
            if not p.is_absolute():
                image.src = str((source_dir / p).resolve())

    @staticmethod
    def _iter_images(document: Document) -> Iterator[ASTImage]:
        for node in document.children:
            if isinstance(node, ASTImage):
                yield node
            elif isinstance(node, Paragraph):
                for child in node.children:
                    if isinstance(child, ASTImage):
                        yield child

    @staticmethod
    def _iter_renderable_assets(
        document: Document,
    ) -> Iterator[tuple[Block, ASTImage | None]]:
        for node in document.children:
            if isinstance(node, MermaidBlock):
                yield node, None
            elif isinstance(node, ASTImage):
                yield node, node
            elif isinstance(node, Paragraph):
                for child in node.children:
                    if isinstance(child, ASTImage):
                        yield node, child


def _document_title(document: Document) -> str:
    """Return the document's H1 title as plain text, or '' if absent."""
    for node in document.children:
        if isinstance(node, Heading) and node.level == 1:
            return _inline_to_plain(node.children) or ""
    return ""
