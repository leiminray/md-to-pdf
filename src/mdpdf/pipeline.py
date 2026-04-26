"""Pipeline contracts and orchestrator (RenderRequest, RenderResult, Pipeline).

See spec §2.1.1, §2.1.7.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import structlog

from mdpdf.errors import FontError, PipelineError, TemplateError
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

_log = structlog.get_logger("mdpdf.pipeline")

# v2.0 allowlist; replaced by template registry in v2.1.
_TEMPLATE_ALLOWLIST = frozenset({"generic"})


def _is_cjk(ch: str) -> bool:
    """Detect CJK code points (CJK Unified, Hiragana, Katakana, Hangul)."""
    cp = ord(ch)
    return (
        0x3040 <= cp <= 0x309F  # Hiragana
        or 0x30A0 <= cp <= 0x30FF  # Katakana
        or 0x3400 <= cp <= 0x4DBF  # CJK Extension A
        or 0x4E00 <= cp <= 0x9FFF  # CJK Unified
        or 0xAC00 <= cp <= 0xD7AF  # Hangul Syllables
        or 0xF900 <= cp <= 0xFAFF  # CJK Compatibility
    )


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
    brand: str | dict[str, Any] | None = None
    brand_overrides: dict[str, Any] = field(default_factory=dict)
    template: str = "generic"
    watermark: WatermarkOptions = field(default_factory=WatermarkOptions)
    deterministic: bool = False
    locale: str = "en"
    audit_enabled: bool = True


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

        # Validate phase (Plan 1: only template allowlist; other steps in plans 2-4)
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

        # Read the source once (path branch needs the bytes for CJK preview
        # AND the full string for parsing — avoid double I/O on large docs).
        if request.source_type == "path":
            source_text = Path(request.source).read_text(encoding="utf-8")
        else:
            # source_type == "content" implies source: str by RenderRequest contract.
            assert isinstance(request.source, str)  # noqa: S101 — type narrow for mypy
            source_text = request.source

        # Spec §2.1.2 step 5: fail loudly on CJK input until font manager ships
        # in Plan 2. Byte-level CJK detector (no font registry needed) — the
        # proper font/manager.py with brand-pack font resolution lands in Plan 2.
        if any(_is_cjk(c) for c in source_text[:65536]):
            raise FontError(
                code="FONT_NOT_INSTALLED",
                user_message=(
                    "Input contains CJK characters but v2.0a1 walking skeleton ships "
                    "no CJK font support. Use the v1.8.9 monolith "
                    "(`scripts/md_to_pdf.py`) for CJK input until Plan 2 lands."
                ),
                render_id=render_id,
            )

        _log.info(
            "render.start",
            render_id=render_id,
            template=request.template,
            output=str(request.output),
        )

        # Parse phase
        t_parse_start = time.perf_counter()
        document = parse_markdown(source_text)
        # AST transformers (spec §2.1.3)
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

        # Render phase
        t_render_start = time.perf_counter()
        try:
            pages = self._engine.render(document, request.output)
        except Exception as exc:  # noqa: BLE001 — wrap in PipelineError
            raise PipelineError(
                code="RENDER_FAILED",
                user_message=f"engine '{self._engine.name}' failed during render",
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
                asset_resolve_ms=0,  # Plan 3 populates
                render_ms=render_ms,
                post_process_ms=0,  # Plan 4 populates
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
