"""Pipeline contracts (RenderRequest, RenderResult, RenderMetrics).

See spec §2.1.1, §2.1.7. The Pipeline class itself is added in Task 11;
this file ships the dataclasses first so other modules can import them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


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


import hashlib
import time
import uuid

import structlog

from mdpdf.errors import PipelineError, TemplateError
from mdpdf.markdown.parser import parse_markdown
from mdpdf.render.engine_base import RenderEngine
from mdpdf.render.engine_reportlab import ReportLabEngine

_log = structlog.get_logger("mdpdf.pipeline")

# v2.0 allowlist; replaced by template registry in v2.1.
_TEMPLATE_ALLOWLIST = frozenset({"generic"})


class Pipeline:
    """Top-level orchestrator (spec §2.1).

    Plan 1 implements: validate (template allowlist only) → parse → render →
    output (atomic write) → metrics. AST transformers, brand resolution,
    asset resolution, watermark/audit post-processing land in plans 2–4.
    """

    def __init__(self, engine: RenderEngine) -> None:
        self._engine = engine

    @classmethod
    def from_env(cls) -> "Pipeline":
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

        _log.info(
            "render.start",
            render_id=render_id,
            template=request.template,
            output=str(request.output),
        )

        # Parse phase
        t_parse_start = time.perf_counter()
        if request.source_type == "path":
            source_text = Path(request.source).read_text(encoding="utf-8")
        else:
            assert isinstance(request.source, str)
            source_text = request.source
        document = parse_markdown(source_text)
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
